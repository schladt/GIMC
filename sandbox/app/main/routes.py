import os
import hashlib
import datetime

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding

from flask import request, jsonify, current_app, url_for, redirect
from app.main import bp
from app import db, auth
from app.models import Sample, Analysis

@auth.verify_token
def verify_token(token):
    return token == current_app.config['SECRET_TOKEN']

@bp.route('/submit/analysis/<hash>', methods=['POST'])
@auth.login_required
def submit_analysis(hash):
    # check for hash type based on length
    if len(hash) == 32:
        hash_type = 'md5'
    elif len(hash) == 40:
        hash_type = 'sha1'
    elif len(hash) == 64:
        hash_type = 'sha256'
    elif len(hash) == 56:
        hash_type = 'sha224'
    elif len(hash) == 96:
        hash_type = 'sha384'
    elif len(hash) == 128:
        hash_type = 'sha512'
    else:
        return {"error": "invalid hash"}, 400

    # get sample from database
    sample = Sample.query.filter_by(**{hash_type: hash}).first()
    if sample is None:
        return {"error": "sample not found"}, 404
    
    # create analysis object
    timestamp = datetime.datetime.utcnow()
    report_path = sample.filepath + '_{0}.json'.format(timestamp.strftime("%Y%m%d%H%M%S"))
    analysis = Analysis(sample=sample.sha256, report=report_path)
    db.session.add(analysis)
    db.session.commit()

    return {"message": "analysis successfully uploaded"}, 200

@bp.route('/submit/sample', methods=['POST'])
@auth.login_required
def submit_sample():
    # ensure file is in request
    if 'file' not in request.files:
        return {"error": "no file in request"}, 400
    
    # get file from request
    file = request.files['file']

    # ensure file has a name
    if file.filename == '':
        return {"error": "no file in request"}, 400
    
    # calculate hashes and encrypt while saving file to avoid reading file twice
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    sha224 = hashlib.sha224()
    sha384 = hashlib.sha384()
    sha512 = hashlib.sha512()

    # Key derivation from passphrase
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )

    # convert passphrase to bytes
    passphrase = current_app.config['SECRET_TOKEN']
    passphrase = passphrase.encode('utf-8')
    
    # derive key from passphrase
    key = kdf.derive(passphrase)

    # For AES encryption
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    padder = sym_padding.PKCS7(128).padder() # 128-bit block size for AES

    encrypted_content = b""
    chunk = file.read(4096)
    while len(chunk) > 0:
        # take hash of chunk before encrypting
        md5.update(chunk)
        sha1.update(chunk)
        sha256.update(chunk)
        sha224.update(chunk)
        sha384.update(chunk)
        sha512.update(chunk)

        # encrypt chunk
        padded_data = padder.update(chunk)
        encrypted_content += encryptor.update(padded_data)

        # read next chunk
        chunk = file.read(4096)

    # finalize encryption
    padded_data = padder.finalize()
    encrypted_content += encryptor.update(padded_data)
    encrypted_content += encryptor.finalize()

    # write salt, iv, and encrypted content to file on system based on hash value
    filename = sha256.hexdigest()
    filepath = os.path.join(current_app.config['DATA_PATH'], filename[0:2], filename[0:4])
    if not os.path.exists(filepath):
        os.makedirs(filepath)
    fullpath = os.path.join(filepath, filename)
    with open(fullpath, 'wb') as f:
        f.write(salt + iv + encrypted_content)

    file_hashes = {
        'md5': md5.hexdigest(),
        'sha1': sha1.hexdigest(),
        'sha256': sha256.hexdigest(),
        'sha224': sha224.hexdigest(),
        'sha384': sha384.hexdigest(),
        'sha512': sha512.hexdigest(),
    }

    # update sample if already exists, otherwise create new sample
    sample = Sample.query.filter_by(sha256=file_hashes['sha256']).first()
    if not sample:
        sample = Sample(sha256=file_hashes['sha256'])
    
    sample.md5 = file_hashes['md5']
    sample.sha1 = file_hashes['sha1']
    sample.sha224 = file_hashes['sha224']
    sample.sha384 = file_hashes['sha384']
    sample.sha512 = file_hashes['sha512']
    sample.filepath = fullpath

    db.session.add(sample)
    db.session.commit()

    # check if user requested to submit sample for analysis
    if 'analyze' in request.form and request.form['analyze'] == 'true':
        # call submit analysis endpoint
        response = submit_analysis(file_hashes['sha256'])
        if response[1] != 200:
            return response
        return {"message": "analysis successfully uploaded", 'hashes': file_hashes}, 200

    return {"message": "sample successfully uploaded", 'hashes': file_hashes}, 200

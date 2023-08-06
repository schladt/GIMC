import os
import hashlib

from flask import request, jsonify, current_app
from app.main import bp
from app import db, auth
from app.models import User

@auth.verify_token
def verify_token(token):
    return token == current_app.config['CLIENT_TOKEN']

@bp.route('/hello', methods=['POST'])
@auth.login_required
def say_hello():
    name = request.json['name']
    new_user = User(name=name)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': f'Hello, {name}!'}), 200

@bp.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify({'users': [user.name for user in users]}), 200


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
    
    # calculate hashes hashes while saving file to avoid reading file twice
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    sha224 = hashlib.sha224()
    sha384 = hashlib.sha384()
    sha512 = hashlib.sha512()

    # we first save to temp directory before moving to final destination based on hash value
    tempdir = os.path.join(current_app.config['DATA_PATH'], 'temp')
    if not os.path.exists(tempdir):
        os.makedirs(tempdir)

    with open(os.path.join(tempdir, file.filename), 'wb') as f:
        chunk = file.read(4096)
        while len(chunk) > 0:
            f.write(chunk)
            md5.update(chunk)
            sha1.update(chunk)
            sha256.update(chunk)
            sha224.update(chunk)
            sha384.update(chunk)
            sha512.update(chunk)
            chunk = file.read(4096)

    hashes = {
        'md5': md5.hexdigest(),
        'sha1': sha1.hexdigest(),
        'sha256': sha256.hexdigest(),
        'sha224': sha224.hexdigest(),
        'sha384': sha384.hexdigest(),
        'sha512': sha512.hexdigest(),
    }

    return {"message": "sample successfully uploaded", 'hashes': hashes}, 200

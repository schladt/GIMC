import os
import hashlib
import datetime
import json
import time
import threading

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding

from flask import request, jsonify, current_app, url_for, redirect, send_file, make_response
from app.main import bp
from app import db, auth
from app.models import Sample, Analysis, Tag
from utils.monitor import vmware_linux_get_running_vms, vmware_linux_reset_snapshot, vmware_linux_start_vm

import logging
# set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

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

    # check if tags were submitted
    if 'tags' in request.form:
        try:
            # get tags from request
            tags = request.form['tags']
            tags = tags.split(',')
            tags = [tag.strip() for tag in tags]

            # add tags to sample
            for tag in tags:
                # split on =
                key, value = tag.split('=')

                # check if tag exists
                tag_obj = db.session.query(Tag).filter_by(key=key, value=value).first()
                if not tag_obj:
                    tag_obj = Tag(key=key, value=value)
                    db.session.add(tag_obj)
                    db.session.commit()
                # check if tag is already associated with sample
                if tag_obj not in sample.tags:
                    sample.tags.append(tag_obj)
        except Exception as e:
            logging.info(f"error adding tags to sample: {e}")
            return {f'"error": "error adding tags to sample: {e}'}, 400

    # check if user requested to submit sample for analysis
    if 'analyze' in request.form and request.form['analyze'] == 'true':
        # call submit analysis endpoint
        response = submit_analysis(file_hashes['sha256'])
        if response[1] != 200:
            return response
        return {"message": "analysis successfully uploaded", 'hashes': file_hashes}, 200

    return {"message": "sample successfully uploaded", 'hashes': file_hashes}, 200

@bp.route('/vm/checkin', methods=['GET'])
@auth.login_required
def vm_checkin():
    """ Endpoint for VMs to check in with server and receive new analysis tasks if available """
    
    # get IP address of VM
    ip = request.remote_addr

    # get VM name from the configuration file
    vm_name = None
    for vm in current_app.config['VMS']:
        if ip == vm['ip']:
            vm_name = vm['name']

    if not vm_name:
        logging.error("requesting IP address not registered in configuration file")
        return {"error": "requesting IP address not registered in configuration file"}, 400

    logging.info(f"VM {vm_name} checking in")

    # check if analysis tasks are available
    analysis = Analysis.query.filter_by(status=0).first()

    # if no analysis tasks are available, return empty response
    if not analysis:
        return {"message": "no analysis tasks available"}, 200
    
    # if analysis tasks are available, update database and return file located at analysis.sample
    analysis.status = 1
    analysis.analysis_vm = vm_name
    db.session.commit()

    # get sample from database
    sample = Sample.query.filter_by(sha256=analysis.sample).first()
    if sample is None:
        analysis.status = 3
        analysis.error_message = "sample not found"
        db.session.commit()
        threading.Thread(target=revert_vm, args=(vm_name,current_app.config)).start()
        logging.error("sample not found for analysis task {analysis.id}")
        return {"error": "sample not found"}, 404
    
    # send file to VM WITHOUT decrypting
    response = make_response(send_file(sample.filepath, as_attachment=True, download_name=analysis.sample))
    response.headers['X-Message'] = "sample attached"
    logging.info(f"VM {vm_name} received analysis task {analysis.id} for sample {analysis.sample}")
    return response

@bp.route('/vm/submit/report', methods=['POST'])
@auth.login_required
def vm_submit_static():
    """ Endpoint for VMs to submit analysis report """

    # get IP address of VM
    ip = request.remote_addr

    # get VM name from the configuration file
    vm_name = None
    for vm in current_app.config['VMS']:
        if ip == vm['ip']:
            vm_name = vm['name']

    if not vm_name:
        logging.error(f"requesting IP address {ip} not registered in configuration file")
        return {"error": "requesting IP address not registered in configuration file"}, 400
    
    # get analysis from database based on VM name and status
    analysis = Analysis.query.filter_by(analysis_vm=vm_name, status=1).first()
    if not analysis:
        threading.Thread(target=revert_vm, args=(vm_name,current_app.config)).start()
        logging.error("no analysis task matching vm assignment")
        return {"error": "no analysis tasks available"}, 400
    
    # get report from request
    try:
        report = request.get_json()
    except Exception as e:
        logging.error(f"error getting report from request: {e}")
        report = None
    if not report:
        analysis.status = 3
        db.session.commit()
        threading.Thread(target=revert_vm, args=(vm_name,current_app.config)).start()
        logging.error("no report in request")
        return {"error": "no report in request"}, 400
    
    # save report to file
    try:
        with open(analysis.report, 'w') as outfile:
            json.dump(report, outfile, indent=4)
    except Exception as e:
        logging.error(f"error saving report to file: {e}")
        analysis.status = 3
        threading.Thread(target=revert_vm, args=(vm_name,current_app.config)).start()
        return {"error": "error saving report to file"}, 400

    # update analysis status
    analysis.status = 2
    db.session.commit()

    # revert VM to snapshot
    threading.Thread(target=revert_vm, args=(vm_name,current_app.config)).start()
    logging.info(f"VM {vm_name} successfully submitted report for analysis task {analysis.id} for sample {analysis.sample}")
    return {"message": "report successfully uploaded"}, 200

@bp.route('/vm/submit/error', methods=['POST'])
@auth.login_required
def vm_submit_error():
    """ Endpoint for VMs to submit error message """

    # get IP address of VM
    ip = request.remote_addr

    # get VM name from the configuration file
    vm_name = None
    for vm in current_app.config['VMS']:
        if ip == vm['ip']:
            vm_name = vm['name']

    if not vm_name:
        logging.info("requesting IP address not registered in configuration file")
        return {"error": "requesting IP address not registered in configuration file"}, 400
    
    # get analysis from database based on VM name
    analysis = Analysis.query.filter_by(analysis_vm=vm_name).first()
    if not analysis:
        logging.info("no analysis tasks available")
        return {"error": "no analysis tasks available"}, 400
    
    # get error message from request
    try: 
        error_data = request.get_json()
        if error_data:
            error_message = error_data['error']
        else:   
            error_message = "no error message in request"
    except Exception as e:
        logging.info(f"error getting error message from request: {e}")
        error_message = "error getting error message from request"
    
    # update analysis status
    if analysis:
        analysis.status = 3
        analysis.error_message = error_message
        db.session.commit()

    # revert VM to snapshot and return
    threading.Thread(target=revert_vm, args=(vm_name,current_app.config)).start()
    return {"message": "error message successfully uploaded"}, 200

def revert_vm(vm_name, config):
    """ Revert VM to snapshot """

    # read config file for VM provider
    vm_provider = config['VM_PROVIDER']

    if vm_provider == 'vmware':
        reset_snapshot = vmware_linux_reset_snapshot
        start_vm = vmware_linux_start_vm
        get_running_vms = vmware_linux_get_running_vms
    else:
        logging.error(f"unknown VM provider: {vm_provider}")
        return

    # get snapshot name from configuration file
    snapshot = None
    for vm in config['VMS']:
        if vm['name'] == vm_name:
            snapshot = vm['snapshot']
            break
    if not snapshot:
        logging.error(f"snapshot name not found for VM: {vm_name}")
        return

    # revert VM to snapshot
    if not reset_snapshot(vm_name, snapshot):
        logging.error(f"error reverting VM: {vm_name} to snapshot: {snapshot}")
        return

    # wait until VM is ready
    running_vms = get_running_vms()
    while vm_name in running_vms:
        time.sleep(1)
        running_vms = get_running_vms()

    # start VM
    start_vm(vm_name)

    logging.info(f"reverted VM: {vm_name} to snapshot {snapshot}")
    return
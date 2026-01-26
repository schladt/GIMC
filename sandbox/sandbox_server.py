"""
Sandbox Server for Malware Analysis
- This has NO SECURITY MEASURES AT ALL
- IT WILL EXECUTE/ANALYZE ANY MALWARE THAT IS SENT TO IT
- DO NOT USE THIS IN PRODUCTION
"""

import os
import hashlib
import datetime
import json
import time
import threading
import asyncio
import logging
import sys

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding

from flask import Flask, jsonify, request, make_response, send_file
from flask_httpauth import HTTPTokenAuth
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import Config
from models import Base, User, Analysis, Tag, Sample, sample_tag
from .monitor import vmware_linux_get_running_vms, vmware_linux_reset_snapshot, vmware_linux_start_vm
from .monitor import virsh_get_running_vms, virsh_reset_snapshot, virsh_start_vm

###################################
# Configuration and Setup
###################################

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

app = Flask(__name__)
auth = HTTPTokenAuth(scheme='Bearer')

# Load configuration from Config class
app.config.from_object(Config)

# Database setup
DATABASE_URL = app.config['SQLALCHEMY_DATABASE_URI']
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)

###################################
# Helper Functions
###################################

@auth.verify_token
def verify_token(token):
    return token == app.config['SECRET_TOKEN']

def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(engine)
    
    # Reset status of previously running analyses
    session = Session()
    try:
        analyses = session.query(Analysis).filter(Analysis.status == 1).all()
        for analysis in analyses:
            analysis.status = 0
        session.commit()
    finally:
        session.close()
        
    logging.info("Database tables created successfully")

def revert_vm(vm_name, config):
    """Revert VM to snapshot"""
    vm_provider = config['VM_PROVIDER']

    if vm_provider == 'vmware':
        reset_snapshot = vmware_linux_reset_snapshot
        start_vm = vmware_linux_start_vm
        get_running_vms = vmware_linux_get_running_vms
    elif vm_provider == 'libvirt':
        reset_snapshot = virsh_reset_snapshot
        start_vm = virsh_start_vm
        get_running_vms = virsh_get_running_vms
    else:
        logging.error(f"unknown VM provider: {vm_provider}")
        return

    # Get snapshot name from configuration file
    snapshot = None
    for vm in config['VMS']:
        if vm['name'] == vm_name:
            snapshot = vm['snapshot']
            break
    if not snapshot:
        logging.error(f"snapshot name not found for VM: {vm_name}")
        return

    # Revert VM to snapshot
    if not asyncio.run(reset_snapshot(vm_name, snapshot)):
        logging.error(f"error reverting VM: {vm_name} to snapshot: {snapshot}")
        return

    logging.info(f"reverted VM: {vm_name} to snapshot {snapshot}")
    return

###################################
# API Endpoints
###################################

@app.route('/submit/analysis/<hash>', methods=['POST'])
@auth.login_required
def submit_analysis(hash):
    """Submit a sample for analysis by hash"""
    session = Session()
    try:
        # Check for hash type based on length
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

        # Get sample from database
        sample = session.query(Sample).filter_by(**{hash_type: hash}).first()
        if sample is None:
            return {"error": "sample not found"}, 404
        
        # Create analysis object
        timestamp = datetime.datetime.now(datetime.UTC)
        report_path = sample.filepath + '_{0}.json'.format(timestamp.strftime("%Y%m%d%H%M%S"))
        analysis = Analysis(sample=sample.sha256, report=report_path)
        session.add(analysis)
        session.commit()

        return {"message": "analysis successfully uploaded", "analysis_id": analysis.id}, 200
    finally:
        session.close()

@app.route('/submit/sample', methods=['POST'])
@auth.login_required
def submit_sample():
    """Submit a malware sample for storage and optional analysis"""
    # Ensure file is in request
    if 'file' not in request.files:
        return {"error": "no file in request"}, 400
    
    # Get file from request
    file = request.files['file']

    # Ensure file has a name
    if file.filename == '':
        return {"error": "no file in request"}, 400
    
    # Calculate hashes and encrypt while saving file to avoid reading file twice
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

    # Convert passphrase to bytes
    passphrase = app.config['SECRET_TOKEN']
    passphrase = passphrase.encode('utf-8')
    
    # Derive key from passphrase
    key = kdf.derive(passphrase)

    # For AES encryption
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    padder = sym_padding.PKCS7(128).padder()

    encrypted_content = b""
    chunk = file.read(4096)
    while len(chunk) > 0:
        # Take hash of chunk before encrypting
        md5.update(chunk)
        sha1.update(chunk)
        sha256.update(chunk)
        sha224.update(chunk)
        sha384.update(chunk)
        sha512.update(chunk)

        # Encrypt chunk
        padded_data = padder.update(chunk)
        encrypted_content += encryptor.update(padded_data)

        # Read next chunk
        chunk = file.read(4096)

    # Finalize encryption
    padded_data = padder.finalize()
    encrypted_content += encryptor.update(padded_data)
    encrypted_content += encryptor.finalize()

    # Write salt, iv, and encrypted content to file
    filename = sha256.hexdigest()
    filepath = os.path.join(app.config['DATA_PATH'], filename[0:2], filename[0:4])
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

    # Update sample if already exists, otherwise create new sample
    session = Session()
    try:
        sample = session.query(Sample).filter_by(sha256=file_hashes['sha256']).first()
        if not sample:
            sample = Sample(sha256=file_hashes['sha256'])
        
        sample.md5 = file_hashes['md5']
        sample.sha1 = file_hashes['sha1']
        sample.sha224 = file_hashes['sha224']
        sample.sha384 = file_hashes['sha384']
        sample.sha512 = file_hashes['sha512']
        sample.filepath = fullpath

        session.add(sample)
        session.commit()

        # Check if tags were submitted
        if 'tags' in request.form:
            logging.info(f"adding tags to sample {file_hashes['sha256']}, tags: {request.form['tags']}")
            try:
                tags = request.form['tags']
                tags = tags.split(',')
                tags = [tag.strip() for tag in tags]

                # Add tags to sample
                for tag in tags:
                    key, value = tag.split('=')

                    # Check if tag exists
                    tag_obj = session.query(Tag).filter_by(key=key, value=value).first()
                    if not tag_obj:
                        tag_obj = Tag(key=key, value=value)
                        session.add(tag_obj)
                        session.commit()
                    # Check if tag is already associated with sample
                    if tag_obj not in sample.tags:
                        sample.tags.append(tag_obj)
                
                # Commit the tag associations
                session.commit()
            except Exception as e:
                logging.info(f"error adding tags to sample: {e}")
                session.close()
                return {f'"error": "error adding tags to sample: {e}'}, 400
    finally:
        session.close()

    # Check if user requested to submit sample for analysis
    if 'analyze' in request.form and request.form['analyze'] == 'true':
        response = submit_analysis(file_hashes['sha256'])
        if response[1] != 200:
            return response
        analysis_id = response[0].get('analysis_id')
        return {"message": "analysis successfully uploaded", 'hashes': file_hashes, 'analysis_id': analysis_id}, 200

    return {"message": "sample successfully uploaded", 'hashes': file_hashes}, 200

@app.route('/vm/checkin', methods=['GET'])
@auth.login_required
def vm_checkin():
    """Endpoint for VMs to check in with server and receive new analysis tasks if available"""
    
    # Get IP address of VM
    ip = request.remote_addr

    # Get VM name from the configuration file
    vm_name = None
    for vm in app.config['VMS']:
        if ip == vm['ip']:
            vm_name = vm['name']

    if not vm_name:
        logging.error("requesting IP address not registered in configuration file")
        return {"error": "requesting IP address not registered in configuration file"}, 400

    logging.debug(f"VM {vm_name} checking in")

    # Check if analysis tasks are available
    session = Session()
    try:
        analysis = session.query(Analysis).filter_by(status=0).first()

        # If no analysis tasks are available, return empty response
        if not analysis:
            return {"message": "no analysis tasks available"}, 200
        
        # If analysis tasks are available, update database and return file
        analysis.status = 1
        analysis.analysis_vm = vm_name
        session.commit()

        # Get sample from database
        sample = session.query(Sample).filter_by(sha256=analysis.sample).first()
        if sample is None:
            analysis.status = 3
            analysis.error_message = "sample not found"
            session.commit()
            session.close()
            threading.Thread(target=revert_vm, args=(vm_name, app.config)).start()
            logging.error(f"sample not found for analysis task {analysis.id}")
            return {"error": "sample not found"}, 404
        
        # Send file to VM WITHOUT decrypting
        response = make_response(send_file(sample.filepath, as_attachment=True, download_name=analysis.sample))
        response.headers['X-Message'] = "sample attached"
        response.headers['X-Sample-SHA256'] = analysis.sample
        response.headers['X-Analysis-ID'] = analysis.id
        logging.info(f"VM {vm_name} received analysis task {analysis.id} for sample {analysis.sample}")
        return response
    finally:
        session.close()

@app.route('/vm/submit/report', methods=['POST'])
@auth.login_required
def vm_submit_report():
    """Endpoint for VMs to submit analysis report"""

    # Get IP address of VM
    ip = request.remote_addr

    # Get VM name from the configuration file
    vm_name = None
    for vm in app.config['VMS']:
        if ip == vm['ip']:
            vm_name = vm['name']

    if not vm_name:
        logging.error(f"requesting IP address {ip} not registered in configuration file")
        return {"error": "requesting IP address not registered in configuration file"}, 400
    
    # Get analysis from database based on analysis id
    if 'X-Analysis-ID' not in request.headers:
        logging.error("no analysis ID in request")
        return {"error": "no analysis ID in request"}, 400
    
    if 'X-Sample-SHA256' not in request.headers:
        logging.error("no sample SHA256 in request")
        return {"error": "no sample SHA256 in request"}, 400

    analysis_id = request.headers['X-Analysis-ID']
    session = Session()
    try:
        analysis = session.query(Analysis).filter_by(id=analysis_id).first()
        if not analysis:
            threading.Thread(target=revert_vm, args=(vm_name, app.config)).start()
            err_msg = f"no analysis task matching {analysis_id} found"
            logging.error(err_msg)
            return {"error": err_msg}, 400

        # Make sure analysis hash matches sample hash
        if analysis.sample != request.headers['X-Sample-SHA256']:
            threading.Thread(target=revert_vm, args=(vm_name, app.config)).start()
            err_msg = f"analysis task {analysis_id} does not match sample {request.headers['X-Sample-SHA256']}"
            logging.error(err_msg)
            return {"error": err_msg}, 400

        # Get report from request
        try:
            report = request.get_json()
        except Exception as e:
            logging.error(f"error getting report from request: {e}")
            report = None
        if not report:
            analysis.status = 3
            session.commit()
            session.close()
            threading.Thread(target=revert_vm, args=(vm_name, app.config)).start()
            logging.error("no report in request")
            return {"error": "no report in request"}, 400
        
        # Save report to file
        try:
            with open(analysis.report, 'w') as outfile:
                json.dump(report, outfile, indent=4)
        except Exception as e:
            logging.error(f"error saving report to file: {e}")
            analysis.status = 3
            session.commit()
            session.close()
            threading.Thread(target=revert_vm, args=(vm_name, app.config)).start()
            return {"error": "error saving report to file"}, 400

        # Update analysis status
        analysis.status = 2
        session.commit()

        # Revert VM to snapshot
        threading.Thread(target=revert_vm, args=(vm_name, app.config)).start()
        logging.info(f"VM {vm_name} successfully submitted report for analysis task {analysis.id} for sample {analysis.sample}")
        return {"message": "report successfully uploaded"}, 200
    finally:
        session.close()

@app.route('/vm/submit/error', methods=['POST'])
@auth.login_required
def vm_submit_error():
    """Endpoint for VMs to submit error message"""

    # Get IP address of VM
    ip = request.remote_addr

    # Get VM name from the configuration file
    vm_name = None
    for vm in app.config['VMS']:
        if ip == vm['ip']:
            vm_name = vm['name']

    if not vm_name:
        logging.error("requesting IP address not registered in configuration file")
        return {"error": "requesting IP address not registered in configuration file"}, 400
    
    if 'X-Analysis-ID' not in request.headers:
        logging.error("no analysis ID in request")
        return {"error": "no analysis ID in request"}, 400

    if 'X-Sample-SHA256' not in request.headers:
        logging.error("no sample SHA256 in request")
        return {"error": "no sample SHA256 in request"}, 400

    # Get analysis from database based on VM name
    analysis_id = request.headers['X-Analysis-ID']
    session = Session()
    try:
        analysis = session.query(Analysis).filter_by(id=analysis_id).first()
        if not analysis:
            err_msg = f"no analysis task matching {analysis_id} found"
            logging.error(err_msg)
            return {"error": err_msg}, 400
        
        # Make sure analysis hash matches sample hash
        if analysis.sample != request.headers['X-Sample-SHA256']:
            threading.Thread(target=revert_vm, args=(vm_name, app.config)).start()
            err_msg = f"analysis task {analysis_id} does not match sample {request.headers['X-Sample-SHA256']}"
            logging.error(err_msg)
            return {"error": err_msg}, 400

        # Get error message from request
        try: 
            error_data = request.get_json()
            if error_data:
                error_message = error_data['error']
            else:   
                error_message = "no error message in request"
        except Exception as e:
            logging.info(f"error getting error message from request: {e}")
            error_message = "error getting error message from request"

        # Update analysis status
        if analysis:
            analysis.status = 3
            analysis.error_message = error_message
            session.commit()

        # Revert VM to snapshot and return
        threading.Thread(target=revert_vm, args=(vm_name, app.config)).start()
        logging.error(f"VM {vm_name} failed analysis task {analysis.id} for sample {analysis.sample}: {error_message}")
        return {"message": "error message successfully uploaded"}, 200
    finally:
        session.close()

###################################
# Main
###################################

def main():
    """Entry point for sandbox server"""
    init_db()
    
    # Get interface and port from command line
    if len(sys.argv) > 2:
        interface = sys.argv[1]
        port = int(sys.argv[2])
    else:
        print("Usage: python -m sandbox.sandbox_server <interface address> <port>")
        sys.exit(1)

    app.run(host=interface, port=port, threaded=True)

if __name__ == "__main__":
    main()

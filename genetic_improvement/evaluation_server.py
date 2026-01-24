"""
Evaluation Server for GI
- This has NO SECURITY MEASURES AT ALL
- IT WILL EXECUTE ANY CODE THAT IS SENT TO IT NO QUESTIONS ASKED
- DO NOT USE THIS IN PRODUCTION
"""

import base64
import hashlib
import os
import logging
import subprocess
import json
import shutil
import sys
import requests
import re
import threading
import asyncio

from flask import Flask, jsonify, request, make_response
from flask_httpauth import HTTPTokenAuth
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import UNIT_TEST_FILE, SANDBOX_TOKEN, SANDBOX_URL, Config
from models import Base, Candidate, Ingredient, Analysis, Sample, Tag

###################################
# Configuration and Setup
###################################

# Load settings from settings.json
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
settings_file = os.path.join(project_root, 'settings.json')
with open(settings_file) as f:
    settings = json.load(f)

# set up logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

app = Flask(__name__)
auth = HTTPTokenAuth(scheme='Bearer')

# Database setup
DATABASE_URL = settings['sqlalchemy_database_uri']
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)

@auth.verify_token
def verify_token(token):
    return token == settings['sandbox_token']

def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(engine)
    logging.info("Database tables created successfully")

###################################
# API Endpoints
###################################

@app.route('/testauth', methods=['POST', 'GET'])
@auth.login_required
def testauth():
    """
    Test authentication endpoint
    """
    return jsonify({'status': 'success', 'message': 'Authentication successful'}), 200

@app.route('/submit', methods=['POST'])
@auth.login_required
def submit():
    """
    Endpoint to submit code to server for evaluation
    """
    # check to see if 'code' is in the request
    if 'code' not in request.json:
        return jsonify({'status': 'error', 'message': 'No code provided'}), 400
    
    # get code
    code = request.json['code']
    
    # check if code is base64 encoded
    try:
        decoded_code = base64.b64decode(code).decode('utf-8')
    except Exception as e:
        decoded_code = code  # assume it's plain text if decoding fails
    
    # take sha256 hash of the code
    code_hash = hashlib.sha256(decoded_code.encode('utf-8')).hexdigest()

    # base64 encode the code again to store
    encoded_code = base64.b64encode(decoded_code.encode('utf-8')).decode('utf-8')

    # create a new database session
    session = Session()
    
    try:
        # check if candidate already exists
        candidate = session.query(Candidate).filter_by(hash=code_hash).first()
        if candidate:
            # reset status, fitness values, and other fields
            candidate.status = 0
            candidate.F1 = None
            candidate.F2 = None
            candidate.F3 = None
            candidate.analysis_id = None
            candidate.error_message = None
            candidate.build_vm = None
        else:
            # create new candidate entry
            candidate = Candidate(
                hash=code_hash,
                code=encoded_code,
                status=0
            )
        session.add(candidate)
        session.commit()
        
        # Handle class tag if provided
        if 'class' in request.json:
            class_value = request.json['class']
            
            # Get or create the tag
            tag = session.query(Tag).filter_by(key='class', value=class_value).first()
            if not tag:
                tag = Tag(key='class', value=class_value)
                session.add(tag)
                session.commit()
                session.refresh(tag)
                logging.info(f"Created new tag: class={class_value}")
            
            # Associate tag with candidate if not already associated
            if tag not in candidate.tags:
                candidate.tags.append(tag)
                session.commit()
                logging.info(f"Associated tag class={class_value} with candidate {code_hash[:8]}...")
            else:
                logging.info(f"Tag class={class_value} already associated with candidate {code_hash[:8]}...")
        
        session.close()
        return jsonify({'status': 'success', 'message': 'Code received for evaluation'}), 200
        
    except Exception as e:
        session.rollback()
        session.close()
        logging.error(f"Error processing submission: {e}")
        return jsonify({'status': 'error', 'message': 'Error processing submission'}), 500

@app.route('/vm/checkin', methods=['GET'])
@auth.login_required
def vm_checkin():
    """ Endpoint for build VMs to check in with server and receive new build tasks if available """
    
    # get IP address of VM
    ip = request.remote_addr

    # get VM name from the configuration file
    vm_name = None
    for vm in Config.VMS:
        if ip == vm['ip']:
            vm_name = vm['name']

    if not vm_name:
        logging.error("requesting IP address not registered in configuration file")
        return jsonify({"error": "requesting IP address not registered in configuration file"}), 400

    logging.info(f"Build VM {vm_name} checking in")

    # create a new database session
    session = Session()
    
    # check if build tasks are available (status=0 means pending)
    candidate = session.query(Candidate).filter_by(status=0).first()

    # if no build tasks are available, return empty response
    if not candidate:
        session.close()
        return jsonify({"message": "no build tasks available"}), 200
    
    # if build tasks are available, update database
    candidate.status = 1  # status=1 means building
    candidate.build_vm = vm_name
    session.commit()
    
    # send base64 encoded code to VM
    encoded_code = candidate.code
    session.close()
    
    # send code to VM as base64 encoded text in response body
    response = make_response(encoded_code)
    response.headers['Content-Type'] = 'text/plain'
    response.headers['X-Message'] = "code attached"
    response.headers['X-Candidate-Hash'] = candidate.hash
    logging.info(f"Build VM {vm_name} received build task for candidate {candidate.hash}")
    return response

@app.route('/vm/update', methods=['POST'])
@auth.login_required
def vm_update():
    """ Endpoint for build VMs to update candidate status and fitness values """
    
    # get IP address of VM
    ip = request.remote_addr

    # get VM name from the configuration file
    vm_name = None
    for vm in Config.VMS:
        if ip == vm['ip']:
            vm_name = vm['name']

    if not vm_name:
        logging.error("requesting IP address not registered in configuration file")
        return jsonify({"error": "requesting IP address not registered in configuration file"}), 400
    
    # check for candidate hash in request
    if 'hash' not in request.json:
        logging.error("no candidate hash in request")
        threading.Thread(target=revert_vm, args=(vm_name, Config)).start()
        return jsonify({"error": "no candidate hash in request"}), 400
    
    candidate_hash = request.json['hash']
    
    # create a new database session
    session = Session()
    
    # get candidate from database
    candidate = session.query(Candidate).filter_by(hash=candidate_hash).first()
    if not candidate:
        session.close()
        logging.error(f"candidate {candidate_hash} not found")
        threading.Thread(target=revert_vm, args=(vm_name, Config)).start()
        return jsonify({"error": "candidate not found"}), 404
    
    # update fields if provided
    updated_fields = []
    if 'status' in request.json:
        candidate.status = request.json['status']
        updated_fields.append('status')
    if 'F1' in request.json:
        candidate.F1 = request.json['F1']
        updated_fields.append('F1')
    if 'F2' in request.json:
        candidate.F2 = request.json['F2']
        updated_fields.append('F2')
    if 'F3' in request.json:
        candidate.F3 = request.json['F3']
        updated_fields.append('F3')
    if 'analysis_id' in request.json:
        candidate.analysis_id = request.json['analysis_id']
        updated_fields.append('analysis_id')
        
        # Create candidate-sample association when analysis_id is provided
        try:
            analysis = session.query(Analysis).filter_by(id=request.json['analysis_id']).first()
            if analysis and analysis.sample:
                sample = session.query(Sample).filter_by(sha256=analysis.sample).first()
                if sample:
                    # Associate sample with candidate if not already associated
                    if sample not in candidate.samples:
                        candidate.samples.append(sample)
                        logging.info(f"Associated sample {sample.sha256[:8]}... with candidate {candidate_hash[:8]}...")
                    else:
                        logging.info(f"Sample {sample.sha256[:8]}... already associated with candidate {candidate_hash[:8]}...")
                else:
                    logging.warning(f"Sample {analysis.sample} not found for analysis {request.json['analysis_id']}")
            else:
                logging.warning(f"Analysis {request.json['analysis_id']} not found or has no sample")
        except Exception as e:
            logging.error(f"Error associating sample with candidate: {e}")
    if 'error_message' in request.json:
        candidate.error_message = request.json['error_message']
        updated_fields.append('error_message')
    
    # Check if vm is clean (no vm revert needed)
    vm_clean = request.json.get('clean', False)
    
    # If status is complete (3) or error (4) and F3 is not provided and still NULL, set it to 0
    # This handles cases where sandbox analysis doesn't occur (build errors, testing errors, or sandbox offline)
    if 'status' in request.json and request.json['status'] in [3, 4]:
        if 'F3' not in request.json and candidate.F3 is None:
            candidate.F3 = 0
            updated_fields.append('F3 (auto-set to 0)')
            logging.info(f"Auto-setting F3 to 0 for candidate {candidate_hash} due to status {request.json['status']} without sandbox analysis")
    
    session.commit()
    session.close()
    
    logging.info(f"VM {vm_name} updated candidate {candidate_hash}: {', '.join(updated_fields)}")
    
    # revert VM if build agent is not clean on completion or error
    if 'status' in request.json and request.json['status'] in [2, 3, 4] and not vm_clean:
        threading.Thread(target=revert_vm, args=(vm_name, Config)).start()
    
    return jsonify({"message": "candidate updated successfully"}), 200

@app.route('/info/<hash>', methods=['GET'])
@auth.login_required
def info(hash):
    """ Endpoint to get candidate information by hash """
    
    # check if returncode parameter is set
    return_code = request.args.get('returncode', 'false').lower() == 'true'
    
    # create a new database session
    session = Session()
    
    # get candidate from database
    candidate = session.query(Candidate).filter_by(hash=hash).first()
    if not candidate:
        session.close()
        return jsonify({"error": "candidate not found"}), 404
    
    # build response
    response_data = {
        'hash': candidate.hash,
        'status': candidate.status,
        'F1': candidate.F1,
        'F2': candidate.F2,
        'F3': candidate.F3,
        'analysis_id': candidate.analysis_id,
        'date_added': candidate.date_added.isoformat() if candidate.date_added else None,
        'date_updated': candidate.date_updated.isoformat() if candidate.date_updated else None,
        'error_message': candidate.error_message,
        'build_vm': candidate.build_vm
    }
    
    # include code if requested
    if return_code:
        response_data['code'] = candidate.code
    
    session.close()
    return jsonify(response_data), 200

@app.route('/reanalyze/<hash>', methods=['GET'])
@auth.login_required
def reanalyze(hash):
    """ Endpoint to reset candidate status to pending for reanalysis """
    
    # create a new database session
    session = Session()
    
    # get candidate from database
    candidate = session.query(Candidate).filter_by(hash=hash).first()
    if not candidate:
        session.close()
        return jsonify({"error": "candidate not found"}), 404
    
    # reset status to pending
    candidate.status = 0
    candidate.build_vm = None
    candidate.error_message = None
    session.commit()
    session.close()
    
    logging.info(f"Candidate {hash} reset to pending for reanalysis")
    return jsonify({"message": "candidate reset to pending"}), 200

def revert_vm(vm_name, config):
    """ Revert VM to snapshot """
    from sandbox.monitor import vmware_linux_reset_snapshot, vmware_linux_start_vm, vmware_linux_get_running_vms
    from sandbox.monitor import virsh_reset_snapshot, virsh_start_vm, virsh_get_running_vms

    # read config for VM provider
    vm_provider = config.VM_PROVIDER

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

    # get snapshot name from configuration
    snapshot = None
    for vm in config.VMS:
        if vm['name'] == vm_name:
            snapshot = vm['snapshot']
            break
    if not snapshot:
        logging.error(f"snapshot name not found for VM: {vm_name}")
        return

    # revert VM to snapshot
    if not asyncio.run(reset_snapshot(vm_name, snapshot)):
        logging.error(f"error reverting VM: {vm_name} to snapshot: {snapshot}")
        return

    logging.info(f"reverted VM: {vm_name} to snapshot {snapshot}")
    return


###################################
# Main Entry Point
###################################

def main():
    """Entry point for evaluation server"""
    # get the first argument
    if len(sys.argv) > 2:
        interface = sys.argv[1]
        port = sys.argv[2]
    else:
        # exit
        print("Usage: python -m genetic_improvement.evaluation_server <interface address> <port>")
        sys.exit(1)
    # Initialize database on startup
    init_db()
    app.run(host=interface, port=int(port), debug=True, threaded=True)


if __name__ == '__main__':
    main()
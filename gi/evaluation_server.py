"""
Evaluation Server for GI
- This has NO SECURITY MEASURES AT ALL
- IT WILL EXECUTE ANY CODE THAT IS SENT TO IT NO QUESTIONS ASKED
- DO NOT USE THIS IN PRODUCTION
"""

import os
import logging
import subprocess
import json
import shutil
import requests

from flask import Flask, jsonify, request
from config import UNIT_TEST_FILE, SANDBOX_TOKEN, SANDBOX_URL

# set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

app = Flask(__name__)

@app.route('/submit', methods=['POST'])
def submit():
    """
    Endpoint to submit code to server for evaluation
    - Actually it's the only endpoint
    """
    # ensure file is the request
    if 'file' not in request.files:
        return jsonify({"message": "no file part"}), 400
    
    # get the file
    file = request.files['file']

    # ensure the file has a name
    if file.filename == '':
        return jsonify({"message": "no selected file"}), 400
    
    # create random tmp dir if not exist
    tmp_dir = os.urandom(8).hex()
    tmp_dir = f'tmp_{tmp_dir}'
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)

    # write the file to disk
    filepath = os.path.join(tmp_dir, file.filename)
    file.save(filepath)

    # compile the code
    outfilepath = os.path.join(tmp_dir, 'proto.dll')            
    p = subprocess.Popen(['gcc.exe', '-shared', '-o', outfilepath, filepath], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = p.communicate()
    if p.returncode != 0:
        logging.error(f"Error compiling code in ")
        out = out.decode("utf-8")
        err = err.decode("utf-8")
        logging.error(out)
        logging.error(err)
        # remove the tmp dir using shutil
        shutil.rmtree(tmp_dir)
        return jsonify({"message": "error compiling code"}), 500

    # run the unit tests
    logging.info("Running unit tests in {}".format(UNIT_TEST_FILE))
    p = subprocess.Popen(['python', UNIT_TEST_FILE, outfilepath], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, _) = p.communicate()
    
    # check for errors in subprocess, if so, log filename and continue
    if p.returncode != 0:
        logging.error(f"Error in unit test {UNIT_TEST_FILE} - {outfilepath}")
        logging.error(out)
        # update database with error code (1)
        # remove the tmp dir using shutil
        shutil.rmtree(tmp_dir)
        return jsonify({"message": "error running unit tests"}), 500

    # Decode output as json
    try: 
        out = json.loads(out)
        num_failures = out["num_failures"]
        num_errors = out["num_errors"]
        num_tests = out["num_tests"]
    except:
        logging.error(f"Error decoding json in unit test {UNIT_TEST_FILE} - {outfilepath}")
        # remove the tmp dir using shutil
        shutil.rmtree(tmp_dir)
        return jsonify({"message": "error decoding json from unit test output"}), 500

    # if therea are no failures or errors, recompile and submit to sandbox
    if num_failures == 0 and num_errors == 0:
        # recompile the code
        exefilepath = os.path.join(tmp_dir, 'proto.exe')
        p = subprocess.Popen(['gcc.exe', '-o', exefilepath, filepath], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        (out, err) = p.communicate()
        if p.returncode != 0:
            logging.error(f"Error recompiling code in ")
            out = out.decode("utf-8")
            err = err.decode("utf-8")
            logging.error(out)
            logging.error(err)
            # remove the tmp dir using shutil
            shutil.rmtree(tmp_dir)
            return jsonify({
                "message": "error recompiling code",
                "unit_test_results": {
                    "num_failures": num_failures,
                    "num_errors": num_errors,
                    "num_tests": num_tests
                }   }), 200

        # submit to sandbox
        logging.info("Submitting to sandbox")

        files = {
            'file': exefilepath
        }
        headers = {
            'Authorization': f'Bearer {SANDBOX_TOKEN}'
        }
        data = {
            'analyze': 'true',
            'tags': f'disposition=genome'
        }
        r = requests.post(SANDBOX_URL + "/submit/sample", files=files, headers=headers, data=data)
        if r.status_code != 200:
            logging.error(f"Error submitting to sandbox")
            shutil.rmtree(tmp_dir)
            return jsonify({
                "message": "error submitting to sandbox",
                "unit_test_results": {
                    "num_failures": num_failures,
                    "num_errors": num_errors,
                    "num_tests": num_tests
                }           
           }), 200
        else:
            logging.info(r.text)
            logging.info("Submitted to sandbox")
            # remove the tmp dir using shutil
            shutil.rmtree(tmp_dir)
            return jsonify({
                "message": "successfully submitted to sandbox",
                "unit_test_results": {
                    "num_failures": num_failures,
                    "num_errors": num_errors,
                    "num_tests": num_tests
                },
                "sandbox_hashes": r.json()['hashes']         
           }), 200




    # remove the tmp dir using shutil
    shutil.rmtree(tmp_dir)
    return jsonify({
        "num_failures": num_failures,
        "num_errors": num_errors,
        "num_tests": num_tests
    })




if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
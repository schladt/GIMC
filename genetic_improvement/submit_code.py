"""
Utility script to submit code for evaluation via a REST API.
"""
import base64
import hashlib
import logging
import os
import sys
import requests
import json
import argparse

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

ES_SERVER = settings['evaluation_server']
TOKEN = settings['sandbox_token']

if __name__ == '__main__':
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Submit code for evaluation')
    parser.add_argument('code_file', help='Path to the code file to submit')
    parser.add_argument('--class', dest='class_tag', help='Classification tag value (e.g., malware, benign)')
    args = parser.parse_args()

    code_file_path = args.code_file

    # Read the code from the specified file
    with open(code_file_path, 'r') as code_file:
        code_content = code_file.read()

    # Base64 encode the code content
    encoded_code = base64.b64encode(code_content.encode('utf-8')).decode('utf-8')

    # Prepare the payload
    payload = {
        'code': encoded_code
    }
    
    # Add class tag if provided
    if args.class_tag:
        payload['class'] = args.class_tag
    
    headers = {"Authorization": f"Bearer {TOKEN}"}

    # Send the POST request to the evaluation server
    try:
        response = requests.post(
            ES_SERVER + '/submit',
            json=payload,
            headers=headers
        )
        response.raise_for_status()
        print("Code submitted successfully. Server response:")
        print(response.json())
                
    except requests.exceptions.RequestException as e:
        logging.error(f"Error submitting code: {e}")
        print("Failed to submit code. Check logs for details.")
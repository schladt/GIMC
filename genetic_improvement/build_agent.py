"""
Build Agent for GI Evaluation Server
Runs on Windows VMs to compile, test, and submit candidates for dynamic analysis.

- This agent polls the ES API for pending candidates
- Compiles code using provided Makefile
- Runs unit tests if binary is produced
- Submits binary to GIMC sandbox for dynamic analysis
- Reports fitness scores back to ES API

SECURITY WARNING: This agent will compile and execute arbitrary code.
Only run in an isolated VM environment.
"""

import base64
import hashlib
import os
import sys
import logging
import subprocess
import json
import time
import re
import requests
import argparse
import importlib.util
from pathlib import Path

###################################
# Configuration (set via CLI args)
###################################

# Global configuration variables (will be set by parse_args)
ES_API_URL = None
ES_API_TOKEN = None
SANDBOX_URL = None
SANDBOX_TOKEN = None
BUILD_DIR = None
MAKEFILE_PATH = None
UNIT_TEST_PATH = None
POLL_INTERVAL = 5  # seconds
BUILD_TIMEOUT = 300  # seconds

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('build_agent.log'),
        logging.StreamHandler()
    ]
)

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description='Build Agent for GI Evaluation Server',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Required arguments
    parser.add_argument('--es-url', required=True,
                        help='Evaluation Server API URL (e.g., http://192.168.122.1:5000)')
    parser.add_argument('--es-token', required=True,
                        help='Evaluation Server authentication token')
    parser.add_argument('--sandbox-url', required=True,
                        help='GIMC Sandbox URL (e.g., http://192.168.122.1:8000)')
    parser.add_argument('--sandbox-token', required=True,
                        help='GIMC Sandbox authentication token')
    parser.add_argument('--build-dir', required=True,
                        help='Directory for building code (must contain Makefile)')
    parser.add_argument('--unit-test', required=True,
                        help='Path to unit test script')
    
    # Optional arguments
    parser.add_argument('--poll-interval', type=int, default=5,
                        help='Polling interval in seconds (default: 5)')
    parser.add_argument('--timeout', type=int, default=300,
                        help='Build timeout in seconds (default: 300)')
    
    args = parser.parse_args()
    
    # Set global configuration
    global ES_API_URL, ES_API_TOKEN, SANDBOX_URL, SANDBOX_TOKEN
    global BUILD_DIR, MAKEFILE_PATH, UNIT_TEST_PATH, POLL_INTERVAL, BUILD_TIMEOUT
    
    ES_API_URL = args.es_url
    ES_API_TOKEN = args.es_token
    SANDBOX_URL = args.sandbox_url
    SANDBOX_TOKEN = args.sandbox_token
    BUILD_DIR = os.path.abspath(args.build_dir)
    MAKEFILE_PATH = os.path.join(BUILD_DIR, 'Makefile')
    UNIT_TEST_PATH = os.path.abspath(args.unit_test)
    POLL_INTERVAL = args.poll_interval
    BUILD_TIMEOUT = args.timeout
    
    return args

###################################
# Makefile Parsing
###################################

def parse_makefile(makefile_path):
    """
    Parse Makefile to extract source filename and output binary name.
    Returns tuple: (source_file, output_file)
    """
    try:
        with open(makefile_path, 'r') as f:
            content = f.read()
        
        # Look for SRC or SOURCE variable
        src_match = re.search(r'^(?:SRC|SOURCE)\s*=\s*(\S+)', content, re.MULTILINE)
        if src_match:
            source_file = src_match.group(1).strip()
        else:
            # Default to persistence.c if not found
            source_file = 'persistence.c'
            logging.warning(f"Could not find SRC/SOURCE in Makefile, defaulting to {source_file}")
        
        # Look for OUT or TARGET variable
        out_match = re.search(r'^(?:OUT|TARGET)\s*=\s*(\S+)', content, re.MULTILINE)
        if out_match:
            output_file = out_match.group(1).strip()
        else:
            # Default to .exe extension
            base_name = os.path.splitext(source_file)[0]
            output_file = f"{base_name}.exe"
            logging.warning(f"Could not find OUT/TARGET in Makefile, defaulting to {output_file}")
        
        logging.info(f"Parsed Makefile: source={source_file}, output={output_file}")
        return source_file, output_file
    
    except Exception as e:
        logging.error(f"Error parsing Makefile: {e}")
        return 'persistence.c', 'persistence.exe'

###################################
# API Communication
###################################

def check_for_build_task():
    """
    Poll ES API /vm/checkin endpoint for pending build tasks.
    Returns tuple: (candidate_hash, code) or (None, None) if no tasks available
    """
    try:
        headers = {
            'Authorization': f'Bearer {ES_API_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f'{ES_API_URL}/vm/checkin',
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            # Check if there's a candidate hash in headers
            candidate_hash = response.headers.get('X-Candidate-Hash')
            if candidate_hash:
                # Code is in response body as base64
                encoded_code = response.text
                logging.info(f"Received build task for candidate: {candidate_hash}")
                return candidate_hash, encoded_code
            else:
                # No tasks available
                logging.info("No build tasks available")
                return None, None
        else:
            logging.error(f"Error checking for build tasks: {response.status_code} - {response.text}")
            return None, None
    
    except Exception as e:
        logging.error(f"Exception while checking for build tasks: {e}")
        return None, None

def update_candidate(candidate_hash, **kwargs):
    """
    Update candidate status and fitness values via ES API /vm/update endpoint.
    
    Args:
        candidate_hash: Hash of the candidate
        **kwargs: Fields to update (status, F1, F2, F3, analysis_id, error_message, clean)
                 clean: If True, signals ES that build agent cleaned up and VM doesn't need reset
    """
    try:
        headers = {
            'Authorization': f'Bearer {ES_API_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        data = {'hash': candidate_hash}
        data.update(kwargs)
        
        response = requests.post(
            f'{ES_API_URL}/vm/update',
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            logging.info(f"Successfully updated candidate {candidate_hash}: {kwargs}")
            return True
        else:
            logging.error(f"Error updating candidate: {response.status_code} - {response.text}")
            return False
    
    except Exception as e:
        logging.error(f"Exception while updating candidate: {e}")
        return False

###################################
# Build and Test
###################################

def clean_build_directory():
    """Clean and recreate build directory"""
    if os.path.exists(BUILD_DIR):
        # use make clean
        try:
            logging.info(f"Cleaning build directory: {BUILD_DIR}")
            subprocess.run(['make', 'clean', '-f', MAKEFILE_PATH], cwd=BUILD_DIR)
        except Exception as e:
            logging.warning(f"Failed to clean build directory using make clean: {e}")
    else:
        os.makedirs(BUILD_DIR, exist_ok=True)

def save_code_to_file(encoded_code, source_file):
    """
    Decode base64 code and save to source file in build directory.
    
    Args:
        encoded_code: Base64 encoded source code
        source_file: Filename to save code to
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Decode base64
        decoded_code = base64.b64decode(encoded_code).decode('utf-8')
        
        # Save to file
        source_path = os.path.join(BUILD_DIR, source_file)
        with open(source_path, 'w') as f:
            f.write(decoded_code)
        
        logging.info(f"Saved code to {source_path}")
        return True
    
    except Exception as e:
        logging.error(f"Error saving code to file: {e}")
        return False

def compile_code():
    """
    Compile code using Makefile and compute F1 fitness from compiler output.
    
    Returns:
        tuple: (success: bool, F1: float, output_file: str or None, error_message: str or None)
    """
    try:
        # Run make command
        result = subprocess.run(
            ['make', '-f', 'Makefile'],
            cwd=BUILD_DIR,
            capture_output=True,
            text=True,
            timeout=BUILD_TIMEOUT
        )
        
        # Combine stdout and stderr for analysis
        output = result.stdout + result.stderr
        
        # Count warnings and errors
        # Common patterns for GCC/MinGW and MSVC
        error_pattern = r'error[:\s]'
        warning_pattern = r'warning[:\s]'
        
        errors = len(re.findall(error_pattern, output, re.IGNORECASE))
        warnings = len(re.findall(warning_pattern, output, re.IGNORECASE))
        
        # Calculate F1: weighted by errors × 3 + warnings
        # Normalize to 0-1 range (inverse, so 0 errors/warnings = 1.0)
        # Using formula: F1 = 1 / (1 + (errors * 3 + warnings))
        penalty = errors * 3 + warnings
        F1 = 1.0 / (1.0 + penalty)
        
        logging.info(f"Compilation result: errors={errors}, warnings={warnings}, F1={F1:.4f}")
        logging.debug(f"Compiler output:\n{output}")
        
        # Check if compilation was successful (binary produced)
        source_file, output_file = parse_makefile(MAKEFILE_PATH)
        output_path = os.path.join(BUILD_DIR, output_file)
        
        if os.path.exists(output_path):
            logging.info(f"Binary produced: {output_path}")
            return True, F1, output_file, None
        else:
            logging.warning(f"Compilation failed - no binary produced")
            error_message = f"Compilation failed: {errors} errors, {warnings} warnings"
            return False, F1, None, error_message
    
    except subprocess.TimeoutExpired:
        logging.error("Compilation timed out")
        return False, 0.0, None, "Compilation timed out"
    
    except Exception as e:
        logging.error(f"Error during compilation: {e}")
        return False, 0.0, None, f"Compilation error: {str(e)}"

def run_unit_tests(binary_name):
    """
    Run unit tests and compute F2 fitness from pass rate.
    Imports and calls the unit test run() function directly.
    
    Args:
        binary_name: Name of the compiled binary
    
    Returns:
        tuple: (F2: float, error_message: str or None)
    """
    try:
        # Get absolute path to binary
        binary_path = os.path.abspath(os.path.join(BUILD_DIR, binary_name))
        
        # Dynamically import the unit test module
        spec = importlib.util.spec_from_file_location("unit_test", UNIT_TEST_PATH)
        unit_test_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(unit_test_module)
        
        # Call the run() function directly
        test_results = unit_test_module.run(binary_path)
        
        # Extract results from dict
        num_tests = test_results.get('num_tests', 0)
        num_failures = test_results.get('num_failures', 0)
        num_errors = test_results.get('num_errors', 0)
        
        # Calculate F2: pass rate
        if num_tests > 0:
            num_passed = num_tests - num_failures - num_errors
            F2 = num_passed / num_tests
        else:
            F2 = 0.0
        
        logging.info(f"Unit test results: {num_passed}/{num_tests} passed, F2={F2:.4f}")
        logging.debug(f"Test details: {test_results.get('details', {})}")
        return F2, None
    
    except Exception as e:
        logging.error(f"Error running unit tests: {e}")
        return 0.0, f"Unit test error: {str(e)}"

def submit_to_sandbox(binary_name):
    """
    Submit binary to GIMC sandbox for dynamic analysis.
    Submits sample with analyze=true.
    
    Args:
        binary_name: Name of the compiled binary
    
    Returns:
        analysis_id: int or None if submission failed
    """
    try:
        binary_path = os.path.join(BUILD_DIR, binary_name)
        
        # Read binary file
        with open(binary_path, 'rb') as f:
            binary_data = f.read()
        
        # Submit to sandbox with analyze flag and classification tag
        headers = {
            'Authorization': f'Bearer {SANDBOX_TOKEN}'
        }
        
        files = {
            'file': (binary_name, binary_data, 'application/octet-stream')
        }
        
        # Add form data for analyze flag
        data = {
            'analyze': 'true'
        }
        
        response = requests.post(
            f'{SANDBOX_URL}/submit/sample',
            headers=headers,
            files=files,
            data=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            # Extract analysis_id from response
            analysis_id = result.get('analysis_id')
            if analysis_id:
                sha256 = result.get('hashes', {}).get('sha256', 'unknown')
                logging.info(f"Successfully submitted to sandbox: analysis_id={analysis_id}, SHA256={sha256}")
                return analysis_id
            else:
                logging.error(f"No analysis_id in response: {result}")
                return None
        else:
            logging.error(f"Error submitting to sandbox: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        logging.error(f"Exception while submitting to sandbox: {e}")
        return None

###################################
# Main Build Loop
###################################

def process_build_task(candidate_hash, encoded_code):
    """
    Process a single build task: decode, compile, test, submit.
    
    Args:
        candidate_hash: Hash of the candidate
        encoded_code: Base64 encoded source code
    
    Returns:
        bool: True if VM needs reset (binary was submitted), False otherwise
    """
    try:
        # Check if Makefile exists
        if not os.path.exists(MAKEFILE_PATH):
            logging.error(f"Makefile not found at {MAKEFILE_PATH}")
            update_candidate(candidate_hash, status=4, error_message="Makefile not configured", clean=True)
            return False
        
        # Parse Makefile to get filenames
        source_file, output_file = parse_makefile(MAKEFILE_PATH)
        
        # Clean build directory
        clean_build_directory()
        
        # Save code to file
        if not save_code_to_file(encoded_code, source_file):
            update_candidate(candidate_hash, status=4, error_message="Failed to save code to file", clean=True)
            return False
        
        # Compile code
        compile_success, F1, binary_name, compile_error = compile_code()
        
        if not compile_success:
            # No binary produced - report F1, complete, and clean up
            update_candidate(
                candidate_hash,
                status=3,  # complete
                F1=F1,
                F2=0.0,
                error_message=compile_error,
                clean=True  # Signal ES that we're cleaning up
            )
            # Clean up files
            clean_build_directory()
            logging.info("Compilation failed - cleaned up and ready for next task")
            return False  # VM doesn't need reset
        
        # Binary produced - update F1 and continue
        update_candidate(candidate_hash, F1=F1)
        
        # Run unit tests
        F2, test_error = run_unit_tests(binary_name)
        update_candidate(candidate_hash, F2=F2)
        
        # Submit to sandbox for dynamic analysis
        analysis_id = submit_to_sandbox(binary_name)
        
        if analysis_id:
            # Successfully submitted - update status to analyzing
            update_candidate(
                candidate_hash,
                status=2,  # analyzing
                analysis_id=analysis_id
            )
            logging.info("Binary submitted to sandbox - VM will be reset")
        else:
            # Failed to submit - mark as complete with error, but still reset VM
            update_candidate(
                candidate_hash,
                status=3,  # complete
                error_message="Failed to submit to sandbox"
            )
            logging.info("Sandbox submission failed but binary was compiled - VM will be reset")
        
        # VM needs reset because binary was successfully compiled
        return True


    except Exception as e:
        logging.error(f"Error processing build task: {e}")
        update_candidate(
            candidate_hash,
            status=4,  # error
            error_message=f"Build error: {str(e)}",
            clean=False  # Reset VM on error
        )

        return True  # VM needs reset on error

def main():
    """Main build agent loop - processes tasks until a binary is successfully compiled"""
    logging.info("Build agent starting...")
    logging.info(f"ES API URL: {ES_API_URL}")
    logging.info(f"Sandbox URL: {SANDBOX_URL}")
    logging.info(f"Build directory: {BUILD_DIR}")
    logging.info(f"Makefile path: {MAKEFILE_PATH}")
    logging.info(f"Unit test path: {UNIT_TEST_PATH}")
    logging.info(f"Poll interval: {POLL_INTERVAL}s")
    
    # Note: Makefile and unit test file will be provided as configuration
    # The agent will check for their existence when processing each task
    
    # Poll for tasks and process them
    # Exit when a binary is successfully compiled (VM needs reset)
    # If compilation fails (no binary), clean up and continue processing more tasks
    while True:
        try:
            # Check for build task
            candidate_hash, encoded_code = check_for_build_task()
            
            if candidate_hash:
                # Process build task
                logging.info(f"Processing candidate: {candidate_hash}")
                needs_vm_reset = process_build_task(candidate_hash, encoded_code)
                logging.info(f"Finished processing candidate: {candidate_hash}")
                
                # Exit if binary was compiled (VM needs reset)
                if needs_vm_reset:
                    logging.info("Binary compiled - exiting for VM reset")
                    break
                else:
                    logging.info("Compilation failed - continuing to next task")
                    # Continue loop to fetch next task
            else:
                # No tasks available - wait before polling again
                logging.debug("No tasks available, waiting...")
                time.sleep(POLL_INTERVAL)
        
        except KeyboardInterrupt:
            logging.info("Build agent stopped by user")
            break
        
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            time.sleep(POLL_INTERVAL)

###################################
# Entry Point
###################################

if __name__ == '__main__':
    # Parse command-line arguments
    parse_args()
    
    # Run main loop
    main()

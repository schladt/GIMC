# Driver program to create prototypes using ChatGPT4 LLM from defined unit tests

import os
import subprocess
import json

def main():

    # get directory of this file
    dir_path = os.path.dirname(os.path.realpath(__file__))
    test_dir = os.path.join(dir_path, "unit_tests")

    # recursively list all files in test_dir
    files = []
    for r, d, f in os.walk(test_dir):
        for file in f:
            if file[-7:] == 'test.py':
                files.append(os.path.join(r, file))

    # run unit tests using subprocess and capture output
    for file in files:
        print("Running unit tests in {}".format(file))
        p = subprocess.Popen(['python', file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        (out, _) = p.communicate()
        
        # decode output as json
        out = json.loads(out)
        num_failures = out["num_failures"]
        num_errors = out["num_errors"]
        num_tests = out["num_tests"]

        # print output
        print("num_failures: {}".format(num_failures))
        print("num_errors: {}".format(num_errors))
        print("num_tests: {}".format(num_tests))
        
if __name__ == "__main__":
    main()
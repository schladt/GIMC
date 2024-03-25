# use unittest to test depth first file search
import unittest
import ctypes
import contextlib
import os, sys
import json
import shutil

def create_file_str():
    file_str = 'file_6.txt,file_7.txt,file_8.txt,file_33.txt,file_34.txt,file_35.txt,file_30.txt,file_31.txt,file_32.txt,file_27.txt,file_28.txt,file_29.txt,file_3.txt,file_4.txt,file_5.txt,file_24.txt,file_25.txt,file_26.txt,file_21.txt,file_22.txt,file_23.txt,file_18.txt,file_19.txt,file_20.txt,file_0.txt,file_1.txt,file_2.txt,file_15.txt,file_16.txt,file_17.txt,file_12.txt,file_13.txt,file_14.txt,file_10.txt,file_11.txt,file_9.txt'
    files = file_str.split(',')
    files.sort()
    return ','.join(files)

# GLOBAL FUNCTIONS - to be loaded on main
file_search = None
dll_name = None

class TestFileSearch(unittest.TestCase):
    def test_file_search(self):
        sorted_files_str = create_file_str()
        sorted_files_str = sorted_files_str.replace(" ", "")
        results = file_search()
        results = results.decode('utf-8')
        results = results.replace(" ", "")
        results = results.replace("\n", "")
        results = results.split(",")
        results.sort()
        results = ','.join(results)
        self.assertEqual(results, sorted_files_str)

def run_tests():
    global dll_name
    global file_search

    dll = ctypes.CDLL(dll_name)
    file_search = dll.file_search

    # modify the return type of file_search to be ctypes.c_char_p
    file_search.restype = ctypes.c_char_p

    # run unit tests silently
    with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull):
                with contextlib.redirect_stderr(devnull):
                    results = unittest.main(argv=['first-arg-is-ignored'], exit=False)
    # unittest.main(argv=['first-arg-is-ignored'], exit=False)
    return results


if __name__ == '__main__':

    # get dll name as first argument
    dll_name = sys.argv[1]
    
    # run the tests
    results = run_tests()
    num_failures = len(results.result.failures)
    num_errors = len(results.result.errors)
    num_tests = results.result.testsRun

    # print results as json. MUST BE IN THIS FORMAT FOR DRIVER TO READ
    json_obj = {
            "num_failures": num_failures,
            "num_errors": num_errors,
            "num_tests": num_tests
        }
    
    print(json.dumps(json_obj))

    # # clean up 
    # if os.path.exists('root'):
    #     shutil.rmtree('root')
# use unittest to test the divide function
import unittest
import ctypes
import sys
import contextlib, os
import json

# GLOBAL FUNCTIONS - to be loaded on main
dll = None
divide = None
multiply = None

# VARIABLES REQUIRED BY DRIVER
CODE_NAME = "div_mult_test"
LANGUAGE = "c"
PROMPT = f"""
function1 name: divide
function1 input: int a, int b
function1 output: int
function1 return: a / b
function1 additional tasks: none

function2 name: multiply
function2 input: int a, int b
function2 output: int
function2 return: a * b
function2 additional tasks: none

function3 name: main
function3 input: none
function3 output: int
function3 return: 0
function3 additional tasks: Ask the user which function to run and for inputs to that function. Then run the function. Then print the output. Then return 0.
"""


class TestDivide(unittest.TestCase):
    def test_divide_positive(self):
        ans = divide(4, 2)
        self.assertEqual(ans, 2)
        self.assertEqual(divide(4, 2), 2)
        self.assertEqual(divide(0, 1), 0)
        
        self.assertEqual(divide(1, 1), 1)
        self.assertEqual(divide(1, 2), 0)
        self.assertEqual(divide(2, 1), 2)
        self.assertEqual(divide(2, 2), 1)

    def test_divide_negative(self):
        self.assertEqual(divide(-4, 2), -2)
        self.assertEqual(divide(4, -2), -2)
        self.assertEqual(divide(-4, -2), 2)

    def test_divide_zero(self):
        self.assertRaises(Exception, divide, 1, 0)

class TestMultiply(unittest.TestCase):
    def test_multiply_positive(self):
        self.assertEqual(multiply(4, 2), 8)
        self.assertEqual(multiply(0, 1), 0)
        self.assertEqual(multiply(1, 1), 1)
        self.assertEqual(multiply(1, 2), 2)
        self.assertEqual(multiply(2, 1), 2)
        self.assertEqual(multiply(2, 2), 4)

    def test_multiply_negative(self):
        self.assertEqual(multiply(-4, 2), -8)
        self.assertEqual(multiply(4, -2), -8)
        self.assertEqual(multiply(-4, -2), 8)

    def test_multiply_zero(self):
        self.assertEqual(multiply(1, 0), 0)
        self.assertEqual(multiply(0, 0), 0)

def run_tests():
    global dll
    global divide
    global multiply

    dll = ctypes.CDLL('.\proto.dll')
    divide = dll.divide
    multiply = dll.multiply

    # run unit tests silently
    with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull):
                with contextlib.redirect_stderr(devnull):
                    results = unittest.main(exit=False)
    return results


if __name__ == '__main__':
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
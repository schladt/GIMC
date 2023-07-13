# use unittest to test the divide function
import unittest
import ctypes

import contextlib, os


dll = ctypes.CDLL('.\proto.dll')
divide = dll.divide
multiply = dll.multiply

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
    # run unit tests silently
    with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull):
                with contextlib.redirect_stderr(devnull):
                    results = unittest.main(exit=False, buffer=True)
    return results


if __name__ == '__main__':
    
    results = run_tests()
    num_failures = len(results.result.failures)
    num_errors = len(results.result.errors)

    print('Number of failures: {}'.format(num_failures))
    print('Number of errors: {}'.format(num_errors))
    print('Number of tests run: {}'.format(results.result.testsRun))
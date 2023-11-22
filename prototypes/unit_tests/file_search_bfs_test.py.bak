# use unittest to test the divide function
import unittest
import ctypes
import contextlib
import os
import json
import shutil

try:
    from unit_tests.create_test_file_tree import create_test_file_tree
except:
    from create_test_file_tree import create_test_file_tree

# GLOBAL FUNCTIONS - to be loaded on main
file_search = None

# VARIABLES REQUIRED BY DRIVER
CODE_NAME = "file_search_bfs"
LANGUAGE = "c"
PROMPT = """
Please write a C function named `file_search` that performs a breadth-first search on a directory tree, starting from a root directory named 'root'. The function should identify all files with a .txt extension using the Windows API for directory operations and return their names (excluding paths) in a comma-separated string, without any trailing commas. The function should not take any arguments.

The output should be formatted as follows:
- If there are .txt files found, return their names in a comma-separated string like this: "file1.txt,file2.txt,..."
- If no .txt files are found, return a string saying "No .txt files found."

You can assume that the root directory is hardcoded as 'root' in the code.

Here's a template to get you started:

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

// Queue structure for BFS
struct Queue {
    char** items;
    int front, rear, size;
};

// Create a new empty queue
struct Queue* createQueue(int size) {
    // Implementation goes here
}

// Enqueue an item into the queue
void enqueue(struct Queue* queue, const char* item) {
    // Implementation goes here
}

// Dequeue an item from the queue
char* dequeue(struct Queue* queue) {
    // Implementation goes here
}

// Check if a given path is a directory
int isDirectory(const char* path) {
    // Implementation goes here
}

// Perform a breadth-first search on the directory tree starting from 'root'
char* file_search() {
    const char* root = "root"; // Set your root directory here
    struct Queue* queue = createQueue(1000); // Adjust the size as needed
    char* result = NULL;

    // Enqueue the root directory
    // BFS implementation goes here

    // File search and result formatting goes here

    // Cleanup and return result
    // Implementation goes here
}

int main() {
    char* txtFiles = file_search();
    if (txtFiles != NULL) {
        printf("Text Files: %s\n", txtFiles);
        free(txtFiles);
    } else {
        printf("No .txt files found.\n");
    }

    return 0;
}

"""

# Alternate prompts:
# """
# Please write a C function named file_search that performs a breadth-first search on a directory tree, starting from a root directory named 'root'. 
# The function should identify all files with a .txt extension using the Windows API for directory operations and return their names (excluding paths)
# in a comma-separated string, without any trailing commas. For instance, the output should be formatted like file1.txt,file2.txt,....
# The function should not take any arguments. Use a queue-based approach for the BFS and do not sort the results alphabetically.
# You can assume that the root directory is hardcoded as 'root' in the code.
# Also include a main function that calls file_search and prints the output.
# """

# function1 name: file_search
# function1 input: none
# function1 output: string
# function1 return:
#     The function should perform a breadth-first search on a directory tree, 
#     starting from a root directory named 'root'.
#     It should not take any arguments (the directory name 'root' should be hard coded in the function).
#     The function should identify all files with a .txt extension. 
#     and return their names (excluding paths) in a comma-separated string, without any trailing commas. 
#     For instance, the output should be formatted like file1.txt,file2.txt,.... 
#     Use a queue-based approach for the BFS.
# function1 additional tasks: none

# function2 name: main
# function2 input: none
# function2 output: int
# function2 return: 0
# function2 additional tasks: Call file_search and print the output. Then return 0.


class TestFileSearch(unittest.TestCase):
    def test_file_search(self):
        sorted_files_str = create_test_file_tree()
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
    global file_search

    dll = ctypes.CDLL('.\proto.dll')
    file_search = dll.file_search

    # modify the return type of file_search to be ctypes.c_char_p
    file_search.restype = ctypes.c_char_p

    # run unit tests silently
    with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull):
                with contextlib.redirect_stderr(devnull):
                    results = unittest.main(exit=False)
    # results = unittest.main(exit=False)
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

    # clean up 
    if os.path.exists('root'):
        shutil.rmtree('root')
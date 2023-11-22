"""
Creates NON-random file tree for sandbox testing
"""

import os
import shutil
import random
import string

def create_test_file_tree():
    """ Create a directory structure with files in it.

    Args:
    - None

    Returns:
    - None
    """
    count = 0

    # delete root directory if it exists
    if os.path.exists('root'):
        shutil.rmtree('root')
        
    # create root directory
    os.mkdir('root')

    # create subdirectories
    for i in range(1, 4):
        os.mkdir(f'root/dir_{i}')

    # create files in each subdirectoy
    for i in range(1, 4):
        for j in range(1, 4):
            with open(f'root/dir_{i}/file_{count}.txt', 'w') as f:
                f.write(f'root/dir_{i}/file_{count}.txt')
                count += 1

    # create another level of subdirectories
    for i in range(1, 4):
        for j in range(1, 4):
            os.mkdir(f'root/dir_{i}/dir_{j}')

    # create files in each subdirectoy
    for i in range(1, 4):
        for j in range(1, 4):
            for k in range(1, 4):
                with open(f'root/dir_{i}/dir_{j}/file_{count}.txt', 'w') as f:
                    f.write(f'root/dir_{i}/dir_{j}/file_{count}.txt')
                    count += 1

if __name__ == '__main__':
    file_list = create_test_file_tree()
    print('Complete')
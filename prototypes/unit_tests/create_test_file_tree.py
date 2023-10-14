import os
import shutil
import random
import string

def create_test_file_tree():
    """ Create a directory structure with files in it.

    Args:
    - None

    Returns:
    - sorted_files_str (str): comma separated string of words with file extension .txt
    """
    count = 0
    # generate a random word of length 1 to max_length
    def generate_random_word(max_length):
        length = random.randint(1, max_length)
        return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))

    random_words = [generate_random_word(7) for _ in range(36)]

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
            with open(f'root/dir_{i}/{random_words[count]}.txt', 'w') as f:
                f.write(f'root/dir_{i}/{random_words[count]}.txt')
                count += 1

    # create another level of subdirectories
    for i in range(1, 4):
        for j in range(1, 4):
            os.mkdir(f'root/dir_{i}/dir_{j}')

    # create files in each subdirectoy
    for i in range(1, 4):
        for j in range(1, 4):
            for k in range(1, 4):
                with open(f'root/dir_{i}/dir_{j}/{random_words[count]}.txt', 'w') as f:
                    f.write(f'root/dir_{i}/dir_{j}/{random_words[count]}.txt')
                    count += 1

    # order the words alphabetically
    random_words.sort()

    # create comma separated string of words with file extension .txt
    random_words = [f'{word}.txt' for word in random_words]
    sorted_files_str = ', '.join(random_words)

    return sorted_files_str

if __name__ == '__main__':
    file_list = create_test_file_tree()
    print(file_list)
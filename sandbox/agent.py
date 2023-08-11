"""
Sandbox Agent
"""

import argparse
import logging
import os
import time

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding

import requests
from urllib.parse import urljoin

# set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

def decrypt_file(filepath, passphrase):
    """Decrypts a file encrypted using the upload_file function.
    
    Args:
    - filepath (str): Path to the encrypted file.
    - passphrase (bytes): Passphrase used for encryption.

    Returns:
    - bytes: Decrypted content of the file.
    """

    with open(filepath, 'rb') as f:
        salt = f.read(16)
        iv = f.read(16)
        encrypted_content = f.read()

    # Key derivation from passphrase
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    key = kdf.derive(passphrase)

    # Decrypt
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    unpadder = sym_padding.PKCS7(128).unpadder() # 128-bit block size for AES

    decrypted_content = decryptor.update(encrypted_content)
    decrypted_content += decryptor.finalize()

    unpadded_content = unpadder.update(decrypted_content)
    unpadded_content += unpadder.finalize()

    return unpadded_content

def main():
    parser = argparse.ArgumentParser(description='Super Simple Sandbox VM Agent')
    parser.add_argument('-s' , '--server', type=str, help='Server host address w/port example: http://192.168.1.1:1234/', required=True)
    parser.add_argument('-p' , '--passphrase', type=str, help='Passphrase to authenticate to host server', required=True)
    parser.add_argument('-t', '--timeout', type=int, help='Timeout in seconds for sample to execute', default=120)

    args = parser.parse_args()

    # check in with server until a sample is available
    passphrase = args.passphrase

    while True:
        url = urljoin(args.server, 'vm/checkin')

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {passphrase}'
        }   

        r = requests.get(url, headers=headers)
        
        # check if sample attached by looking at headera
        if 'X-Message' in r.headers and r.headers['X-Message'] == 'sample attached':
            break

        logging.error(f'Error checking in with server: {r.status_code} - {r.json()}')
        time.sleep(5)
        
    # write reponse to file
    with open('sample', 'wb') as f:
        f.write(r.content)
   
    # decrypt sample
    content = decrypt_file('sample', passphrase.encode('utf-8'))
    with open('sample', 'wb') as f:
        f.write(content)

    # execute sample
    # upload results



if __name__ == '__main__':
    main()


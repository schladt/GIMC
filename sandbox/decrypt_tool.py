import argparse
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding
import os

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
    parser = argparse.ArgumentParser(description='Decrypt a file encrypted with AES-256.')

    parser.add_argument('-p', '--passphrase', required=True, help='Passphrase used for encryption.')
    parser.add_argument('-s', '--source', required=True, help='Path to the encrypted source file.')
    parser.add_argument('-d', '--destination', required=True, help='Destination path to save the decrypted file.')

    args = parser.parse_args()

    try:
        decrypted_data = decrypt_file(args.source, args.passphrase.encode('utf-8'))
    except Exception as e:
        print(f"Error decrypting file: {e}")
        print("Make sure you are using the correct passphrase.")
        return

    with open(args.destination, 'wb') as f:
        f.write(decrypted_data)

    print(f"File decrypted and saved to {args.destination}")

if __name__ == "__main__":
    main()
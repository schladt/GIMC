#!/usr/bin/env python3
"""
Utility to encrypt/decrypt BSI files with password protection.

This script helps manage malware behavioral subset implementations (BSI) by:
- Encrypting source files into password-protected ZIP archives
- Decrypting archives to a working directory for development

Requirements:
    pip install pyzipper
"""

import argparse
import os
import sys
from pathlib import Path

try:
    import pyzipper
except ImportError:
    print("Error: pyzipper is required for encryption.", file=sys.stderr)
    print("Install it with: pip install pyzipper", file=sys.stderr)
    sys.exit(1)


def encrypt_file(input_file, output_file, password):
    """
    Encrypt a file into a password-protected ZIP archive.
    
    Args:
        input_file: Path to the file to encrypt
        output_file: Path for the output ZIP file
        password: Password for encryption
    """
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' does not exist.", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Create password-protected ZIP with AES encryption
        with pyzipper.AESZipFile(output_file, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
            zf.setpassword(password.encode('utf-8'))
            arcname = os.path.basename(input_file)
            zf.write(input_file, arcname=arcname)
        
        print(f"✓ Encrypted '{input_file}' to '{output_file}'")
        print(f"  Password: {password}")
    except Exception as e:
        print(f"Error encrypting file: {e}", file=sys.stderr)
        sys.exit(1)


def decrypt_file(input_file, output_dir, password):
    """
    Decrypt a password-protected ZIP archive.
    
    Args:
        input_file: Path to the ZIP file to decrypt
        output_dir: Directory to extract files to
        password: Password for decryption
    """
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' does not exist.", file=sys.stderr)
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        with pyzipper.AESZipFile(input_file, 'r') as zf:
            # Set password for extraction
            zf.setpassword(password.encode('utf-8'))
            
            # Extract all files
            zf.extractall(output_dir)
            
            # List extracted files
            extracted_files = zf.namelist()
            print(f"✓ Decrypted '{input_file}' to '{output_dir}/'")
            print(f"  Extracted files:")
            for fname in extracted_files:
                print(f"    - {fname}")
    except RuntimeError as e:
        if "Bad password" in str(e) or "password" in str(e).lower():
            print(f"Error: Incorrect password for '{input_file}'", file=sys.stderr)
        else:
            print(f"Error decrypting file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error decrypting file: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Encrypt or decrypt BSI files with password protection.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Encrypt a file with default password
  python encrypt_bsi.py myfile.c
  
  # Encrypt with custom output and password
  python encrypt_bsi.py myfile.c -o archive.zip -p mypassword
  
  # Decrypt to default tmp/ directory
  python encrypt_bsi.py archive.zip -d
  
  # Decrypt to custom directory
  python encrypt_bsi.py archive.zip -d --output-dir ./custom/
        """
    )
    
    parser.add_argument(
        'input_file',
        help='File to encrypt or ZIP archive to decrypt'
    )
    
    parser.add_argument(
        '-d', '--decrypt',
        action='store_true',
        help='Decrypt mode (default is encrypt)'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='Output filename for encryption (default: <input_file>.zip in current directory)'
    )
    
    parser.add_argument(
        '--output-dir',
        default='./tmp/',
        help='Output directory for decryption (default: ./tmp/)'
    )
    
    parser.add_argument(
        '-p', '--password',
        default='gimc',
        help='Password for encryption/decryption (default: gimc)'
    )
    
    args = parser.parse_args()
    
    if args.decrypt:
        # Decrypt mode
        decrypt_file(args.input_file, args.output_dir, args.password)
    else:
        # Encrypt mode
        if args.output:
            output_file = args.output
        else:
            # Default: input filename + .zip in current directory
            input_basename = os.path.basename(args.input_file)
            output_file = f"{input_basename}.zip"
        
        encrypt_file(args.input_file, output_file, args.password)


if __name__ == '__main__':
    main()

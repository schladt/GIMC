"""
Sandbox Agent
"""

import argparse
import logging
import os
import io
import time
import subprocess
import shlex

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding

import pefile
import binary2strings as b2s
from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_MODE_64
import hashlib

import requests
from urllib.parse import urljoin

from collect_procmon import collect_events

# set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

# globals
passphrase = None
args = None

def decrypt_file(file, passphrase):
    """Decrypts a file encrypted using the upload_file function.
    
    Args:
    - filepath (byets): content of encrypted file.
    - passphrase (bytes): Passphrase used for encryption.

    Returns:
    - bytes: Decrypted content of the file.
    """

    # with open(filepath, 'rb') as f:
    #     salt = f.read(16)
    #     iv = f.read(16)
    #     encrypted_content = f.read()

    salt = file[:16]
    iv = file[16:32]
    encrypted_content = file[32:]

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

def windows_file_type(file_content):
    """ Determine if a file is an EXE or DLL
    
    Args:
        file_path (bytes): Path to the file to check

    Returns:
        str: 'EXE' or 'DLL' if the file is a PE file, None otherwise
    """
    # treat file_content as a file-like object
    try:
        with io.BytesIO(file_content) as file:
            # Read the first 2 bytes to check for 'MZ' magic number
            if file.read(2) != b'MZ':
                return None

            # Move to offset 0x3C to read the PE header offset
            file.seek(0x3C)
            pe_offset = int.from_bytes(file.read(4), byteorder='little')

            # Move to the PE header offset and skip 'PE\0\0'
            file.seek(pe_offset + 4)

            # Skip the IMAGE_FILE_HEADER but leave the last 2 bytes for Characteristics
            file.seek(18, 1) 
            characteristics = int.from_bytes(file.read(2), byteorder='little')

            if characteristics & 0x2000:  # IMAGE_FILE_DLL
                return "DLL"
            else:
                return "EXE"

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return None

def detached_process(cmd):
    """Runs a command as a detached process."""
    CREATE_NEW_PROCESS_GROUP = 0x00000200  # note: could get it from subprocess
    DETACHED_PROCESS = 0x00000008          # 0x8 | 0x200 == 0x208
    subprocess.Popen(cmd, creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def get_static_analysis(filepath):
    """Performs static analysis on a file.
    
    Args:
    - filepath (str): Path to the file to analyze.
    """
    pe = pefile.PE(filepath)

    # create empty report
    static_analysis = {}

    # get all the hashes using hashlib
    hashers = {
            "md5": hashlib.md5(),
            "sha1": hashlib.sha1(),
            "sha256": hashlib.sha256(),
            "sha512": hashlib.sha512(),
            "sha224": hashlib.sha224(),
            "sha384": hashlib.sha384(),
        }

    static_analysis['hashes'] = {}
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):  # Reading in 4K chunks
            for hasher in hashers.values():
                hasher.update(chunk)

    for hash_type, hasher in hashers.items():
        static_analysis['hashes'][hash_type] = hasher.hexdigest()

    # PE seection information
    static_analysis['sections'] = []
    for section in pe.sections:
        name = section.Name.decode('utf-8').rstrip('\x00')
        static_analysis['sections'].append({
            'name': name,
            'virtual_address': hex(section.VirtualAddress),
            'virtual_size': hex(section.Misc_VirtualSize),
            'size_of_raw_data': section.SizeOfRawData
        })

    # PE imports
    static_analysis['imports'] = []
    for entry in pe.DIRECTORY_ENTRY_IMPORT:
        static_analysis['imports'].append({
            'dll': entry.dll.decode('utf-8'),
            'imports': [imported.name.decode('utf-8') for imported in entry.imports]
        })

    # PE exports
    static_analysis['exports'] = []
    if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT'):
        for exported in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            static_analysis['exports'].append({
                'name': exported.name.decode('utf-8'),
                'address': hex(pe.OPTIONAL_HEADER.ImageBase + exported.address),
                'ordinal': exported.ordinal
            })

    # PE resources
    static_analysis['resources'] = []
    if hasattr(pe, 'DIRECTORY_ENTRY_RESOURCE'):
        for resource_type in pe.DIRECTORY_ENTRY_RESOURCE.entries:
            static_analysis['resources'].append(resource_type.struct.dump_dict())

    # PE debug
    static_analysis['debug'] = []
    if hasattr(pe, 'DIRECTORY_ENTRY_DEBUG'):
        for debug in pe.DIRECTORY_ENTRY_DEBUG:
            static_analysis['debug'].append({
                'type': debug.struct.Type,
                'size_of_data': debug.struct.SizeOfData,
                'address_of_raw_data': hex(debug.struct.AddressOfRawData),
                'pointer_to_raw_data': hex(debug.struct.PointerToRawData)
            })

    # PE load configuration
    static_analysis['load_configuration'] = []
    if hasattr(pe, 'DIRECTORY_ENTRY_LOAD_CONFIG'):
        static_analysis['load_configuration'].append({
            'size': pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.Size,
            'time_date_stamp': pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.TimeDateStamp,
            'major_version': pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.MajorVersion,
            'minor_version': pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.MinorVersion,
            'global_flags_clear': pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.GlobalFlagsClear,
            'global_flags_set': pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.GlobalFlagsSet,
            'critical_section_default_timeout': pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.CriticalSectionDefaultTimeout,
            'decommit_free_block_threshold': pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.DeCommitFreeBlockThreshold,
            'decommit_total_free_threshold': pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.DeCommitTotalFreeThreshold,
            'lock_prefix_table': pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.LockPrefixTable,
            'maximum_allocation_size': pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.MaximumAllocationSize,
            'virtual_memory_threshold': pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.VirtualMemoryThreshold,
            'process_affinity_mask': pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.ProcessAffinityMask,
            'process_heap_flags': pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.ProcessHeapFlags,
            'service_pack_version': pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.ServicePackVersion,
            'reserved1': pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.Reserved1,
            'edit_list': pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.EditList,
            'security_cookie': hex(pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.SecurityCookie),
            'se_handler_table': hex(pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.SEHandlerTable),
            'se_handler_count': pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.SEHandlerCount
        })

    # PE bound import
    static_analysis['bound_imports'] = []
    if hasattr(pe, 'DIRECTORY_ENTRY_BOUND_IMPORT'):
        for bound_import in pe.DIRECTORY_ENTRY_BOUND_IMPORT:
            static_analysis['bound_imports'].append({
                'name': bound_import.name.decode('utf-8'),
                'entries': []
            })
            for entry in bound_import.entries:
                static_analysis['bound_imports'][-1]['entries'].append({
                    'name': entry.name.decode('utf-8'),
                    'address': hex(entry.address)
                })

    # header information
    raw_data = pe.dump_dict()
    file_header = raw_data['FILE_HEADER']
    dos_header = raw_data['DOS_HEADER']
    nt_headers = raw_data['NT_HEADERS']
    optional_header = raw_data['OPTIONAL_HEADER']
    flags = raw_data['Flags']

    # the following parses FILE_HEADER, DOS_HEADER, NT_HEADERS, OPTIONAL_HEADER
    static_analysis['file_header'] = {}
    for key in file_header.keys():
        value = file_header[key]
        if type(value) == dict:
            static_analysis['file_header'][key] = value['Value']
        else:
            static_analysis['file_header'][key] = value

    static_analysis['dos_header'] = {}
    for key in dos_header.keys():
        value = dos_header[key]
        if type(value) == dict:
            static_analysis['dos_header'][key] = value['Value']
        else:
            static_analysis['dos_header'][key] = value

    static_analysis['nt_headers'] = {}
    for key in nt_headers.keys():
        value = nt_headers[key]
        if type(value) == dict:
            static_analysis['nt_headers'][key] = value['Value']
        else:
            static_analysis['nt_headers'][key] = value

    static_analysis['optional_header'] = {}
    for key in optional_header.keys():
        value = optional_header[key]
        if type(value) == dict:
            static_analysis['optional_header'][key] = value['Value']
        else:
            static_analysis['optional_header'][key] = value

    static_analysis['flags'] = flags

    # get strings
    static_analysis['strings'] = {}
    with open(filepath, "rb") as i:
        data = i.read()
        for (string, str_type, span, is_interesting) in b2s.extract_all_strings(data):
            if str_type not in static_analysis['strings']:
                static_analysis['strings'][str_type] = []
            static_analysis['strings'][str_type].append(string)

    # perform disassembly for op code count
    static_analysis['opcodes'] = {}
    pe = pefile.PE(filepath)

    # Determine architecture (32-bit or 64-bit)
    if pe.FILE_HEADER.Machine == pefile.MACHINE_TYPE['IMAGE_FILE_MACHINE_I386']:
        mode = CS_MODE_32
    elif pe.FILE_HEADER.Machine == pefile.MACHINE_TYPE['IMAGE_FILE_MACHINE_AMD64']:
        mode = CS_MODE_64
    else:
        logging.error("Unsupported architecture!")
        return None

    # Initialize capstone disassembler for x86/64
    md = Cs(CS_ARCH_X86, mode)

    for section in pe.sections:
        # Check if this section has executable code
        if section.IMAGE_SCN_MEM_EXECUTE:
            code = section.get_data()
            for i in md.disasm(code, section.VirtualAddress):
                if i.mnemonic not in static_analysis['opcodes']:
                    static_analysis['opcodes'][i.mnemonic] = 0
                static_analysis['opcodes'][i.mnemonic] += 1

    return static_analysis

def main():
    global passphrase
    global args

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
        
        # check if sample attached by looking at headers
        if 'X-Message' in r.headers and r.headers['X-Message'] == 'sample attached':
            break
        
        if r.status_code != 200:
            logging.error(f'Error checking in with server: {r.status_code} - {r.json()}')
        else:
            logging.info(r.json()['message'])

        time.sleep(5)
    
    logging.info('received sample from server...')
    # decrypt sample
    content = decrypt_file(r.content, passphrase.encode('utf-8'))

    # determine if file is dll or exe and add extension
    file_type = windows_file_type(content)
    if file_type is None:
        error = 'file is not a PE file'
        report_error(error)
        return
    elif file_type == 'EXE':
        extension = '.exe'
    elif file_type == 'DLL':
        extension = '.dll'
        error = 'DLL files are not supported at this time'
        report_error(error)
        return

    # write sample to file
    sample_filename = f'testsample{extension}'
    with open(sample_filename, 'wb') as f:
        f.write(content)

    logging.info(f'saved sample to {sample_filename}')
    logging.info('performing static and analysis...')

    # perform static analysis on sample
    static_report = get_static_analysis(sample_filename)

    logging.info('static analysis complete')
    logging.info('performing dynamic analysis...')
    # turn on process monitor as detached process
    cmd = shlex.split(f'./procmon/Procmon.exe /AcceptEula /Quiet /Minimized /BackingFile procmon_report.pml /Runtime {args.timeout}')
    detached_process(cmd)

    # wait for procmon to start
    time.sleep(5)

    # execute sample as detached process
    cmd = shlex.split(f'{sample_filename}')
    detached_process(cmd)

    # wait for sample to finish executing
    time.sleep(args.timeout + 5)

    # make sure that report was generated by testing the existence of the file
    while not os.path.isfile('procmon_report.pml'):
        time.sleep(1)
    
    # save procmon report as csv and collect events
    cmd = shlex.split(f'./procmon/Procmon.exe /AcceptEula /Quiet /Minimized /OpenLog procmon_report.pml /SaveAs procmon_report.csv')
    result = subprocess.run(cmd)
    if result.returncode != 0:
        error = "failed to save procmon report as csv"
        report_error(error)
        return

    dynamic_report = collect_events(target_process_name=sample_filename, csv_file='procmon_report.csv')

    # combine static and dynamic reports
    report = {
        'static': static_report,
        'dynamic': dynamic_report
    }

    logging.info('dynamic analysis complete')
    logging.info('uploading results to server...')

    # upload results
    url = urljoin(args.server, 'vm/submit/report')
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {passphrase}'
    }   
    r = requests.post(url, headers=headers, json=report)

    if r.status_code != 200:
        logging.error(f'Error submitting results to server: {r.status_code} - {r.json()}')
    else:
        logging.info(r.json()['message'])
    
def report_error(error):
    """Reports an error to the server.
    
    Args:
    - error (str): Error message to report.
    """
    logging.error(error)
    url = urljoin(args.server, 'vm/submit/error')

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {passphrase}'
    }
    error_data = {
        'error': str(error)
    }   
    r = requests.post(url, headers=headers, json=error_data)
    if r.status_code != 200:
        logging.error(f'Error submitting error to server: {r.status_code} - {r.text}')
    else:
        logging.info(r.json()['message'])

if __name__ == '__main__':
    main()

"""
Complies all prototypes in the database 
Files are saved to {settings}/{data_path}/raw
"""

import os
import json
import logging
import sqlalchemy
import subprocess

from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Text, ForeignKey

# set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

SETTINGS_PATH = "..\\settings.json"


with open(SETTINGS_PATH, "r") as f:
    settings = json.load(f)

# open database connection using sqlalchemy
engine = sqlalchemy.create_engine(settings['sqlalchemy_database_uri'])
metadata_obj = MetaData()
conn = engine.connect()
prototypes = Table('prototypes', metadata_obj, autoload_with=engine)

# get all hashes from prototypes table
logging.info("Getting all hashes from prototypes table")
query = sqlalchemy.select(prototypes.c.hash, prototypes.c.name).where(prototypes.c.status == 3)
result = conn.execute(query)
hashes = [[row[0], row[1]] for row in result]
logging.info(f'Found {len(hashes)} hashes with successful status')

# compile each binary         
for hash in hashes:

    # get code for hash from database
    result = conn.execute(sqlalchemy.select(prototypes.c.code).where(prototypes.c.hash == hash[0]))
    code = result.fetchone()[0]

    # write code to file
    raw_dir = os.path.join(settings['data_path'], 'raw', hash[1])
    source_file = os.path.join(raw_dir, f'{hash[0]}.c')
    bin_file = os.path.join(raw_dir, f'{hash[0]}.exe')

    # create directories if they don't exist
    if not os.path.exists(raw_dir):
        os.makedirs(raw_dir)

    try:
        with open(source_file, 'w') as f:
            f.write(code)
    except Exception as e:
        logging.error(f"Error writing code to {source_file}: {e}")
        continue

    # compile code
    p = subprocess.Popen(['gcc.exe', '-o', bin_file, '-fPIC', source_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = p.communicate()
    if p.returncode != 0:
        logging.error(f"Error compiling code in {source_file}")
        out = out.decode("utf-8")
        err = err.decode("utf-8")
        logging.error(out)
        logging.error(err)
    else:
        logging.info(f"Successfully compiled code for {hash[0]}")
    
# Driver program to create prototypes using ChatGPT4 LLM from defined unit tests

import os
import re
import subprocess
import json
import importlib.util
import openai
import sqlite3
import hashlib
import logging

# set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


SETTINGS_PATH = "..\\settings.json"
DB_NAME = "prototypes.db"

def main():

    # read settings
    with open(SETTINGS_PATH, "r") as f:
        settings = json.load(f)
    
    # authenticate with openai
    logging.debug("Authenticating with OpenAI")
    openai_api_key = settings["openai_api_key"]
    openai.api_key = openai_api_key

    # setup database
    logging.debug("Setting up database")
    db_path = os.path.join(settings["data_path"], DB_NAME)
    setup_db(db_path)

    # open database connection
    db = sqlite3.connect(db_path)
    cursor = db.cursor()

    # get directory of this file
    dir_path = os.path.dirname(os.path.realpath(__file__))
    test_dir = os.path.join(dir_path, "unit_tests")

    # recursively walk all files in test_dir
    files = []
    for r, d, f in os.walk(test_dir):
        for file in f:
            if file[-7:] == 'test.py':
                files.append(os.path.join(r, file))

    # process each file
    for file in files:
        logging.info("Processing {}".format(file))

        # step 1: get the prompt and programming language from the file
        user_prompt = import_var_from_module(file, "PROMPT")
        language = import_var_from_module(file, "LANGUAGE")
        code_name = import_var_from_module(file, "CODE_NAME")

        # step 2: run the prompt through the LLM
        system_prompt = f""" 
            You are an experienced programmer. 
            Only return code in the {language} programming language. Do not any text outside of the code block.
            Please comment thoroughly comment your code.
            One or more functions along with required imports and global variables should be returned depending on the user input. 
            The function should be named with the user provided name. 
            The function should accept the user provided inputs. 
            The function should return the user provided outputs.
            The function should also perform additional user defined tasks.    
            """
        system_prompt = " ".join(system_prompt.split())
      
        logging.info("Running prompt through LLM")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            n = 5,
            messages=[
                { "role": "system", "content": system_prompt },
                {"role": "user", "content": user_prompt}
            ]
        )

        # step 3: store the returned code in the database
        for choice in response['choices']:
            
            content  = choice['message']['content']

            # look for the code block
            pattern = r'```\S*(.*?)```'
            matches = re.findall(pattern, content, re.DOTALL)
            if len(matches) > 0:
                content = matches[0].strip()

            # find the sha256 hash of the content
            hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
            
            # insert into database
            query = """ INSERT INTO prototypes (
                    hash, 
                    name, 
                    prompt, 
                    language, 
                    code, 
                    status,
                    num_errors) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(query, (hash, code_name, user_prompt, language, content, 0, 0))

            # commit changes
            db.commit()

            # step 4: write the code to a file and compile it using subprocess popen
            with open("proto.c", "w") as f:
                f.write(content)

            # compile the code            
            p = subprocess.Popen(['gcc.exe', '-shared', '-o', 'proto.dll', '-fPIC', 'proto.c'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            (out, err) = p.communicate()
            if p.returncode != 0:
                logging.error(f"Error compiling code in ")
                out = out.decode("utf-8")
                err = err.decode("utf-8")
                logging.error(out)
                logging.error(err)

                # update database with error code (1)
                query = """ UPDATE prototypes SET status = ? WHERE hash = ? """
                cursor.execute(query, (1, hash))
                db.commit()
                continue

            # step 5: run the unit tests
            logging.info("Running unit tests in {}".format(file))
            p = subprocess.Popen(['python', file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            (out, _) = p.communicate()
            
            # check for errors in subprocess, if so, log filename and continue
            if p.returncode != 0:
                logging.error(f"Error in unit test {file} - {hash}")
                logging.error(out)
                continue

            # Decode output as json
            try: 
                out = json.loads(out)
                num_failures = out["num_failures"]
                num_errors = out["num_errors"]
                num_tests = out["num_tests"]
            except:
                logging.info(f"Error decoding json in unit test {file} - {hash}")
                continue

            # log output
            logging.info("num_failures: {}".format(num_failures))
            logging.info("num_errors: {}".format(num_errors))
            logging.info("num_tests: {}".format(num_tests))

            # step 6: update the database with the number of failures and errors
            query = """ UPDATE prototypes SET num_errors = ?, status = ? WHERE hash = ? """
            cursor.execute(query, (num_errors, 2 if num_errors > 0 else 3, hash))
            db.commit()
    # close database connection
    db.close()

def setup_db(db_name = DB_NAME):
    """
    Creates the database if it does not exist
    """
    # open database connection
    db = sqlite3.connect(db_name)
    cursor = db.cursor()

    # create table if it does not exist
    query = """
        CREATE TABLE IF NOT EXISTS prototypes (
            hash TEXT,
            name TEXT,
            prompt TEXT,
            language TEXT,
            code TEXT, 
            status INT,
            num_errors INT, 
            PRIMARY KEY (hash)
        )"""
    cursor.execute(query)

    # commit changes and close connection
    db.commit()
    db.close()

def import_var_from_module(path, var):
    """
    Imports a variable from a module given the path to the module and the variable name
    """
    spec = importlib.util.spec_from_file_location("module.name", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, var, None)

if __name__ == "__main__":
    main()

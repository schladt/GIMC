"""
Script creates ingredients associated with all candidates in the database
Ingredients are stored in the ingredient table
Script does not check for duplicates but will silently ignore them
"""

# Import necessary libraries
import os
import json
import tqdm
import subprocess
import xml.etree.ElementTree as ET

from sqlalchemy import create_engine, MetaData, Table, func, Column, Integer, String, Text, ForeignKey, UniqueConstraint, exc
from sqlalchemy.orm import sessionmaker

from models import Candidate, Ingredient, Base

# Import settings
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
setting_file = os.path.join(project_root, 'settings.json')

with open(setting_file, 'r') as f:
    settings = json.load(f)

def prepare_database():
    """ 
    Connect and prepare the database
    """
    # create the engine
    engine = create_engine(settings['sqlalchemy_database_uri'])

    # Create the Table 
    Base.metadata.create_all(engine) 

def find_depth(elem, depth=0):
    """Find the depth of an element in the XML tree."""
    # Base case: if the element has no children, return the current depth
    if len(elem) == 0:
        return depth
    # Recursive case: return the maximum depth of the element's children
    else:
        return max(find_depth(child, depth + 1) for child in elem)

def main():
    # connect to database
    # create engine, connection, and session
    engine = create_engine(settings['sqlalchemy_database_uri'])
    conn = engine.connect()
    Session = sessionmaker(bind=engine)
    session = Session()

    # Reflect the tables
    metadata = MetaData()
    metadata.reflect(bind=engine)

    # Analysis = Table('analysis', metadata, autoload_with=engine)
    # Sample = Table('sample', metadata, autoload_with=engine)
    # Tag = Table('tag', metadata, autoload_with=engine)
    # SampleTag = Table('sample_tag', metadata, autoload_with=engine)
    Ingredient = Table('ingredient', metadata, autoload_with=engine)
    Candidates = Table('candidate', metadata, autoload_with=engine)

    # Get all candidates
    candidates = session.query(Candidates).all()

    # create a temporary directory to store the prototype
    tmp_dir = os.path.abspath('tmp')
    os.makedirs(tmp_dir, exist_ok=True)

    # process each candidate and show progress bar using tqdm
    for candidate in tqdm.tqdm(candidates, desc='Creating ingredients'):
        print(f"Processing candidate: {candidate.hash}")
        
        # write the candidate to a file
        candidate_source = os.path.join(tmp_dir, 'candidate.c')
        with open(candidate_source, 'w') as f:
            f.write(candidate.code)    

        # get the srcml client
        srcml_client = settings['srcml_client']

        # compile the code
        candidate_xml = os.path.join(tmp_dir, 'candidate.xml')            
        result = subprocess.run([srcml_client, candidate_source, '-o', candidate_xml], capture_output=True, text=True)

        # check if the command was successful
        if result.returncode != 0:
            print(result.stderr)
            raise Exception('Failed to run srcml client')
        else:
            print(result.stdout)

        # read the xml file
        with open(candidate_xml, 'r') as f:
            xml = f.read()

        # update the candidate with the xml
        query = Candidates.update().where(Candidates.c.hash == candidate.hash).values(xml=xml)
        conn.execute(query)

        # parse the xml file
        tree = ET.parse(candidate_xml)
        root = tree.getroot()

        # create and add ingredients to the database
        position = 0
        for elem in root.iter():
            depth = find_depth(elem)
            tag = elem.tag.split('}')[1]
            # print(f"Adding {tag} at position {position} with depth {depth} to the database for candidate {candidate.hash}.")
            query = Ingredient.insert().values(candidate=candidate.hash, tag=tag, position=position, depth=depth)
            try:
                conn.execute(query)
            except exc.IntegrityError as e:
                print(f"Failed to add {tag} at position {position} with depth {depth} to the database for candidate {candidate.hash}.")
                # conn.rollback()
            position += 1
        conn.commit()

    # close the connections
    conn.close()
    session.close()
    engine.dispose()
    print('Done')

if __name__ == '__main__':
    prepare_database()
    main()

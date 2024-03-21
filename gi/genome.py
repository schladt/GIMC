"""
Contains the chromosome class and functions for constructing a genome from an xml file
"""

import os, json

from sqlalchemy import create_engine, MetaData, Table, func, Column, Integer, String, Text, ForeignKey, UniqueConstraint, exc
from sqlalchemy.orm import sessionmaker

import xml.etree.ElementTree as ET

class Edit: 
    """
    A class representing an edit
    """
    _edit_types = ['insert', 'delete', 'replace']

    def __init__(self, edit_type: str, prototype_hash: str, prototype_position: int):
        self._edit_type = None
        self.edit_type = edit_type # must be in ['insert', 'delete', 'replace']
        self.prototype_hash = prototype_hash # hash of the prototype containing the ingredient (insert and replace)
        self.prototype_position = prototype_position # position of the ingredient in the prototype (insert and replace only)
    
    @property
    def edit_type(self):
        return self._edit_type
    
    @edit_type.setter
    def edit_type(self, value):
        if value in self._edit_types:
            self._edit_type = value
        else:
            raise ValueError(f"Edit type must be one of {self._edit_types}")

    def __str__(self):
        if self.edit_type == 'replace' or self.edit_type == 'insert':
            return f"Edit: {self.edit_type} with ingredient at position {self.prototype_position} in prototype {self.prototype_hash}"
        else:
            return f"Edit: {self.edit_type}"
        
class Chromosome:
    """
    A class representing a chromosome
    """
    def __init__(self, tag, position, prototype_hash, weight=1, parents = [], edits = []):
        self.tag = tag
        self.position = position
        self.parents = parents
        self.edits = edits
        self.prototype = prototype_hash
        self.weight = weight

    def __str__(self):
        return f"Position: {self.position}, Tag: '{self.tag}', Prototype {self.prototype}, Weight: {self.weight}, Parents: {self.parents}, Edits: {self.edits}"
    
    def add_edit(self, edit):
        self.edits.append(edit)
    

def build_genome(prototype_hash):
    """
    Build a genome from a prototype hash. Assuming that XML is stored in the database
    
    - Args:
        prototype_hash (str): The hash of the prototype to build the genome from
    
    - Returns:
        genome (list): A list of chromosomes
    """

    # Import settings
    setting_file = os.path.abspath(os.path.join('..', 'settings.json'))

    with open(setting_file, 'r') as f:
        settings = json.load(f)

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
    Prototypes = Table('prototypes', metadata, autoload_with=engine)

    # Get the prototype
    prototype = session.query(Prototypes).filter(Prototypes.c.hash == prototype_hash).first()

    # parse the xml file
    tree = ET.ElementTree(ET.fromstring(prototype.xml))
    root = tree.getroot()

    # index map keeps track of the index of each element in the xml
    idx_map = {element: idx for idx, element in enumerate(root.iter())}

    # parent map keeps track of the parent of each element in the xml
    parent_map = {c: p for p in root.iter() for c in p}

    # create a genome (list) of chromosomes
    genome = []
    position = 0
    for element in root.iter():
        
        # find the dependencies of the element
        parents = []
        current_element = element
        while current_element in parent_map:
            parents.append(idx_map[parent_map[current_element]])
            current_element = parent_map[current_element]
        tag = element.tag.split("}")[1]
        chromosome = Chromosome(tag, position, prototype_hash, parents=parents)        
        genome.append(chromosome)
        position += 1

    return genome
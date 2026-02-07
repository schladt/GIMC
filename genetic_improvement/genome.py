"""
Contains the chromosome class and functions for constructing a genome from an xml file
"""

import os
import subprocess
import shutil
import requests
import io
import json
import math
import xml.etree.ElementTree as ET
from pylibsrcml import srcMLArchive, srcMLArchiveWriteString, srcMLArchiveRead, srcMLUnit

from models import Candidate
from genetic_improvement.config import Config

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, echo=False)
Session = sessionmaker(bind=engine)

def find_depth(elem, depth=0):
    """Find the depth of an element in the XML tree."""
    # Base case: if the element has no children, return the current depth
    if len(elem) == 0:
        return depth
    # Recursive case: return the maximum depth of the element's children
    else:
        return max(find_depth(child, depth + 1) for child in elem)

def replace_element(org_tree, org_elem, donor_elem):
    """ 
    Replace an element in the original tree with an element in the donor tree.
    
    Args:
        org_tree (ElementTree): the original tree
        org_elem (Element): the element to be swapped
        donor_elem (Element): the donor element

    Returns:
        ElementTree: the original tree with the elements swapped
    """
    org_root = org_tree.getroot()

    # parent map keeps track of the parent of each element in the xml
    parent_map = {c: p for p in org_root.iter() for c in p}

    for elem in org_root.iter():
        if elem == org_elem:
            parent = parent_map[elem]
            # find the position of the element in the parent
            i = 0
            for child in parent:
                if child == elem:
                    break
                i += 1
            # remove element from original tree and insert the donor element in its place
            parent.remove(elem)
            parent.insert(i, donor_elem)
            break

    return org_tree

class Edit: 
    """
    A class representing an edit
    """
    _edit_types = ['insert', 'delete', 'replace']

    def __init__(self, edit_type: str, candidate_hash: str, candidate_position: int):
        self._edit_type = None
        self.edit_type = edit_type # must be in ['insert', 'delete', 'replace']
        self.candidate_hash = candidate_hash # hash of the candidate containing the code element (insert and replace)
        self.candidate_position = candidate_position # position of the element in the candidate (insert and replace only)
    
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
        if self.edit_type in ('replace', 'insert'):
            return f"Edit: {self.edit_type} with position {self.candidate_position} in candidate {self.candidate_hash}"
        elif self.edit_type == 'delete':
            return f"Edit: {self.edit_type}"
        
class Chromosome:
    """
    A class representing a chromosome
    """
    def __init__(self, tag, position, candidate_hash, depth, weight=1, parents = None, edits = None):
        self.tag = tag
        self.position = position
        self.parents = parents if parents is not None else []
        self.edits = edits if edits is not None else []
        self.candidate_hash = candidate_hash
        self.weight = weight
        self.depth = depth

    def __str__(self):
        if self.edits:
            edit_str = "\n\t".join([edit.__str__() for edit in self.edits])
            return f"Position: {self.position}, Tag: '{self.tag}', Candidate {self.candidate_hash}, Depth, {self.depth}, Weight: {self.weight}, Parents: {self.parents}, Edits:\n\t{edit_str}"
        else:
            return f"Position: {self.position}, Tag: '{self.tag}', Candidate {self.candidate_hash}, Depth, {self.depth}, Weight: {self.weight}, Parents: {self.parents}, Edits: None"

class Genome:
    """
    Class representing a genome
    """       

    def __init__(self, candidate_hash, build_genome=False):

        # load class variables
        self.candidate_hash = candidate_hash
        self.chromosomes = []
        self.orig_elems = None
        self.modified_tree = None
        self.fitness = 0
        self.code = None
        if build_genome:
            self.build_genome()

    def __str__(self):
        return "\n".join([chromosome.__str__() for chromosome in self.chromosomes])

    def get_candidate(self):
        """
        Get the candidate associated with this genome.

        - Returns: 
            The candidate object
        """
        candidate = None

        with Session() as session:
            candidate = session.query(Candidate).filter(Candidate.hash == self.candidate_hash).first()
        
        return candidate

    def build_genome(self):
        """
        Build a genome from self.candidate_hash
        
        - Returns:
            genome (list): A list of chromosomes
        """

        # Get the candidate
        with Session() as session:
            candidate = session.query(Candidate).filter(Candidate.hash == self.candidate_hash).first()

        # parse the xml file
        tree = ET.ElementTree(ET.fromstring(candidate.xml))
        self.modified_tree = tree # modified tree starts as the base tree
        root = tree.getroot()
        self.orig_elems = [e for e in root.iter()]

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
            depth = find_depth(element)
            chromosome = Chromosome(tag, position, self.candidate_hash, depth=depth, parents=parents)
            genome.append(chromosome)
            position += 1

        self.chromosomes = genome

    def apply_edits(self):
        """
        Apply the edits to the genome and store the modified tree in self.modified_tree
        """

        dirty_list = []
        for chromosome in self.chromosomes:
            for edit in chromosome.edits:
                if edit.edit_type == 'replace':
                    # check if in dirty list or previous edits on parents have already replaced the element
                    if (chromosome.position not in dirty_list) and (not bool(set(chromosome.parents) & set(dirty_list))):
                        # get the original and donor element
                        with Session() as session:
                            donor_candidate = session.query(Candidate).filter(Candidate.hash == edit.candidate_hash).first()
                        donor_tree = ET.ElementTree(ET.fromstring(donor_candidate.xml))
                        donor_elems = [e for e in donor_tree.getroot().iter()]
                        # replace the element
                        donor_elem = donor_elems[edit.candidate_position]
                        self.modified_tree = replace_element(self.modified_tree, self.orig_elems[chromosome.position], donor_elem)
                        dirty_list.append(chromosome.position)

                        # replace names associated with swap
                        # step 1 - find the name of the element in the original tree
                        old_name = None
                        org_elem = self.orig_elems[chromosome.position]
                        if org_elem.tag.split("}")[1] == 'name':
                            old_name = org_elem.text
                        else:
                            for child in org_elem:
                                if child.tag.split("}")[1] == 'name':
                                    old_name = child.text
                                    break
                        # step 2 - find the name of the element in the donor tree
                        new_name = None
                        if donor_elem.tag.split("}")[1] == 'name':
                            new_name = donor_elem.text
                        else:
                            for child in donor_elem:
                                if child.tag.split("}")[1] == 'name':
                                    new_name = child.text
                                    break
                        # step 3 - replace the name in all instances of the modified tree
                        if new_name:
                            for elem in self.modified_tree.getroot().iter():
                                if elem.tag.split("}")[1] == 'name' and elem.text == old_name:
                                    elem.text = new_name
    
    def to_xml(code: str, language: str) -> str:
        """
        Convert source code to srcML XML format.
        
        Args:
            code: Source code string
            language: Programming language (e.g., "C++", "C", "Java")
        
        Returns:
            XML string representation of the code
        """
        archive = srcMLArchiveWriteString()
        archive.set_language(language)
        archive.enable_solitary_unit()
        
        unit = archive.unit_create()
        unit.parse_memory(code)
        
        archive.write_unit(unit)
        xml_output = archive.close()
        
        return xml_output


    def to_code(xml: str) -> str:
        """
        Convert srcML XML back to source code.
        
        Args:
            xml: srcML XML string
            language: Programming language (e.g., "C++", "C", "Java")
        
        Returns:
            Source code string
        """
        read_archive = srcMLArchiveRead(xml, string_read_mode='source')
        unit = read_archive.read_unit()
        
        if unit:
            code = unit.get_src()
            read_archive.close()
            return code
        else:
            read_archive.close()
            raise ValueError("Failed to parse XML and extract source code")    
    
    def submit_to_evaluation(self, evaluation_server=None, sandbox=False):
        """
        Submit the genome to evaluation
        
        Args:
            language (str): the language of the code to return (default: 'c')
            srcML_path (str): the path to the srcML executable
            evaluation_server (str): the url of the evaluation server
        """
        if evaluation_server is None:
            raise ValueError("evaluation_server must be provided to submit to evaluation")
        
        if self.code is None:
            raise ValueError("Genome must have code (hint: call get_code first) to submit to evaluation")
        
        url = f"{evaluation_server}/submit"
        code_file = io.StringIO(self.code)
        files={'file': ('proto.c', code_file)}
        data={'sandbox': sandbox}
        r = requests.post(url, files=files, data={"json_data": json.dumps(data)})
        if r.status_code != 200:
            raise ValueError(f"Error submitting to evaluation server: {r.text}")
        
        return r.json()

    def calculate_fitness(self, server_response):
        """
        Calculates fitness from evaluation server response

        Args:
            server_response (dict): the response from the evaluation server

        Returns:
            float: the fitness of the genome. A value between 0 and 1. Also stores the fitness in self.fitness
        """

        # case one - server response is a compile error
        if 'compile_errors' in server_response:
            errors = server_response['compile_errors']['errors']
            warnings = server_response['compile_errors']['warnings']
            
            error_penalty = 3  # errors to be worth 3x the penalty as a warning
            warning_penalty = 1
            compile_fitness = max(0, 1 - (math.log(errors * error_penalty + warnings * warning_penalty + 1,2)/10))

        else:
            compile_fitness = 1

        # case two - unit test results
        if 'unit_test_results' in server_response:
            num_failures = server_response['unit_test_results']['num_failures']
            num_errors = server_response['unit_test_results']['num_errors']
            num_tests = server_response['unit_test_results']['num_tests']

            unit_test_fitness = max(0, 1 - (num_failures + num_errors) / num_tests)
        else:
            unit_test_fitness = 0

        # case three - sandbox classification probability
        if 'sandbox_hashes' in server_response:
            # get surrogate fitness as a placeholder for classification fitness
            num_edits = sum([len(c.edits) for c in self.chromosomes])
            edit_fitness = max(0,((6 - abs(6 - num_edits)) / 6))
        elif compile_fitness == 1:
            # get surrogate fitness as a placeholder for classification fitness
            num_edits = sum([len(c.edits) for c in self.chromosomes])
            edit_fitness = max(0,((6 - abs(6 - num_edits)) / 6))
        else:
            edit_fitness = 0
        
        # combine the fitnesses
        self.fitness = (compile_fitness + unit_test_fitness + edit_fitness) / 3
        return self.fitness


"""
Contains the chromosome class and functions for constructing a genome from an xml file
"""

import base64
import requests
import xml.etree.ElementTree as ET
from pylibsrcml import srcMLArchive, srcMLArchiveWriteString, srcMLArchiveRead, srcMLUnit
from copy import deepcopy

from genetic_improvement.ollamachat import OllamaChat
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
            if elem not in parent_map:
                org_tree._setroot(donor_elem)
                return org_tree

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
        return f'Edit Type: {self._edit_type}, Candidate: {self.candidate_hash}, Position: {self.candidate_position}'
    
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
        self.tree = None
        self.modified_tree = None
        self.fitness = 0
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

    def repair_code(self):
        """
        Repair a candidate that failed to compile using LLM assistance.
        
        This method:
        1. Loads the candidate and decodes its source/makefile
        2. Extracts build error output
        3. Calls LLM to generate a fixed version
        4. Submits the repaired code as a new child candidate
        5. Returns the new candidate hash
        
        - Returns:
            str: Hash of the newly created repaired candidate, or None if repair failed
        """
        import base64
        from genetic_improvement.ollamachat import OllamaChat
        from genetic_improvement.config import REPAIR_SYSTEM_PROMPT, REPAIR_CODE_PROMPT, UNIT_TEST_CODE, MODEL
        
        # Load candidate
        candidate = self.get_candidate()
        if not candidate:
            print(f"Error: Candidate {self.candidate_hash} not found")
            return None
        
        # Check if candidate has build errors
        if not candidate.error_message:
            print(f"Warning: Candidate {self.candidate_hash} has no error_message, nothing to repair")
            return None
        
        # Decode base64 artifacts (only source and makefile, unit_test comes from config)
        try:
            source_code = base64.b64decode(candidate.code).decode('utf-8')
            makefile_code = base64.b64decode(candidate.makefile).decode('utf-8')
        except Exception as e:
            print(f"Error decoding candidate artifacts: {e}")
            return None
        
        # Truncate error message if too long to avoid overwhelming the LLM
        error_output = candidate.error_message
        if len(error_output) > 4000:
            error_output = error_output[:2000] + "\n... [truncated] ...\n" + error_output[-2000:]
        
        # Format repair prompt using UNIT_TEST_CODE and bsi_objectives from config
        from genetic_improvement.config import UNIT_TEST_CODE as unit_test_code_import
        from genetic_improvement.config import bsi_objectives as bsi_objectives_import
        
        repair_prompt = REPAIR_CODE_PROMPT.format(
            unit_test_code=unit_test_code_import,
            source_code=source_code,
            makefile_code=makefile_code,
            error_output=error_output,
            bsi_objectives=bsi_objectives_import
        )
        
        # Call LLM to repair code
        print(f"Requesting LLM repair for candidate {self.candidate_hash[:8]}...")
        chat = OllamaChat(model=MODEL, system_prompt=REPAIR_SYSTEM_PROMPT, temperature=0.5, timeout_s=180)
        
        try:
            repair_response = chat.chat(repair_prompt, stream=False)
        except requests.exceptions.ReadTimeout:
            print(f"ERROR: LLM request timed out after 180 seconds for candidate {self.candidate_hash[:8]}")
            return None
        except requests.exceptions.ConnectionError as e:
            print(f"ERROR: Failed to connect to LLM server: {e}")
            print(f"Please ensure Ollama is running and accessible at the configured endpoint.")
            return None
        except Exception as e:
            print(f"ERROR: Unexpected error during LLM request: {type(e).__name__}: {e}")
            return None
        
        # Parse repaired code
        repaired = OllamaChat.parse_variant(repair_response)
        if not repaired:
            print(f"ERROR: Failed to parse LLM repair response")
            print(f"Response length: {len(repair_response)} chars")
            print(f"Response preview (first 800 chars):\n{repair_response[:800]}")
            print(f"Response preview (last 800 chars):\n{repair_response[-800:]}")
            return None
        
        # Resubmit as new candidate using existing submit_variants infrastructure
        repaired_variant = [{
            'code': repaired['code'],
            'makefile': repaired['makefile']
        }]
        candidate_hashes = OllamaChat.submit_variants(repaired_variant, candidate.classification)
        new_candidate_hash = candidate_hashes[0] if candidate_hashes else None
        
        if new_candidate_hash:
            print(f"Repair successful: {new_candidate_hash[:8]} (parent: {self.candidate_hash[:8]})")
        else:
            print(f"ERROR: Failed to submit repaired candidate")
        
        return new_candidate_hash

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
        if candidate.xml is None:
            code_decoded = base64.b64decode(candidate.code).decode('utf-8')
            candidate.xml = Genome.to_xml(code_decoded, None)
        
        self.tree = ET.ElementTree(ET.fromstring(candidate.xml))
        root = self.tree.getroot()
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
        
        # modified_tree starts as exact copy of the original tree
        self.modified_tree = deepcopy(self.tree)

        dirty_list = []
        for chromosome in self.chromosomes:
            for edit in chromosome.edits:
                if edit.edit_type == 'replace':
                    # check if in dirty list or previous edits on parents have already replaced the element
                    in_dirty = chromosome.position in dirty_list
                    parent_conflict = bool(set(chromosome.parents) & set(dirty_list))
                    if (not in_dirty) and (not parent_conflict):
                        # get the original and donor element
                        with Session() as session:
                            donor_candidate = session.query(Candidate).filter(Candidate.hash == edit.candidate_hash).first()
                        if donor_candidate is None:
                            continue

                        if donor_candidate.xml is None:
                            code_decoded = base64.b64decode(donor_candidate.code).decode('utf-8')
                            donor_candidate.xml = Genome.to_xml(code_decoded, None)

                        donor_tree = ET.ElementTree(ET.fromstring(donor_candidate.xml))
                        donor_elems = [e for e in donor_tree.getroot().iter()]
                        if edit.candidate_position < 0 or edit.candidate_position >= len(donor_elems):
                            continue
                        if self.orig_elems is None or chromosome.position < 0 or chromosome.position >= len(self.orig_elems):
                            continue
                        if self.modified_tree is None:
                            continue

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

        # submit the modified code to the evaluation server to get candidate hashes
        m_xml = ET.tostring(self.modified_tree.getroot(), encoding='unicode')
        m_code = Genome.to_code(m_xml)
        mutated_variant = [{
            'code': m_code,
            'makefile': self.get_candidate().makefile
        }]
        m_candidate_hashes = OllamaChat.submit_variants(mutated_variant, classification=self.get_candidate().classification)
        if m_candidate_hashes is None or len(m_candidate_hashes) == 0:
            return None
        return m_candidate_hashes[0]
    
    def to_xml(code: str, language: str) -> str:
        """
        Convert source code to srcML XML format.
        
        Args:
            code: Source code string
            language: Programming language (e.g., "C++", "C", "Java")
        
        Returns:
            XML string representation of the code
        """
        if language is None:
            language = "C++"
        
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

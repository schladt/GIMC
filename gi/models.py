
from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, UniqueConstraint, DateTime, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import sys
import os

# Add sandbox to path to import its models
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from sandbox.models import Tag, Sample

Base = declarative_base()

# Many-to-many table for candidate and tag
candidate_tag = Table('candidate_tag', Base.metadata,
    Column('candidate_hash', String, ForeignKey('candidate.hash'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tag.id'), primary_key=True)
)

# Many-to-many table for candidate and sample
candidate_sample = Table('candidate_sample', Base.metadata,
    Column('candidate_hash', String, ForeignKey('candidate.hash'), primary_key=True),
    Column('sample_sha256', String(64), ForeignKey('sample.sha256'), primary_key=True)
)

class Candidate(Base):
    __tablename__ = 'candidate'
    
    hash = Column(String, primary_key=True)  # sha256 unique identifier
    code = Column(Text)  # base64 encoded C source code
    status = Column(Integer, default=0)  # 0=pending, 1=building, 2=analyzing, 3=complete, 4=error
    F1 = Column(Float)  # Fitness 1: compile quality (warnings/errors)
    F2 = Column(Float)  # Fitness 2: unit test pass rate
    F3 = Column(Float)  # Fitness 3: ML classification score
    analysis_id = Column(Integer)  # associated GIMC sandbox Analysis.id
    date_added = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    date_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    error_message = Column(Text)
    build_vm = Column(String)  # VM name assigned to this build
    
    # Relationships
    tags = relationship('Tag', secondary=candidate_tag, backref='candidates', lazy=True)
    samples = relationship('Sample', secondary=candidate_sample, backref='candidates', lazy=True)

class Prototypes(Base):
    __tablename__ = 'prototypes'
                          
    hash = Column(String, primary_key=True)   
    name = Column(String)
    prompt  = Column(Text)
    language = Column(String)
    code = Column(Text)
    xml = Column(Text)
    status = Column(Integer)
    num_errors = Column(Integer)               

class Ingredient(Base):
    __tablename__ = 'ingredient'
    id =     Column(Integer, primary_key = True, autoincrement=True)
    prototype = Column(String, ForeignKey('prototypes.hash'), nullable=False)
    tag =  Column(String)
    position = Column(Integer)
    depth = Column(Integer)
    
    # create unique constraint
    UniqueConstraint('prototype', 'position', name='unique_ingredient') 

"""
Unified SQLAlchemy models for GIMC project
Combines models from gi and sandbox modules to enable cross-module relationships
"""
from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, UniqueConstraint, DateTime, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

Base = declarative_base()

###################################
# Many-to-Many Association Tables
###################################

# Many-to-many table for sample and tag
sample_tag = Table('sample_tag', Base.metadata,
    Column('sample_id', String(64), ForeignKey('sample.sha256'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tag.id'), primary_key=True)
)

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

###################################
# GI Models (from gi/models.py)
###################################

class Candidate(Base):
    __tablename__ = 'candidate'
    
    hash = Column(String, primary_key=True)  # sha256 unique identifier
    code = Column(Text)  # base64 encoded C source code
    xml = Column(Text)  # srcML XML representation of code
    status = Column(Integer, default=0)  # 0=pending, 1=building, 2=analyzing, 3=complete, 4=error
    F1 = Column(Float)  # Fitness 1: compile quality (warnings/errors)
    F2 = Column(Float)  # Fitness 2: unit test pass rate
    F3 = Column(Float)  # Fitness 3: ML classification score
    analysis_id = Column(Integer)  # associated GIMC sandbox Analysis.id
    date_added = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    date_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    error_message = Column(Text)
    build_vm = Column(String)  # VM name assigned to this build
    makefile = Column(Text)  # Makefile for building the candidate
    unit_test = Column(Text)  # Unit test code
    classification = Column(String(64))  # Classification or class label
    
    # Relationships
    tags = relationship('Tag', secondary=candidate_tag, backref='candidates')
    samples = relationship('Sample', secondary=candidate_sample, backref='candidates')

###################################
# Sandbox Models (from sandbox/models.py)
###################################

class User(Base):
    __tablename__ = 'user'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True)
    
class Analysis(Base):
    __tablename__ = 'analysis'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sample = Column(String(64), ForeignKey('sample.sha256'))
    report = Column(String)
    status = Column(Integer, default=0)
    date_added = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    date_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    analysis_vm = Column(String, default=None)
    error_message = Column(String, default=None)

    def __repr__(self):
        return f'<Analysis {self.id}, Report {self.report}>'
    
class Tag(Base):
    __tablename__ = 'tag'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(64), nullable=False)
    value = Column(String(64), nullable=False)
    date_added = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint('key', 'value', name='_key_value_unique'),)

    def __repr__(self):
        return f'<Tag {self.key}={self.value}>'
    
class Sample(Base):
    __tablename__ = 'sample'
    
    md5 = Column(String(32), unique=True)
    sha1 = Column(String(40), unique=True)
    sha256 = Column(String(64), unique=True, primary_key=True)
    sha224 = Column(String(56), unique=True)
    sha384 = Column(String(96), unique=True)
    sha512 = Column(String(128), unique=True)
    filepath = Column(String, unique=True)
    date_added = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    tags = relationship('Tag', secondary=sample_tag, backref='samples')

    def __repr__(self):
        return f'<Sample {self.sha256}>'

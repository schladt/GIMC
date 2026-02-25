"""
Unified SQLAlchemy models for GIMC project
Combines models from gi and sandbox modules to enable cross-module relationships
"""
from __future__ import annotations
from typing import Tuple, Optional
from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, UniqueConstraint, DateTime, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

Base = declarative_base()

###################################
# Fitness Function for Candidate evaluation
###################################

def soft_hierarchical_fitness(
    F1: float, F2: float, F3: float,
    *,
    w1: float = 0.15,   # compile quality (warnings/errors)
    w2: float = 0.25,   # unit test pass rate
    w3: float = 0.60,   # behavior/class probability
    w23: float = 0.25,  # bonus when behavior + tests align
    w13: float = 0.10,  # bonus when behavior + compile align
    w12: float = 0.05,  # bonus when compile + tests align
    normalize: bool = True
) -> float:
    """
    Single scalar fitness for F1/F2/F3 in [0,1], maximize.

    - F3 always contributes (no hard thresholds).
    - Interaction terms softly prefer candidates that are also compiling/testing well.
    - Useful when objectives are mostly hierarchical but not strictly dependent.
    """
    # clamp defensively
    F1 = 0.0 if F1 < 0 else 1.0 if F1 > 1 else F1
    F2 = 0.0 if F2 < 0 else 1.0 if F2 > 1 else F2
    F3 = 0.0 if F3 < 0 else 1.0 if F3 > 1 else F3

    base = (w1 * F1) + (w2 * F2) + (w3 * F3)

    # Soft preference for "later-stage" success without hiding early F3
    synergy = (w23 * (F2 * F3)) + (w13 * (F1 * F3)) + (w12 * (F1 * F2))

    score = base + synergy

    if not normalize:
        return score

    # Upper bound occurs at F1=F2=F3=1
    max_score = (w1 + w2 + w3) + (w23 + w13 + w12)
    return score / max_score if max_score > 0 else 0.0

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

    def get_fitness(self, **kwargs) -> Optional[float]:
        """
        Calculate fitness score using soft hierarchical fitness algorithm.
        Returns None if any of F1, F2, or F3 are None.
        
        Args:
            **kwargs: Optional parameters to pass to soft_hierarchical_fitness
                     (w1, w2, w3, w23, w13, w12, normalize)
        
        Returns:
            float: Fitness score in [0,1], or None if any fitness value is None
        """
        if self.F1 is None or self.F2 is None or self.F3 is None:
            return 0.0  # or return None to indicate fitness cannot be calculated
        return soft_hierarchical_fitness(self.F1, self.F2, self.F3, **kwargs)

    def __str__(self):
        fitness = self.get_fitness()
        fit_str = f"{fitness:.3e}" if fitness is not None else "N/A"
        F1_str = f"{self.F1:.3e}" if self.F1 is not None else "N/A"
        F2_str = f"{self.F2:.3e}" if self.F2 is not None else "N/A"
        F3_str = f"{self.F3:.3e}" if self.F3 is not None else "N/A"
        return f"Candidate ID: {self.hash}, Classification: {self.classification}, Status: {self.status}, Fitness: {fit_str}, F1: {F1_str}, F2: {F2_str}, F3: {F3_str}, Analysis ID: {self.analysis_id}, Error: {self.error_message[:100]}"

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


from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timezone
   

Base = declarative_base()

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

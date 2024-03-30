
from sqlalchemy import Column, Integer, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
   

Base = declarative_base()

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

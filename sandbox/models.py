from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

Base = declarative_base()

# Many-to-many table for sample and tag
sample_tag = Table('sample_tag', Base.metadata,
    Column('sample_id', String(64), ForeignKey('sample.sha256'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tag.id'), primary_key=True)
)

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

    tags = relationship('Tag', secondary=sample_tag, backref='samples', lazy=True)

    def __repr__(self):
        return f'<Sample {self.sha256}>'

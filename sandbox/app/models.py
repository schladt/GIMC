from app import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    
class Analysis(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sample = db.Column(db.String(64), db.ForeignKey('sample.sha256'))
    report = db.Column(db.String())
    status = db.Column(db.Integer, default=0)
    date_added = db.Column(db.DateTime, default=db.func.current_timestamp())
    date_updated = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    analysis_vm = db.Column(db.String(), default=None)
    error_message = db.Column(db.String(), default=None)

    def __repr__(self):
        return f'<Analysis {self.id}, Report {self.report}>'
    
class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(db.String(64), nullable=False)
    value = db.Column(db.String(64), nullable=False)
    date_added = db.Column(db.DateTime, default=db.func.current_timestamp())

    # create unique constraint on key and value
    __table_args__ = (db.UniqueConstraint('key', 'value', name='_key_value_unique'),)

    def __repr__(self):
        return f'<Tag {self.key}={self.value}>'
    
class Sample(db.Model):
    md5 = db.Column(db.String(32), unique=True)
    sha1 = db.Column(db.String(40), unique=True)
    sha256 = db.Column(db.String(64), unique=True, primary_key=True)
    sha224 = db.Column(db.String(56), unique=True)
    sha384 = db.Column(db.String(96), unique=True)
    sha512 = db.Column(db.String(128), unique=True)
    filepath = db.Column(db.String(), unique=True)
    date_added = db.Column(db.DateTime, default=db.func.current_timestamp())

    # relationships
    tags = db.relationship('Tag', secondary='sample_tag', backref='samples', lazy=True)

    def __repr__(self):
        return f'<Sample {self.filename}>'
    
# many-to-many table for sample and tag
sample_tag = db.Table('sample_tag',
    db.Column('sample_id', db.String(64), db.ForeignKey('sample.sha256'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)
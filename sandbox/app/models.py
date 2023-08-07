from app import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)

class Sample(db.Model):
    md5 = db.Column(db.String(32), unique=True)
    sha1 = db.Column(db.String(40), unique=True)
    sha256 = db.Column(db.String(64), unique=True, primary_key=True)
    sha224 = db.Column(db.String(56), unique=True)
    sha384 = db.Column(db.String(96), unique=True)
    sha512 = db.Column(db.String(128), unique=True)
    filepath = db.Column(db.String(), unique=True)
    date_added = db.Column(db.DateTime, default=db.func.current_timestamp())

    def __repr__(self):
        return f'<Sample {self.filename}>'
    
class Analysis(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sample = db.Column(db.String(64), db.ForeignKey('sample.sha256'))
    report = db.Column(db.String())
    status = db.Column(db.Integer, default=0)
    date_added = db.Column(db.DateTime, default=db.func.current_timestamp())
    date_updated = db.Column(db.DateTime, default=db.func.current_timestamp())

    def __repr__(self):
        return f'<Analysis {self.id}, Report {self.report}>'
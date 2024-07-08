from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config
from flask_httpauth import HTTPTokenAuth

import logging

db = SQLAlchemy()
auth = HTTPTokenAuth(scheme='Bearer')

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    app.logger.setLevel(logging.INFO)

    # create tables if needed
    with app.app_context():
        db.create_all()  # This will create the tables

    # reset status of previously running analyses
    with app.app_context():
        from app.models import Analysis
        analyses = Analysis.query.filter(Analysis.status == 1).all()
        for analysis in analyses:
            analysis.status = 0
        db.session.commit()

    return app
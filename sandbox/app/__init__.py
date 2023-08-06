from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config
from flask_httpauth import HTTPTokenAuth

db = SQLAlchemy()
auth = HTTPTokenAuth(scheme='Bearer')

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    return app
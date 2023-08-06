from flask import request, jsonify, current_app
from app.main import bp
from app import db, auth
from app.models import User

@auth.verify_token
def verify_token(token):
    return token == current_app.config['CLIENT_TOKEN']

@bp.route('/hello', methods=['POST'])
@auth.login_required
def say_hello():
    name = request.json['name']
    new_user = User(name=name)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': f'Hello, {name}!'}), 200

@bp.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify({'users': [user.name for user in users]}), 200
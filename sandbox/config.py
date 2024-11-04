
import json

# load settings from file. 
# Note: For some reason Flask doesn't like this being in the class __init__ function
settings_file = '../settings.json'
with open(settings_file) as f:
    settings = json.load(f)

class Config(object):

    SQLALCHEMY_DATABASE_URI = settings['sqlalchemy_database_uri']
    SECRET_TOKEN = settings['sandbox_token']
    DATA_PATH = settings['data_path']

    # EXAMPLE VM CONFIG
    VM_PROVIDER = 'libvirt'
    VMS = [
        {
            'name': 'win10-analysis01', 
            'ip': '10.0.10.11',
            'snapshot': 'analysis'
        },
    ]
    VM_TIMEOUT = 60

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
    VM_PROVIDER = 'vmware'
    VMS = [
        {
            'name': '/home/mike/vmware/DEV_Win10x64_02/DEV_Win10x64_02.vmx', 
            'ip': '172.16.99.128',
            'snapshot': 'analysis'
        }
    ]
    VM_TIMEOUT = 45
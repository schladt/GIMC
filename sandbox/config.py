
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
                {
            'name': 'win10-analysis02', 
            'ip': '10.0.10.12',
            'snapshot': 'analysis'
        },
                {
            'name': 'win10-analysis03', 
            'ip': '10.0.10.13',
            'snapshot': 'analysis'
        },
                {
            'name': 'win10-analysis04', 
            'ip': '10.0.10.14',
            'snapshot': 'analysis'
        },
                {
            'name': 'win10-analysis05', 
            'ip': '10.0.10.15',
            'snapshot': 'analysis'
        },
                {
            'name': 'win10-analysis06', 
            'ip': '10.0.10.16',
            'snapshot': 'analysis'
        },
                {
            'name': 'win10-analysis07', 
            'ip': '10.0.10.17',
            'snapshot': 'analysis'
        },
                {
            'name': 'win10-analysis08', 
            'ip': '10.0.10.18',
            'snapshot': 'analysis'
        },
                {
            'name': 'win10-analysis09', 
            'ip': '10.0.10.19',
            'snapshot': 'analysis'
        },
                {
            'name': 'win10-analysis10', 
            'ip': '10.0.10.20',
            'snapshot': 'analysis'
        },
                {
            'name': 'win10-analysis11', 
            'ip': '10.0.10.21',
            'snapshot': 'analysis'
        },
        {
            'name': 'win10-analysis12', 
            'ip': '10.0.10.22',
            'snapshot': 'analysis'
        },
    ]
    VM_TIMEOUT = 180
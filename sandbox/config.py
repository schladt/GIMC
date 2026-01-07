
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
        #         {
        #     'name': 'win10-dev-01', 
        #     'ip': '192.168.122.100',
        #     'snapshot': 'analysis'
        # },
        {
            'name': 'win10-analysis-01', 
            'ip': '192.168.122.101',
            'snapshot': 'analysis'
        },
        {
            'name': 'win10-analysis-02', 
            'ip': '192.168.122.102',
            'snapshot': 'analysis'
        },
        {
            'name': 'win10-analysis-03', 
            'ip': '192.168.122.103',
            'snapshot': 'analysis'
        },
        {
            'name': 'win10-analysis-04', 
            'ip': '192.168.122.104',
            'snapshot': 'analysis'
        },
        {
            'name': 'win10-analysis-05', 
            'ip': '192.168.122.105',
            'snapshot': 'analysis'
        },
        {
            'name': 'win10-analysis-06', 
            'ip': '192.168.122.106',
            'snapshot': 'analysis'
        },
        {
            'name': 'win10-analysis-07', 
            'ip': '192.168.122.107',
            'snapshot': 'analysis'
        },
        {
            'name': 'win10-analysis-08', 
            'ip': '192.168.122.108',
            'snapshot': 'analysis'
        },
        {
            'name': 'win10-analysis-09', 
            'ip': '192.168.122.109',
            'snapshot': 'analysis'
        },
        {
            'name': 'win10-analysis-10', 
            'ip': '192.168.122.110',
            'snapshot': 'analysis'
        },
        {
            'name': 'win10-analysis-11', 
            'ip': '192.168.122.111',
            'snapshot': 'analysis'
        },
        {
            'name': 'win10-analysis-12', 
            'ip': '192.168.122.112',
            'snapshot': 'analysis'
        }
    ]
    VM_TIMEOUT = 180
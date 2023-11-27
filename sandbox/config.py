
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
        },
        # {
        #     'name': '/home/mike/vmware/GISM_Win10x64_01/GISM_Win10x64_01.vmx', 
        #     'ip': '172.16.99.100',
        #     'snapshot': 'analysis'
        # },
        # {
        #     'name': '/home/mike/vmware/GISM_Win10x64_02/GISM_Win10x64_02.vmx', 
        #     'ip': '172.16.99.101',
        #     'snapshot': 'analysis'
        # },
        # {
        #     'name': '/home/mike/vmware/GISM_Win10x64_03/GISM_Win10x64_03.vmx', 
        #     'ip': '172.16.99.102',
        #     'snapshot': 'analysis'
        # },
        #         {
        #     'name': '/home/mike/vmware/GISM_Win10x64_04/GISM_Win10x64_04.vmx', 
        #     'ip': '172.16.99.103',
        #     'snapshot': 'analysis'
        # },
        #         {
        #     'name': '/home/mike/vmware/GISM_Win10x64_05/GISM_Win10x64_05.vmx', 
        #     'ip': '172.16.99.104',
        #     'snapshot': 'analysis'
        # },
        # {
        #     'name': '/home/mike/vmware/GISM_Win10x64_06/GISM_Win10x64_06.vmx', 
        #     'ip': '172.16.99.105',
        #     'snapshot': 'analysis'
        # },
        # {
        #     'name': '/home/mike/vmware/GISM_Win10x64_07/GISM_Win10x64_07.vmx', 
        #     'ip': '172.16.99.106',
        #     'snapshot': 'analysis'
        # },
        # {
        #     'name': '/home/mike/vmware/GISM_Win10x64_08/GISM_Win10x64_08.vmx', 
        #     'ip': '172.16.99.107',
        #     'snapshot': 'analysis'
        # },
        # {
        #     'name': '/home/mike/vmware/GISM_Win10x64_09/GISM_Win10x64_09.vmx', 
        #     'ip': '172.16.99.108',
        #     'snapshot': 'analysis'
        # },
        # {
        #     'name': '/home/mike/vmware/GISM_Win10x64_10/GISM_Win10x64_10.vmx', 
        #     'ip': '172.16.99.109',
        #     'snapshot': 'analysis'
        # },
        # {
        #     'name': '/home/mike/vmware/GISM_Win10x64_11/GISM_Win10x64_11.vmx', 
        #     'ip': '172.16.99.110',
        #     'snapshot': 'analysis'
        # },
        # {
        #     'name': '/home/mike/vmware/GISM_Win10x64_12/GISM_Win10x64_12.vmx', 
        #     'ip': '172.16.99.111',
        #     'snapshot': 'analysis'
        # },
    ]
    VM_TIMEOUT = 120
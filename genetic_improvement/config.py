import os, json

# Get the project root directory (parent of genetic_improvement directory)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
settings_file = os.path.join(project_root, 'settings.json')

with open(settings_file, 'r') as f:
    settings = json.load(f)

SANDBOX_TOKEN = settings['sandbox_token']
SANDBOX_URL = settings['sandbox_url']
UNIT_TEST_FILE = os.path.join('unit_tests', 'file_search_test.py')
DATA_PATH = settings['data_path']
CLASSIFIER_MODEL_PATH = os.path.join(DATA_PATH, 'classifier', 'model_data')
CLASSIFIER_PATH = os.path.join(CLASSIFIER_MODEL_PATH, 'cnn4bsi_checkpoint.pth')
TOKENIZER_PATH = os.path.join(CLASSIFIER_MODEL_PATH, 'mal_reformer')

class Config(object):
    SQLALCHEMY_DATABASE_URI = settings['sqlalchemy_database_uri']
    SECRET_TOKEN = settings['sandbox_token']
    DATA_PATH = settings['data_path']
    SANDBOX_TOKEN = settings['sandbox_token']
    SANDBOX_URL = settings['sandbox_url']
    
    # Build VM Configuration
    VM_PROVIDER = 'libvirt'
    VMS = [
        # {
        #     'name': 'win10',
        #     'ip': '192.168.122.100',
        #     'snapshot': 'build'
        # },
        {
            'name': 'win10-analysis-01',
            'ip': '192.168.122.101',
            'snapshot': 'build'
        },
        {
            'name': 'win10-analysis-02',
            'ip': '192.168.122.102',
            'snapshot': 'build'
        },
        {
            'name': 'win10-analysis-03',
            'ip': '192.168.122.103',
            'snapshot': 'build'
        },
        {
            'name': 'win10-analysis-04',
            'ip': '192.168.122.104',
            'snapshot': 'build'
        },

    ]
    VM_TIMEOUT = 60 # 1 minute timeout for VM operations

import os, json

settings_file = '../settings.json'

with open(settings_file, 'r') as f:
    settings = json.load(f)

SANDBOX_TOKEN = settings['sandbox_token']
SANDBOX_URL = settings['sandbox_url']
UNIT_TEST_FILE = os.path.join('unit_tests', 'file_search_test.py')
DATA_PATH = settings['data_path']
CLASSIFIER_MODEL_PATH = os.path.join(DATA_PATH, 'classifier', 'model_data')
CLASSIFIER_PATH = os.path.join(CLASSIFIER_MODEL_PATH, 'cnn4bsi_checkpoint.pth')
TOKENIZER_PATH = os.path.join(CLASSIFIER_MODEL_PATH, 'mal_reformer')

import os, json

settings_file = '../settings.json'

with open(settings_file, 'r') as f:
    settings = json.load(f)

SANDBOX_TOKEN = settings['sandbox_token']
SANDBOX_URL = settings['sandbox_url']
UNIT_TEST_FILE = os.path.join('unit_tests', 'file_search_test.py')

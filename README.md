# GISM - Genetically Improved Synthetic Malware

## Settings
Setting for this project should be located at `./settings.json`. This file is omitted from the public repo but should contain the following values:
``` json
{
    "openai_api_key": " {{ YOUR OPENAI API KEY}}",
    "data_path": "/path/to/your/data/",
    "sqlalchemy_database_uri": "{{ YOUR DATABASE CONNECTION STRING }}",
    "sandbox_token": "{{ YOU SECRET TOKEN }}"
}
```


## The Super Simple Sandbox

GISM includes a very stripped down malware analysis sandbox. The sandbox is much simpler than nearly all commercial or community malware sandboxes but it's very quick, easy to deploy, and highly customizable. It provides the underlying dynamic analysis for GISM's discriminator network fitness evaluation.

### sandbox controller configuration

The sandbox is controlled by a flask application running on the host machine. The primary configuration file is located at `./sandbox/config.py`. 

``` python
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
    
```

# GISM - Genetically Improved Synthetic Malware

## Code Prototypes
GISM produces code prototypes generated using a LLM which is currently GPT3.5-turbo from OpenAI. Setting for this operation is found at `prototypes/settings.json`. This file is omitted from the public repo but should contain the following values:
``` json
{
    "openai_api_key": "{{ your openai key }}",
    "data_path": "{{ path to store database }}"
}
```


## The Super Simple Sandbox

GISM includes a very stripped down malware analysis sandbox. The sandbox is much simpler than nearly all commercial or community malware sandboxes but it's very quick, easy to deploy, and highly customizable. It provides the underlying dynamic analysis for GISM's discriminator network fitness evaluation.

### sandbox controller configuration

The sandbox is controlled by a flask application running on the host machine. The primary configuration file is located at `sandbox/config.py`. This file is omitted from the public repo for security reasons but should contain the following:

``` python
class Config(object):
    SQLALCHEMY_DATABASE_URI = 'sqlite:////tmp/test.db' // change to your database
    SECRET_TOKEN = '{{ your secret token }}'
    DATA_PATH = '/shared/data/danger/'
    VM_PROVIDER = 'vmware'
    VMS = [
        {
            'name': '/home/mike/vmware/GISM_Win10x64_01/GISM_Win10x64_01.vmx',
            'ip': '192.168.1.10',
            'snapshot': 'current'
        }
    ]
    VM_TIMEOUT = 120
    
```

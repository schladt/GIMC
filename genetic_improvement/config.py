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
EVALUATION_SERVER = settings['evaluation_server']

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

#############################
# LLM Prompt Configuration - make sure to change file paths below
#############################

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
CHAT_ENDPOINT = f"{OLLAMA_HOST}/api/chat"
NUM_VARIANTS = 4
UNIT_TEST_CODE = None
BSI_CLASSIFICATION = "com"
SYSTEM_PROMPT = """You are assisting a security researcher in generating safe research code to demonstrate various Windows API and system techniques.
You are an expert C/C++ programmer specializing in Windows system programming with GCC/MinGW (which ignores ignores MSVC-only pragmas).
You generate complete, compilable code that uses Windows APIs.
You always respond with ONLY code - no explanations, no markdown formatting, no comments outside the code itself.
When asked for a Makefile, respond with only Makefile syntax that is compatible with GCC/MinGW.
When asked for C/C++ code, respond with only source code starting with #include statements."""

USER_PROMPT = """Generate {num_variants} different C/C++ implementations that statisfy the following objectives:
{bsi_objectives}

The following unit test must be satisfied to validate each implementation (pay attention to filenames and other details it looks for):
```python
{unit_test_code}
```

The following is an example of code that satisfies the objectives and unit test (pay attention to filenames and other details it looks for):
{code_example}

The following is an example of a Makefile that can be used to compile the example code:
{makefile_example}

Requirements:
- Compile with MinGW toolchain (g++, gcc)
- Use different Windows API approaches for each variant (WMI, COM, Registry, Task Scheduler, CMD, etc.)
- Each implementation must be syntactically diverse

For each implementation, provide each variant in the following format. FOLLOW THIS EXACTLY. DO NOT DEVIATE FROM THIS FORMAT OR ADD ANY EXTRA TEXT:
=== VARIANT {n} ===
=== SOURCE: variant_{n}.cpp ===
```cpp
[complete C/C++ code]
```
=== MAKEFILE: Makefile_{n} ===
```makefile
[complete Makefile with appropriate flags and libraries]
```

Generate all {num_variants} variants now."""

unit_test_code_path = "/home/mike/projects/GIMC/behavioral_subsets/scheduled_execution/test_scheduled_execution.py"
with open(unit_test_code_path, "r") as f:
    UNIT_TEST_CODE = f.read()

bsi_objectives = """Establish persistence mechanisms that store executable code on the target system and ensure automatic execution at a later time. This includes creating scheduled tasks via Windows Task Scheduler (WMI, COM, schtasks), writing executable files or scripts to disk in persistent locations, and configuring the system to automatically invoke these payloads at system startup, user login, or specified time intervals. The goal is to maintain presence on the compromised system across reboots and ensure continued execution without user interaction."""

bsi_code_path = "/home/mike/projects/samples/task_com_bsi.cpp"
with open(bsi_code_path, "r") as f:
    code_example = f.read()

makefile_path = "/home/mike/projects/GIMC/behavioral_subsets/scheduled_execution/com/Makefile"
with open(makefile_path, "r") as f:
    makefile_example = f.read()

USER_PROMPT = USER_PROMPT.format(num_variants=NUM_VARIANTS, unit_test_code=UNIT_TEST_CODE, n="{n}", bsi_objectives=bsi_objectives, code_example=code_example, makefile_example=makefile_example)
# GIMC Sandbox

## Overview

The GIMC Sandbox is a dynamic malware analysis system designed to analyze Windows PE files (executables and DLLs) using configurable virtual machine environments. The system combines static analysis, dynamic execution monitoring, and behavioral analysis to generate comprehensive reports about submitted samples. Currently optimized for libvirt on Linux hosts, the architecture is extensible to support additional hypervisor platforms.

## Architecture

### Core Components

- **Flask Web API**: RESTful API for sample submission and analysis management (sandbox_server.py)
- **VM Management**: Automated virtual machine provisioning and monitoring (utils/monitor.py)
- **Analysis Engine**: Multi-stage analysis including static and dynamic components (agent.py)
- **Data Collection**: Comprehensive system and network monitoring
- **Reporting**: Structured analysis results with multiple output formats
- **Database**: SQLAlchemy-based data persistence with automatic table creation

### Key Files

#### Web Application
- `sandbox_server.py`: Main Flask application with all routes and logic
- `models.py`: Database models using SQLAlchemy (Sample, Analysis, Tag, User)
- `config.py`: Configuration management and VM definitions (loads from settings.json)

#### Analysis Components
- `agent.py`: Main analysis agent that runs inside VMs (564 lines)
  - File decryption and type detection
  - Static PE analysis (hashes, imports, exports, sections)
  - Dynamic execution and monitoring
  - Report generation
- `collect_procmon.py`: Process Monitor event collection and parsing
- `collect_winevt.py`: Windows Event Log collection via Sysmon
- `collect_test.py`: Test harness for monitoring functionality

#### VM Management
- `utils/monitor.py`: VM lifecycle management and timeout monitoring (libvirt/VMware support)
- `utils/vm-destroy.py`: Emergency VM shutdown utility
- `utils/kvm_ext_snapshot.sh`: External snapshot management for KVM/libvirt VMs

#### Utilities
- `decrypt_tool.py`: Standalone file decryption utility
- `utils/report.py`: Analysis report viewer and management
- `resubmit.ipynb`: Jupyter notebook for bulk analysis resubmission

## API Endpoints

All API endpoints require Bearer token authentication. Include the token in the `Authorization` header:
```
Authorization: Bearer {{SECRET_TOKEN}}
```

### Analyst Endpoints

These endpoints are designed for security analysts to submit samples and request analyses.

#### 1. Submit Sample
**Endpoint**: `POST /submit/sample`  
**Access**: Analyst  
**Authentication**: Required (Bearer token)

Uploads a new malware sample to the system. The sample is automatically encrypted and stored with calculated hashes.

**Parameters**:
- `file` (multipart/form-data, required): The malware sample file to upload
- `tags` (form data, optional): Comma-separated list of key=value tags for sample categorization
  - Example: `tags=family=emotet,source=email,campaign=2024-q4`
- `analyze` (form data, optional): Set to `true` to immediately queue sample for analysis after upload

**Response**:
- **Success (200)**: Returns file hashes and confirmation message
  ```json
  {
    "message": "sample successfully uploaded",
    "hashes": {
      "md5": "5d41402abc4b2a76b9719d911017c592",
      "sha1": "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d",
      "sha256": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
      "sha224": "...",
      "sha384": "...",
      "sha512": "..."
    }
  }
  ```
  - If `analyze=true`, message changes to "analysis successfully uploaded"
- **Error (400)**: No file in request, empty filename, or tag parsing error
- **Error (401)**: Invalid or missing authentication token

**Example curl commands**:
```bash
# Simple sample upload
curl -X POST \
  -H "Authorization: Bearer {{SECRET_TOKEN}}" \
  -F "file=@malware.exe" \
  http://localhost:5000/submit/sample

# Upload with tags
curl -X POST \
  -H "Authorization: Bearer {{SECRET_TOKEN}}" \
  -F "file=@malware.exe" \
  -F "tags=family=emotet,source=email,detected=2024-12-28" \
  http://localhost:5000/submit/sample

# Upload and immediately analyze
curl -X POST \
  -H "Authorization: Bearer {{SECRET_TOKEN}}" \
  -F "file=@malware.exe" \
  -F "analyze=true" \
  http://localhost:5000/submit/sample
```

#### 2. Submit Analysis Request
**Endpoint**: `POST /submit/analysis/<hash>`  
**Access**: Analyst  
**Authentication**: Required (Bearer token)

Requests dynamic analysis of an already-uploaded sample. The hash can be any of the supported hash types (MD5, SHA1, SHA256, SHA224, SHA384, SHA512).

**URL Parameters**:
- `hash` (string, required): Sample hash in any supported format
  - MD5 (32 chars), SHA1 (40 chars), SHA256 (64 chars)
  - SHA224 (56 chars), SHA384 (96 chars), SHA512 (128 chars)

**Response**:
- **Success (200)**: Analysis task created
  ```json
  {
    "message": "analysis successfully uploaded"
  }
  ```
- **Error (400)**: Invalid hash format
- **Error (404)**: Sample not found in database
- **Error (401)**: Invalid or missing authentication token

**Example curl commands**:
```bash
# Submit using SHA256
curl -X POST \
  -H "Authorization: Bearer {{SECRET_TOKEN}}" \
  http://localhost:5000/submit/analysis/{{SAMPLE_SHA256}}

# Submit using MD5
curl -X POST \
  -H "Authorization: Bearer {{SECRET_TOKEN}}" \
  http://localhost:5000/submit/analysis/{{SAMPLE_MD5}}

# Submit using SHA1
curl -X POST \
  -H "Authorization: Bearer {{SECRET_TOKEN}}" \
  http://localhost:5000/submit/analysis/{{SAMPLE_SHA1}}
```

### Guest VM Endpoints

These endpoints are designed for automated communication between the sandbox guest VMs and the orchestration server. Guest VMs must be registered in the VMS configuration with their IP addresses.

#### 3. VM Check-in
**Endpoint**: `GET /vm/checkin`  
**Access**: Guest VM (automated)  
**Authentication**: Required (Bearer token)

Guest VMs poll this endpoint to receive new analysis tasks. The server identifies the VM by its IP address and assigns pending analysis work. If a task is available, the encrypted sample is returned as a file attachment.

**Parameters**: None (VM identified by source IP)

**Response**:
- **Success (200) - No tasks**: 
  ```json
  {
    "message": "no analysis tasks available"
  }
  ```
- **Success (200) - Task assigned**: Returns encrypted sample file with headers:
  - `X-Message`: "sample attached"
  - `X-Sample-SHA256`: SHA256 hash of the sample
  - `X-Analysis-ID`: Database ID of the analysis task
  - Body: Encrypted sample file (still encrypted, agent must decrypt)
- **Error (400)**: VM IP not registered in configuration
- **Error (404)**: Sample file not found for assigned analysis task
- **Error (401)**: Invalid or missing authentication token

**Example curl command**:
```bash
# VM checking for work (must be from registered IP)
curl -X GET \
  -H "Authorization: Bearer {{SECRET_TOKEN}}" \
  -o received_sample.bin \
  -D headers.txt \
  http://{{SERVER_IP}}:5000/vm/checkin

# Check response headers for task details
cat headers.txt | grep "X-"
```

**Notes**:
- VM must be in the VMS configuration list with matching IP address
- If analysis fails to find sample, VM is automatically reverted to snapshot
- Sample remains encrypted; guest agent must decrypt using shared secret

#### 4. Submit Analysis Report
**Endpoint**: `POST /vm/submit/report`  
**Access**: Guest VM (automated)  
**Authentication**: Required (Bearer token)

Guest VM submits the completed analysis report after dynamic execution and monitoring. The report contains all collected static and dynamic analysis data in JSON format.

**Required Headers**:
- `X-Analysis-ID` (string): The analysis task ID from check-in response
- `X-Sample-SHA256` (string): SHA256 hash of analyzed sample (verification)

**Request Body** (JSON):
```json
{
  "sample_info": {
    "sha256": "...",
    "md5": "...",
    "file_type": "PE32 executable",
    "file_size": 123456
  },
  "static_analysis": {
    "pe_info": {...},
    "imports": [...],
    "exports": [...],
    "sections": [...]
  },
  "dynamic_analysis": {
    "processes": [...],
    "file_operations": [...],
    "registry_operations": [...],
    "network_operations": [...]
  },
  "behavioral_analysis": {...},
  "timeline": [...]
}
```

**Response**:
- **Success (200)**: Report saved successfully
  ```json
  {
    "message": "report successfully uploaded"
  }
  ```
- **Error (400)**: Missing headers, analysis ID not found, hash mismatch, or no report data
- **Error (401)**: Invalid or missing authentication token

**Post-Response Actions**:
- VM is automatically reverted to clean snapshot
- Analysis status updated to complete (status=2)
- Report saved to configured data path

**Example curl command**:
```bash
# Submit completed analysis report
curl -X POST \
  -H "Authorization: Bearer {{SECRET_TOKEN}}" \
  -H "X-Analysis-ID: {{ANALYSIS_ID}}" \
  -H "X-Sample-SHA256: {{SAMPLE_SHA256}}" \
  -H "Content-Type: application/json" \
  -d @report.json \
  http://{{SERVER_IP}}:5000/vm/submit/report
```

#### 5. Submit Analysis Error
**Endpoint**: `POST /vm/submit/error`  
**Access**: Guest VM (automated)  
**Authentication**: Required (Bearer token)

Guest VM submits error information when analysis fails. This could be due to decryption failure, unsupported file type, execution timeout, or other runtime errors.

**Required Headers**:
- `X-Analysis-ID` (string): The analysis task ID from check-in response  
- `X-Sample-SHA256` (string): SHA256 hash of sample that failed (verification)

**Request Body** (JSON):
```json
{
  "error": "Detailed error message describing what went wrong"
}
```

**Response**:
- **Success (200)**: Error logged successfully
  ```json
  {
    "message": "error message successfully uploaded"
  }
  ```
- **Error (400)**: Missing headers, analysis ID not found, or hash mismatch
- **Error (401)**: Invalid or missing authentication token

**Post-Response Actions**:
- VM is automatically reverted to clean snapshot
- Analysis status updated to failed (status=3)
- Error message stored in database

**Example curl command**:
```bash
# Submit error report
curl -X POST \
  -H "Authorization: Bearer {{SECRET_TOKEN}}" \
  -H "X-Analysis-ID: {{ANALYSIS_ID}}" \
  -H "X-Sample-SHA256: {{SAMPLE_SHA256}}" \
  -H "Content-Type: application/json" \
  -d '{"error": "Failed to decrypt sample: invalid key"}' \
  http://{{SERVER_IP}}:5000/vm/submit/error
```

## System Workflow

### 1. Sample Submission (Analyst)
Analyst uploads malware sample via `/submit/sample` endpoint. System calculates hashes, encrypts file, and stores with metadata.

### 2. Analysis Request (Analyst)
Analyst requests analysis via `/submit/analysis/<hash>` endpoint. System queues analysis task with status=0 (pending).

### 3. Dynamic Analysis Process (Automated)

#### VM Check-in Loop
Guest VMs continuously poll `/vm/checkin` endpoint. When analysis task is available (status=0), server responds with encrypted sample and analysis metadata.

#### VM Preparation
- Receive encrypted sample from server
- Decrypt using shared secret (PBKDF2-derived AES key)
- Verify file integrity and type
- Configure monitoring tools (Sysmon, ProcMon)

#### Sample Execution
- Start monitoring services
- Determine file type (EXE/DLL)
- Execute in controlled environment
- Monitor for specified timeout (180s default)
- Collect all system events

#### Data Collection
- **Static Analysis**: PE headers, imports, exports, sections, resources
- **Process Monitoring**: File/registry/network operations via ProcMon
- **System Events**: Security events via Sysmon and Windows Event Log
- **Behavioral Analysis**: API calls, process creation, network connections

### 4. Report Submission (Automated)
- Guest VM consolidates all collected data into structured JSON report
- Submit via `/vm/submit/report` with analysis ID and sample hash headers
- Server validates, saves report, updates analysis status to complete (status=2)
- VM automatically reverts to clean snapshot for next analysis

### 5. Error Handling (Automated)
If analysis fails at any stage, guest VM submits error via `/vm/submit/error`:
- Common failure scenarios: decryption failure, unsupported file type, execution timeout, monitoring errors
- Server logs error message, updates analysis status to failed (status=3)
- VM automatically reverts to clean snapshot

## Analysis Status Codes

The system tracks analysis progress through status codes:
- **0 (Queued)**: Analysis created, waiting for available VM
- **1 (Running)**: VM checked in and received sample, analysis in progress
- **2 (Complete)**: Analysis finished successfully, report available
- **3 (Failed)**: Analysis encountered error, see error_message field

## Virtual Machine Configuration

### Supported Hypervisors
- **libvirt**: Primary supported platform (Linux host)
- **VMware Workstation**: Linux host support
- **Extensible**: Architecture supports additional VM providers

### VM Requirements
- **OS**: Windows 10 (analysis VMs)
- **Tools**: Sysmon, Process Monitor
- **Network**: Isolated analysis network (10.0.10.x/24)
- **Snapshots**: Clean `analysis` snapshot for reset

### VM Pool
- **Configurable**: Number of VMs defined in settings file
- **Example Configuration**: 12 Windows 10 VMs (win10-analysis01 through win10-analysis12)
- **IP Range**: Configurable network addressing (example: 10.0.10.11 - 10.0.10.22)
- **Scaling**: Automatic load balancing across available VMs

## Security Features

### Encryption
- **Algorithm**: AES-256-CBC with PBKDF2 key derivation
- **Sample Storage**: All samples encrypted at rest
- **Agent Communication**: Shared secret for decryption

### Isolation
- **Network**: Isolated analysis VLANs
- **VM**: Snapshot-based reset between analyses
- **File System**: Encrypted sample storage

### Authentication
- **API**: Bearer token authentication
- **VM Access**: Controlled agent deployment

## Dependencies

### Python Requirements (Host)
```
Flask>=2.0.0
SQLAlchemy>=1.4.0
cryptography>=41.0.0
requests>=2.31.0
```

### Windows Guest Requirements
```
pefile>=2023.2.7
cryptography>=41.0.4
binary2strings>=0.1.13
capstone>=5.0.1
requests>=2.31.0
```

### System Tools
- **Sysmon**: Advanced system monitoring
- **ProcMon**: Process and file system monitoring
- **VM Management**: libvirt/VMware tools

## Usage Examples

### Complete Analysis Workflow

#### Step 1: Upload Sample
```bash
# Upload sample and get hashes
curl -X POST \
  -H "Authorization: Bearer {{SECRET_TOKEN}}" \
  -F "file=@suspicious.exe" \
  -F "tags=source=email,family=unknown,priority=high" \
  http://{{SERVER_IP}}:5000/submit/sample

# Response:
# {
#   "message": "sample successfully uploaded",
#   "hashes": {
#     "sha256": "a1b2c3d4...",
#     "md5": "5f6g7h8i...",
#     ...
#   }
# }
```

#### Step 2: Request Analysis
```bash
# Submit for analysis using SHA256 hash
curl -X POST \
  -H "Authorization: Bearer {{SECRET_TOKEN}}" \
  http://{{SERVER_IP}}:5000/submit/analysis/{{SAMPLE_SHA256}}

# Response:
# {
#   "message": "analysis successfully uploaded"
# }
```

#### Step 3: One-Step Upload and Analyze
```bash
# Upload and immediately queue for analysis
curl -X POST \
  -H "Authorization: Bearer {{SECRET_TOKEN}}" \
  -F "file=@malware.dll" \
  -F "tags=family=emotet,campaign=2024-q4" \
  -F "analyze=true" \
  http://{{SERVER_IP}}:5000/submit/sample
```

### Guest VM Agent Usage

The analysis agent runs automatically in guest VMs. For manual testing or debugging:

#### Check for Work
```bash
# From guest VM (must be registered IP)
curl -X GET \
  -H "Authorization: Bearer {{SECRET_TOKEN}}" \
  -o sample.bin \
  -D headers.txt \
  http://{{SERVER_IP}}:5000/vm/checkin

# Extract analysis details
ANALYSIS_ID=$(grep "X-Analysis-ID:" headers.txt | cut -d' ' -f2 | tr -d '\r')
SAMPLE_HASH=$(grep "X-Sample-SHA256:" headers.txt | cut -d' ' -f2 | tr -d '\r')
```

#### Submit Successful Report
```bash
# After analysis completes
curl -X POST \
  -H "Authorization: Bearer {{SECRET_TOKEN}}" \
  -H "X-Analysis-ID: ${ANALYSIS_ID}" \
  -H "X-Sample-SHA256: ${SAMPLE_HASH}" \
  -H "Content-Type: application/json" \
  -d @/path/to/report.json \
  http://{{SERVER_IP}}:5000/vm/submit/report
```

#### Submit Error Report
```bash
# If analysis fails
curl -X POST \
  -H "Authorization: Bearer {{SECRET_TOKEN}}" \
  -H "X-Analysis-ID: ${ANALYSIS_ID}" \
  -H "X-Sample-SHA256: ${SAMPLE_HASH}" \
  -H "Content-Type: application/json" \
  -d '{"error": "Timeout: Sample did not execute within 180 seconds"}' \
  http://{{SERVER_IP}}:5000/vm/submit/error
```

### Server Management

#### Starting the Sandbox Server
```bash
# Start on all interfaces, port 5000
python sandbox_server.py 0.0.0.0 5000

# Start on localhost only
python sandbox_server.py 127.0.0.1 5000

# Custom port
python sandbox_server.py 0.0.0.0 8080
```

#### Running VM Monitor
```bash
# Monitor VMs and handle timeouts (run from sandbox directory)
python -m utils.monitor
```

#### Emergency VM Shutdown
```bash
# Force shutdown all VMs (run from sandbox directory)
python -m utils.vm-destroy
```

#### Viewing Reports
```bash
# View specific analysis report
python -m utils.report ANALYSIS_ID --report

# List all analyses
python -m utils.report --list

# View sample details
python -m utils.report SAMPLE_HASH --sample
```

## Authentication and Security

### API Authentication
All endpoints require Bearer token authentication. The token must match the `SECRET_TOKEN` configured in the Flask app (loaded from `settings.json` as `sandbox_token`).

**Setting the Token**:
1. Add to `settings.json`:
   ```json
   {
     "sandbox_token": "{{SECRET_TOKEN}}"
   }
   ```

2. Use in requests:
   ```bash
   curl -H "Authorization: Bearer {{SECRET_TOKEN}}" ...
   ```

### VM Authentication
Guest VMs are authenticated by:
1. **Bearer Token**: Same token as analyst endpoints
2. **IP Address Verification**: VM source IP must match configuration in `VMS` list

This dual authentication ensures only registered VMs can access guest endpoints.

### Token Generation Example
```bash
# Generate secure random token
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Sample Programs
- `example/example.c`: Simple Windows file creation test
- `sample/persistence.c`: Persistence mechanism test (detected as threat)

### Test Files
- `collect_test.py`: ProcMon collection testing
- `resubmit.ipynb`: Bulk analysis management

### Sysmon Configuration
- `sysmon/config.xml`: Comprehensive Sysmon rules (1017 lines)
- `sysmon/install.ps1`: Automated Sysmon deployment

## Configuration

### Database
- SQLite/PostgreSQL support via SQLAlchemy
- Plain SQLAlchemy ORM (not Flask-SQLAlchemy)
- Models: Sample, Analysis, Tag, User relationships
- Tables auto-created on server startup

### VM Settings
```python
VM_PROVIDER = 'libvirt'  # Primary: 'libvirt', also: 'vmware'
VM_TIMEOUT = 180         # Analysis timeout in seconds
VMS = [...]              # VM pool configuration (loaded from settings.json)
```

**VM Configuration Requirements**:
- Each VM must have unique name and IP address
- VM names must match hypervisor VM names exactly
- IPs must be accessible from Flask server
- Snapshot name must exist on each VM (default: `analysis`)
- VMs should be on isolated analysis network

### Network Architecture
```
┌─────────────────────┐
│  Analyst Workstation│
│   (Any Network)     │
└──────────┬──────────┘
           │
           │ HTTPS/HTTP
           │
┌──────────▼──────────┐
│  Sandbox Server     │
│  10.0.10.1:5000     │
│  (Flask API)        │
└──────────┬──────────┘
           │
           │ Isolated Analysis Network (10.0.10.0/24)
           │
    ┌──────┴──────┬──────────┬──────────┐
    │             │          │          │
┌───▼────┐  ┌────▼───┐  ┌───▼────┐  ┌──▼─────┐
│Win10-01│  │Win10-02│  │Win10-03│  │  ...   │
│.10.11  │  │.10.12  │  │.10.13  │  │        │
│(Guest) │  │(Guest) │  │(Guest) │  │        │
└────────┘  └────────┘  └────────┘  └────────┘
```

**Network Isolation Best Practices**:
- Analysis VMs should NOT have internet access (prevent C2 communication)
- Use network address translation (NAT) if internet simulation needed
- Implement firewall rules to block VM-to-VM communication
- Log all network traffic for analysis

### Settings File Structure
The `settings.json` file (referenced from `../settings.json`) should contain:
```json
{
    "sqlalchemy_database_uri": "postgresql://{{DB_USER}}:{{DB_PASSWORD}}@localhost/gimc",
    "sandbox_token": "{{SECRET_TOKEN}}", 
    "data_path": "/mnt/data/gimc/samples",
    "vm_provider": "libvirt",
    "vm_timeout": 180,
    "vms": [
        {
            "name": "win10-analysis01",
            "ip": "10.0.10.11",
            "snapshot": "analysis"
        },
        {
            "name": "win10-analysis02",
            "ip": "10.0.10.12",
            "snapshot": "analysis"
        }
    ]
}
```

**Configuration Keys**:
- `sqlalchemy_database_uri`: Database connection string (SQLite or PostgreSQL)
- `sandbox_token`: API authentication token for all endpoints
- `data_path`: Root directory for sample and report storage
- `vm_provider`: Hypervisor type (`libvirt` or `vmware`)
- `vm_timeout`: Analysis execution timeout in seconds (default: 180)
- `vms`: Array of VM configurations with name, IP, and snapshot details

### Paths
- `DATA_PATH`: Sample and report storage location
- `SECRET_TOKEN`: API authentication token

## Monitoring and Maintenance

### VM Health Checks
- Automatic snapshot reset
- Failed analysis cleanup
- Resource monitoring

### Analysis Status Tracking
- Queued (0), Running (1), Complete (2), Failed (-1)
- Error message logging
- Performance metrics

### Bulk Operations
- Mass sample resubmission
- Tag-based analysis filtering
- Report aggregation

## Security Considerations

⚠️ **Important**: This system is designed for malware analysis in controlled environments. Ensure proper network isolation and security measures when deploying.

- Use isolated analysis networks
- Implement proper access controls
- Regularly update VM snapshots
- Monitor for VM escapes or network breaches
- Encrypt all sample storage
- Limit API access with strong authentication

## Support

For issues or questions regarding the GIMC Sandbox system, refer to the main project documentation or contact the development team.
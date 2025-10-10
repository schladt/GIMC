# GIMC Sandbox

## Overview

The GIMC Sandbox is a dynamic malware analysis system designed to analyze Windows PE files (executables and DLLs) using configurable virtual machine environments. The system combines static analysis, dynamic execution monitoring, and behavioral analysis to generate comprehensive reports about submitted samples. Currently optimized for libvirt on Linux hosts, the architecture is extensible to support additional hypervisor platforms.

## Architecture

### Core Components

- **Flask Web API**: RESTful API for sample submission and analysis management
- **VM Management**: Automated virtual machine provisioning and monitoring
- **Analysis Engine**: Multi-stage analysis including static and dynamic components
- **Data Collection**: Comprehensive system and network monitoring
- **Reporting**: Structured analysis results with multiple output formats

### Key Files

#### Web Application
- `run.py`: Flask application entry point
- `app/`: Main Flask application package
  - `__init__.py`: App factory and initialization
  - `models.py`: Database models (Sample, Analysis, Tag, User)
  - `main/routes.py`: API endpoints and request handlers
- `config.py`: Configuration management and VM definitions

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
- `utils/monitor.py`: VM lifecycle management (libvirt/VMware support, extensible)
- `utils/vm-destroy.py`: Emergency VM shutdown utility
- `config.py`: VM pool configuration (references settings.json for VM definitions)

#### Utilities
- `decrypt_tool.py`: Standalone file decryption utility
- `utils/report.py`: Analysis report viewer and management
- `resubmit.ipynb`: Jupyter notebook for bulk analysis resubmission

## System Workflow

### 1. Sample Submission
```
POST /submit/sample
```
- Accepts encrypted file uploads
- Calculates multiple hash types (MD5, SHA1, SHA256, etc.)
- Stores encrypted samples with metadata
- Returns sample identification hash

### 2. Analysis Submission
```
POST /submit/analysis/<hash>
```
- Queues analysis for existing samples
- Assigns available VM from pool
- Creates analysis record with unique report path
- Returns analysis job ID

### 3. Dynamic Analysis Process

#### VM Preparation
- Reset VM to clean snapshot (`analysis`)
- Deploy analysis agent to target VM
- Configure monitoring tools (Sysmon, ProcMon)

#### Sample Execution
- Transfer encrypted sample to VM
- Decrypt using shared secret
- Determine file type (EXE/DLL)
- Execute in controlled environment
- Monitor for specified timeout (180s default)

#### Data Collection
- **Static Analysis**: PE headers, imports, exports, sections, resources
- **Process Monitoring**: File/registry/network operations via ProcMon
- **System Events**: Security events via Sysmon and Windows Event Log
- **Behavioral Analysis**: API calls, process creation, network connections

### 4. Report Generation
- Consolidate all collected data
- Generate structured JSON report
- Store in configured data path
- Update analysis status and metadata

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
Flask
SQLAlchemy
cryptography
requests
asyncio
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

### Starting the Sandbox Server
```bash
python run.py 0.0.0.0 5000
```

### Submitting a Sample
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@malware.exe" \
  http://localhost:5000/submit/sample
```

### Requesting Analysis
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:5000/submit/analysis/SHA256_HASH
```

### Viewing Reports
```bash
python -m utils.report ANALYSIS_ID --report
```

## Testing and Development

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
- Models: Sample, Analysis, Tag, User relationships

### VM Settings
```python
VM_PROVIDER = 'libvirt'  # Primary: 'libvirt', also: 'vmware'
VM_TIMEOUT = 180         # Analysis timeout in seconds
VMS = [...]              # VM pool configuration (loaded from settings.json)
```

### Settings File Structure
The `settings.json` file (referenced from `../settings.json`) should contain:
```json
{
    "sqlalchemy_database_uri": "database_connection_string",
    "sandbox_token": "api_authentication_token", 
    "data_path": "/path/to/sample/storage"
}
```

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
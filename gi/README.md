# Multi-Agent Evaluation Server with ML Classification for Genetic Improvement

## Overview

This system provides a multi-component architecture for safely evaluating GI-evolved BSI code. Code candidates are compiled and tested in isolated VM snapshots, with three fitness metrics computed: compile quality (F1), unit test pass rate (F2), and ML-classified behavior (F3). The system supports parallel evaluation across multiple build VMs.

## Current Status

### ✅ Implemented Components

1. **Evaluation Server** (`evaluation_server.py`) - Flask API on Linux host
2. **Build Agent** (`build_agent.py`) - Windows VM agent for compilation and testing
3. **Monitor** (`monitor.py`) - Linux host agent for classification and VM management
4. **Database Models** (`models.py`) - Candidate table with full schema
5. **Configuration** (`config.py`) - VM settings and database connection

### 🚧 Work In Progress

- **Genome Integration** - `genome.py` still uses old synchronous evaluation flow
- **GI Demo** - `gi_demo.ipynb` not yet updated for async evaluation
- **End-to-End Loop** - Full GI pipeline not yet operational

## Architecture Components

### 1. Evaluation Server (`evaluation_server.py`)
Flask-based API server running on Linux host. Manages candidate tracking and coordinates build agents and monitor.

**Implemented Endpoints:**
- `POST /submit` - Accepts C code (plain or base64), creates candidate record, returns hash
- `GET /vm/checkin` - Build VMs poll for pending tasks (status=0)
- `POST /vm/update` - VMs report fitness values and status updates
- `GET /info/<hash>` - Returns candidate record (optionally includes code with `?returncode=true`)
- `GET /reanalyze/<hash>` - Resets candidate to pending (status=0) for re-evaluation
- `GET /testauth` - Authentication test endpoint

**Authentication:**
- Bearer token authentication using `sandbox_token` from `settings.json`

**Database:**
- Uses PostgreSQL configured in `settings.json`
- Automatically creates tables on startup
- Candidate table tracks all submissions and fitness scores

### 2. Candidate Database Table
Tracks status and fitness scores for each submitted code candidate.

**Schema (`models.py`):**
- `hash` (sha256, primary key) - unique identifier for code
- `code` (text, base64 encoded) - submitted C source code
- `status` (integer) - 0=pending, 1=building, 2=analyzing, 3=complete, 4=error
- `F1` (float) - Fitness 1: compile quality (warnings/errors)
- `F2` (float) - Fitness 2: unit test pass rate (0 if no binary produced)
- `F3` (float) - Fitness 3: ML classification score (target class probability)
- `analysis_id` (integer, foreign key) - associated GIMC sandbox Analysis.id
- `date_added` (timestamp, timezone-aware)
- `date_updated` (timestamp, timezone-aware, auto-update)
- `error_message` (text)
- `build_vm` (string) - VM name assigned to this build

**Status Flow:**
- 0 (pending) → 1 (building) → 2 (analyzing) → 3 (complete)
- Any stage can transition to 4 (error)

### 3. Build Agent (`build_agent.py`)
Runs on Windows VMs to compile, test, and submit candidates for dynamic analysis.

**Implemented Workflow:**
1. Poll ES `/vm/checkin` endpoint for pending candidates (status=0)
2. Receive base64-encoded code via response body
3. Decode and save code to build directory
4. Compile using Makefile and compute F1 from compiler warnings/errors (weighted: errors × 3 + warnings)
5. If binary produced, run unit tests and compute F2 from pass rate (else F2=0)
6. If binary produced, submit to GIMC sandbox with classification tag (`class=<label>`)
7. Update candidate via `/vm/update` with F1, F2, analysis_id
8. Set status to 2 (analyzing) if submitted to sandbox, else 3 (complete)
9. Exit and await VM snapshot reset by ES

**Command-Line Arguments:**
- `--es-url` - Evaluation server URL (required)
- `--es-token` - Evaluation server auth token (required)
- `--sandbox-url` - GIMC sandbox URL (required)
- `--sandbox-token` - GIMC sandbox auth token (required)
- `--makefile` - Path to Makefile (required)
- `--unit-test` - Path to unit test script (required)
- `--build-dir` - Build directory path (required)
- `--class-label` - Classification label for sandbox submission (required)
- `--poll-interval` - Seconds between polls (default: 5)
- `--build-timeout` - Compilation timeout (default: 300)

### 4. Monitor Agent (`monitor.py`)
Runs on Linux host to manage build VMs and perform ML classification on completed analyses.

**Implemented Responsibilities:**

**VM Lifecycle Management:**
- Monitors candidates with status=1 (building) for timeouts
- Resets stuck VMs and marks candidates as error (status=4)
- Supports both VMware and libvirt VM providers
- Uses async VM operations from `sandbox.utils.monitor`

**Classification Pipeline:**
- Polls for candidates with status=2 (analyzing)
- Checks GIMC sandbox for completed analyses (status=2) or errors (status=3)
- Loads CNN classifier and tokenizer on startup (once)
- Preprocesses sandbox reports in-memory (no intermediate files)
- Extracts target class from analysis tags (`class=<label>`)
- Classifies report and computes F3 as probability of target class
- Updates candidate to status=3 (complete) with F3 score
- Handles analysis errors by setting F3=0 and recording error message

**Command-Line Arguments:**
- `--classifier` - Path to CNN checkpoint file (required)
- `--tokenizer` - Path to tokenizer directory (required)
- `--signatures` - Comma-separated class labels, e.g., "wmi,com,cmd,benign" (required)
- `--vocab-size` - Vocabulary size (default: 20000)
- `--embed-dim` - Embedding dimension (default: 128)
- `--num-classes` - Number of classes (default: 4)
- `--dropout` - Dropout rate (default: 0.5)
- `--poll-interval` - Seconds between polls (default: 10)

**VM Configuration (`config.py`):**
- VM provider (vmware/libvirt)
- VM list with names, IPs, and snapshot names
- VM timeout (default: 300 seconds)

## Quick Start

### Prerequisites
- PostgreSQL database (configured in `../settings.json`)
- GIMC sandbox running and accessible
- CNN classifier trained and checkpoint saved
- Tokenizer artifacts saved
- Windows VM(s) with build tools (GCC/MinGW)
- Linux host with libvirt or VMware

### 1. Start Evaluation Server
```bash
cd gi
python evaluation_server.py 0.0.0.0 5090
```

### 2. Start Monitor (on Linux host)
```bash
cd gi
python monitor.py \
  --classifier /path/to/cnn4bsi_checkpoint.pth \
  --tokenizer /path/to/mal-reformer \
  --signatures "wmi,com,cmd,benign" \
  --vocab-size 20000 \
  --embed-dim 128 \
  --num-classes 4 \
  --poll-interval 10
```

### 3. Start Build Agent(s) (on Windows VM)
```bash
python build_agent.py \
  --es-url http://192.168.122.1:5090 \
  --es-token <token> \
  --sandbox-url http://192.168.122.1:5000 \
  --sandbox-token <token> \
  --makefile C:\path\to\Makefile \
  --unit-test C:\path\to\test.py \
  --build-dir C:\build \
  --class-label wmi \
  --poll-interval 5
```

### 4. Submit Code for Evaluation
```bash
# Using curl
curl -X POST http://localhost:5090/submit \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"code": "<base64-encoded-code>"}'

# Returns: {"status": "success", "message": "Code received for evaluation"}
```

### 5. Check Candidate Status
```bash
curl -X GET http://localhost:5090/info/<hash> \
  -H "Authorization: Bearer <token>"

# Returns candidate with F1, F2, F3, status, etc.
```

## Roadmap: Near-Term Work

### Phase 1: Genome Integration (High Priority)

**Goal:** Update `genome.py` to use the new async evaluation server instead of the old synchronous flow.

1. **Update Genome submission** (`genome.py`)
   - [ ] Modify `submit_to_evaluation()` to POST code to ES `/submit` endpoint
   - [ ] Store returned hash in genome for tracking
   - [ ] Remove old synchronous evaluation logic
   
2. **Add fitness polling** (`genome.py`)
   - [ ] Implement `get_fitness()` method that polls `/info/<hash>` until complete
   - [ ] Extract F1, F2, F3 from response
   - [ ] Compute combined fitness (see normalization strategy below)
   - [ ] Handle error status (4) appropriately
   
3. **Update GI demo** (`gi_demo.ipynb`)
   - [ ] Update evaluation workflow to use async submission
   - [ ] Add fitness visualization for F1, F2, F3 separately
   - [ ] Update documentation cells
   - [ ] Test end-to-end evolution loop

### Phase 2: Testing & Validation

4. **Create integration tests** (`unit_tests/`)
   - [ ] `test_eval_api.py` - Test all ES endpoints
   - [ ] `test_candidate_flow.py` - Test full candidate lifecycle
   - [ ] `test_genome_integration.py` - Test genome submission and fitness retrieval
   
5. **Manual testing**
   - [ ] Submit known-good code and verify all three fitness scores
   - [ ] Submit code with compile errors and verify F1 calculation
   - [ ] Submit code that fails unit tests and verify F2=0
   - [ ] Test VM timeout and recovery
   - [ ] Test parallel processing with multiple build VMs

### Phase 3: Documentation & Deployment

6. **Operational documentation**
   - [ ] Create deployment guide for all components
   - [ ] Document VM setup and snapshot creation
   - [ ] Add troubleshooting guide
   - [ ] Document monitoring and logging practices
   
7. **VM setup automation**
   - [ ] Create Windows VM setup script for build agent
   - [ ] Document network configuration requirements
   - [ ] Create systemd service files for server and monitor

### Phase 4: Optimization & Scaling

8. **Performance improvements**
   - [ ] Measure candidate throughput
   - [ ] Profile bottlenecks (likely classification)
   - [ ] Consider batch classification for multiple candidates
   - [ ] Add metrics/monitoring endpoints
   
9. **Scaling support**
   - [ ] Test with 5+ build VMs
   - [ ] Document how to add new VMs
   - [ ] Add health check endpoints for monitoring

## Design Decisions

### Fitness Normalization Strategy

**Options under consideration:**
- **Simple multiplication:** `fitness = F1 × F2 × F3`
  - Pros: Simple, treats all objectives equally
  - Cons: Creates optimization cliffs (any zero = total zero)

- **Weighted sum:** `fitness = w1×F1 + w2×F2 + w3×F3`
  - Pros: More gradual, configurable priorities
  - Cons: Requires tuning weights, can optimize wrong objective

- **Staged filtering:** Must pass threshold before next stage
  - Pros: Ensures minimum quality at each stage
  - Cons: May discard interesting candidates too early

- **Pareto ranking:** Multi-objective optimization
  - Pros: No weight tuning, preserves diversity
  - Cons: More complex, may slow convergence

**Current approach:** Staged filtering is built into the pipeline (no F2 without compile, no F3 without binary submission). Final fitness combination will be implemented in `genome.py` during integration phase. Recommended starting point: weighted product `fitness = F1^w1 × F2^w2 × F3^w3` with configurable weights.

### Architecture: Single-File vs. Flask App Structure

**Decision:** Single-file server (`evaluation_server.py`) instead of `gi/app/` structure.

**Rationale:**
- Simpler deployment and maintenance
- All ES logic in one place (~200 lines)
- Fewer imports and module dependencies
- Easier to understand for future modifications
- Database models separated into `models.py` for clarity

## Implementation Status

### ✅ Completed

- [x] ES API accepts code submissions and returns hashes
- [x] Build agent compiles code in VM and reports F1
- [x] Build agent runs unit tests and reports F2
- [x] Build agent submits binaries to GIMC sandbox
- [x] Monitor detects completed analyses and computes F3
- [x] Monitor successfully resets VMs after builds and timeouts
- [x] Classifier produces probabilities for sandbox reports
- [x] System handles errors gracefully (timeouts, crashes, bad code)
- [x] Multiple VMs can process candidates in parallel
- [x] Database models with timezone-aware timestamps
- [x] Authentication via Bearer token

### 🚧 In Progress / Not Started

- [ ] Genome class updated to use async evaluation
- [ ] Full GI loop operational end-to-end
- [ ] GI demo notebook updated
- [ ] Integration tests created
- [ ] VM setup automation scripts
- [ ] Operational documentation complete
- [ ] Performance benchmarking

## Configuration

### `settings.json` (project root)
```json
{
  "sqlalchemy_database_uri": "postgresql://user:pass@localhost/gimc",
  "sandbox_token": "your_token_here",
  "sandbox_url": "http://192.168.122.1:5000",
  "data_path": "/mnt/data/gimc",
  "evaluation_server": "http://127.0.0.1:5090"
}
```

### `config.py` (gi folder)
Contains `Config` class with:
- `SQLALCHEMY_DATABASE_URI` - Database connection
- `SECRET_TOKEN` - Authentication token
- `SANDBOX_TOKEN` and `SANDBOX_URL` - For build agent
- `VM_PROVIDER` - 'vmware' or 'libvirt'
- `VMS` - List of build VM configurations (name, IP, snapshot)
- `VM_TIMEOUT` - Build timeout in seconds (default: 300)

Example VM configuration:
```python
VMS = [
    {
        'name': 'win10-build-01',
        'ip': '192.168.122.201',
        'snapshot': 'build'
    },
    {
        'name': 'win10-build-02',
        'ip': '192.168.122.202',
        'snapshot': 'build'
    },
]
```

## Troubleshooting

### Build agent can't connect to ES
- Verify ES is running on correct host/port
- Check firewall rules allow connections from VM network
- Verify token matches `settings.json`

### Monitor can't classify reports
- Check classifier and tokenizer paths are correct
- Verify signatures list matches training data
- Ensure CUDA/GPU available or CPU fallback works

### VMs not resetting
- Check VM provider (vmware/libvirt) matches config
- Verify snapshot names exist on VMs
- Check VM management permissions (libvirt group, sudo, etc.)

### Classification takes too long
- Use GPU if available (monitor will detect automatically)
- Reduce `max_sequence_length` if reports are truncated anyway
- Consider batch processing multiple candidates (future work)

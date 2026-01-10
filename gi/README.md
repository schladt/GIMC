# WORK IN PROGRESS - Plan: Multi-Agent Sandboxed Evaluation Server with ML Classification

## Overview

This plan redesigns the evaluation server using a multi-component architecture similar to the GIMC simple sandbox. The new system will safely compile and test potentially malicious GI-evolved BSI code by isolating each build in a VM snapshot, computing three fitness metrics (compile quality, unit tests, and ML-classified behavior), and supporting parallel evaluation of multiple candidates.

## Architecture Components

### 1. ES API Server (Flask on Linux Host)
Central orchestrator that manages candidate tracking and coordinates all other components.

**Endpoints:**
- `POST /submit` - Accepts C code, creates candidate record, returns hash
- `POST /update` - Receives fitness/status updates from build agents and monitor
- `GET /info/<hash>` - Returns candidate record for given hash
- `POST /reset/<vm_id>` - Triggers VM snapshot revert

### 2. Candidates Database Table
Tracks status and fitness scores for each submitted code candidate.

**Schema:**
- `hash` (sha256, primary key) - unique identifier for code
- `code` (text, base64 encoded) - submitted C source code
- `status` (integer) - 0=pending, 1=building, 2=analyzing, 3=complete, 4=error
- `F1` (float) - Fitness 1: compile quality (warnings/errors)
- `F2` (float) - Fitness 2: unit test pass rate (0 if no binary produced)
- `F3` (float) - Fitness 3: ML classification score (target class probability)
- `analysis_id` (integer, foreign key) - associated GIMC sandbox Analysis.id
- `date_added` (timestamp)
- `date_updated` (timestamp, auto-update)
- `error_message` (text)
- `build_vm` (string) - VM name assigned to this build

### 3. Build Agent (Windows VM)
Runs on sandboxed VMs to compile, test, and submit candidates for dynamic analysis.

**Workflow:**
1. Poll ES API `/checkin` endpoint for pending candidates (status=0)
2. Receive code and decode from base64
3. Compile using provided Makefile and compute F1 from compiler warnings/errors (weighted: errors × 3 + warnings)
4. If binary produced, run unit tests and compute F2 from pass rate (else F2=0)
5. If binary produced, submit to GIMC simple sandbox for dynamic analysis
6. Report back via `/update` with hash, F1, F2, analysis_id (updates status to 2=analyzing if binary submitted, else 3=complete)
7. Await VM snapshot reset from ES API

**Configuration:**
- ES API URL
- GIMC sandbox URL and auth token
- Makefile path
- Unit test script path
- Poll interval (default: 5 seconds)
- Timeout (default: 300 seconds)

### 4. Monitor Agent (Linux Host)
Manages build VM lifecycle and performs ML classification on completed sandbox analyses.

**Responsibilities:**
- **VM Lifecycle Management:**
  - Monitor candidates with status=1 (building) for timeouts
  - Reset stuck VMs and mark candidates as error (status=4)
  - Track VM availability and health

- **Classification Pipeline:**
  - Poll ES API for candidates with status=2 (submitted to sandbox)
  - Check GIMC sandbox for completed analyses
  - Load trained CNN classifier and tokenizer
  - Classify sandbox report (dynamic analysis features)
  - Compute F3 as probability of target class (from config)
  - Update candidate via `/update` to status=3 (complete)

**Configuration:**
- ES API URL
- GIMC sandbox URL and auth token
- VM provider (vmware/libvirt)
- VM configurations (name, snapshot, IP)
- VM timeout (default: 300 seconds)
- Classifier model path
- Tokenizer path
- Target class label

## Implementation Roadmap

### Phase 1: Core Infrastructure

1. **Create ES API Flask application** (`gi/app/`)
   - Set up Flask app with SQLAlchemy
   - Implement database models in `gi/app/models.py` (Candidate table)
   - Create main routes in `gi/app/main/routes.py`
   - Add authentication (Bearer token like sandbox)
   - Implement `/submit`, `/update`, `/info`, `/reset` endpoints
   - Add startup logic to reset any status=1 to pending (crash recovery)

2. **Design database schema and migrations**
   - Define Candidate model with all required fields
   - Create initialization script to set up tables
   - Add database connection configuration to `gi/config.py`
   - Document schema in README

3. **Create build agent** (`gi/build_agent.py`)
   - Implement polling loop for pending candidates
   - Add compilation logic with configurable Makefile
   - Add F1 calculation from compiler output (regex parsing)
   - Implement unit test execution and F2 calculation
   - Add GIMC sandbox submission logic
   - Implement update reporting to ES API
   - Add error handling and timeout management
   - Require admin privileges for Windows VM execution

4. **Create monitor agent** (`gi/eval_monitor.py`)
   - Implement VM management functions (reset, start, stop)
   - Add timeout monitoring for stuck builds
   - Create polling loop for status=3 candidates
   - Integrate with GIMC sandbox API to check analysis completion
   - Implement ML classification pipeline
   - Add F3 calculation and reporting

### Phase 2: ML Integration

5. **Create classification utility** (`gi/classify.py`)
   - Load CNN model from saved checkpoint
   - Load tokenizer from saved artifacts
   - Implement preprocessing for sandbox reports
   - Add inference function that returns class probabilities
   - Ensure can run without GPU (CPU fallback)
   - Add logging and error handling
   - Document expected input format

6. **Integrate classifier into monitor**
   - Load model/tokenizer on monitor startup (avoid reloading)
   - Fetch sandbox reports from GIMC sandbox
   - Extract relevant features for classification
   - Pass features through classification pipeline
   - Extract target class probability for F3
   - Handle classification errors gracefully

### Phase 3: Genome Integration

7. **Update Genome class** (`gi/genome.py`)
   - Modify `submit_to_evaluation()` to:
     - POST code to new ES API `/submit` endpoint
     - Return hash immediately (non-blocking)
     - Remove old synchronous evaluation logic
   
   - Add new `get_fitness()` method to:
     - Poll `/info/<hash>` endpoint until status=4 or 5
     - Extract F1, F2, F3 from response
     - Compute combined fitness (discuss normalization strategy)
     - Handle errors (status=5)
   
   - Remove placeholder `edit_fitness` calculation from `calculate_fitness()`
   - Update method signatures and documentation

8. **Update GI demo notebook** (`gi/gi_demo.ipynb`)
   - Modify genome evaluation workflow to use new async pattern
   - Update fitness plotting to show F1, F2, F3 separately
   - Add error handling for failed evaluations
   - Update documentation cells

### Phase 4: Configuration & Deployment

9. **Extend configuration** (`gi/config.py`)
   - Add ES API server settings:
     - `EVAL_SERVER_URL`
     - `EVAL_SERVER_TOKEN`
     - `EVAL_DB_URI`
   
   - Add build agent settings:
     - `BUILD_VMS` (list of VM configurations)
     - `BUILD_VM_TIMEOUT`
     - `MAKEFILE_PATH`
     - `BUILD_UNIT_TEST_PATH`
   
   - Add monitor settings:
     - `VM_PROVIDER` (vmware/libvirt)
     - `VM_SNAPSHOT_NAME`
   
   - Add classifier settings:
     - `CLASSIFIER_TARGET_CLASS` (e.g., "wmi", "com", "cmd")
     - Verify existing `CLASSIFIER_PATH` and `TOKENIZER_PATH`

10. **Create deployment documentation** (`gi/README.md`)
    - Document four-component architecture
    - Provide setup instructions for each component:
      - ES API server on Linux host
      - Build agent on Windows VMs
      - Monitor on Linux host
      - GIMC sandbox (already running)
    - Add VM configuration guide (snapshots, networking)
    - Document required dependencies for each component
    - Add troubleshooting section

11. **Create VM setup scripts**
    - Windows VM setup script for build agent:
      - Install GCC (MinGW-w64)
      - Install Python and dependencies
      - Configure build agent to auto-start
      - Create VM snapshot
    - Linux setup script for ES API and monitor
    - Document network configuration requirements

### Phase 5: Testing & Validation

12. **Create unit tests** (`gi/unit_tests/`)
    - `test_eval_api.py` - Test all ES API endpoints
    - `test_build_agent.py` - Test compilation and fitness calculation
    - `test_monitor.py` - Test VM management and classification
    - `test_genome_integration.py` - Test end-to-end genome submission

13. **Integration testing**
    - Deploy all components in test environment
    - Submit known-good and known-bad code samples
    - Verify F1, F2, F3 calculations
    - Test VM reset and recovery
    - Test parallel candidate processing
    - Verify classification accuracy on test set

14. **Performance testing**
    - Measure throughput (candidates per minute)
    - Test with multiple VMs for parallel processing
    - Identify bottlenecks (compilation, testing, classification)
    - Optimize as needed

### Phase 6: Documentation & Refinement

15. **Update classifier README** (`classifier/README.md`)
    - Separate DSAA work from BSI work
    - Document BSI CNN model training process
    - Add usage instructions for inference
    - Document model performance metrics
    - Add retraining guide for new classes

16. **Create operational runbook**
    - How to start/stop all components
    - How to add new VMs for scaling
    - How to update classifier model
    - How to change target class
    - Monitoring and logging best practices
    - Common error scenarios and solutions

17. **Smoke test full GI pipeline**
    - Run small genetic improvement experiment (10 generations)
    - Verify candidates progress through all stages
    - Check that fitness influences evolution
    - Validate VM resets occur correctly
    - Confirm no resource leaks or stuck processes

## Critical Design Decisions

### 1. Fitness Normalization Strategy

**Options:**
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

**Recommendation:** Start with staged filtering (F1 > 0.5 to compute F2, F2 > 0.5 to compute F3), then use weighted product for final fitness. Allows early rejection of non-compiling code while still considering all objectives for viable candidates.

### 2. Parallel Processing Model

**Options:**
- **Queue-based:** ES API maintains queue, assigns work to VMs
  - Pros: Fair distribution, better load balancing
  - Cons: More complex API, requires queue management

- **Poll-based (like sandbox):** VMs poll for work round-robin
  - Pros: Simpler, stateless API, matches existing pattern
  - Cons: Potential for uneven load if VMs have different speeds

**Recommendation:** Use poll-based model to match sandbox architecture. ES API returns first pending candidate on each poll. If load balancing becomes issue, add VM-specific queues later.

### 3. Error Recovery Strategy

**Scenarios:**
- **Compilation crashes VM:** Build agent can't report back
- **Unit test hangs:** Build agent stuck in building state
- **Classification fails:** Monitor encounters corrupted report

**Solutions:**
- Monitor detects timeouts (status=1 for > `VM_TIMEOUT` seconds)
- Force VM reset and mark candidate as error (status=4)
- Crashed builds get F1=F2=F3=0, not re-queued (assume bad code)
- Classification errors set F3=0, still mark complete (status=3, partial fitness)

**Recommendation:** Implement aggressive timeouts with no retries. Bad code is more likely than transient errors. Log all errors for post-mortem analysis.

### 4. VM Scaling Strategy

**Options:**
- **Static pool:** Fixed number of VMs, configured at startup
  - Pros: Simple, predictable resource usage
  - Cons: Can't adapt to load

- **Dynamic scaling:** Add/remove VMs based on queue depth
  - Pros: Better resource utilization
  - Cons: Complex, slow (VM startup time)

**Recommendation:** Start with static pool of 2-4 VMs. Easy to add more manually if needed. Dynamic scaling can be future enhancement if throughput becomes bottleneck.

## Open Questions

1. **Should build agent run unit tests in separate process?**
   - Current sandbox runs analysis in same process as agent
   - Unit tests might crash agent if malicious
   - Separate process adds complexity but improves safety

2. **How to handle candidates that pass unit tests but crash sandbox?**
   - F1=0.9, F2=1.0, but no sandbox report for F3
   - Set F3=0 and mark complete (status=3)? Or status=error (status=4)?
   - May indicate interesting evasive behavior

3. **Should ES API enforce uniqueness on code hash?**
   - Prevent duplicate evaluations (efficiency)
   - Or allow re-evaluation with different fitness (exploration)
   - Deduplication could be optional via query parameter

4. **What format for sandbox report input to classifier?**
   - Raw JSON report from sandbox?
   - Pre-extracted features (opcode sequences, API calls)?
   - Need to align with classifier training data format

5. **How to version classifier models?**
   - Config points to specific checkpoint file
   - Or version number in config with lookup table?
   - How to A/B test new models?

## Success Criteria

- [ ] ES API successfully accepts code submissions and returns hashes
- [ ] Build agent compiles code in VM and reports F1
- [ ] Build agent runs unit tests and reports F2
- [ ] Build agent submits binaries to GIMC sandbox
- [ ] Monitor detects completed analyses and computes F3
- [ ] Monitor successfully resets VMs after builds
- [ ] Genome class can submit code and retrieve fitness asynchronously
- [ ] Classifier produces reasonable probabilities for known samples
- [ ] Full GI loop can evolve candidates over multiple generations
- [ ] System handles errors gracefully (timeouts, crashes, bad code)
- [ ] Multiple VMs can process candidates in parallel
- [ ] All components documented and tested

## Next Steps

1. Review and refine this plan
2. Prioritize tasks within each phase
3. Set up development environment and test VMs
4. Begin Phase 1: Core Infrastructure
5. Iterate based on testing and feedback

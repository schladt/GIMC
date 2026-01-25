# 🧬 GIMC - Genetically Improved Malicious Code

[![Research](https://img.shields.io/badge/Research-Cybersecurity%20%2B%20ML-blue)](https://github.com/schladt/GIMC)
[![License](https://img.shields.io/badge/License-Academic%20Use-green)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-brightgreen)](https://python.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-ML%20Framework-orange)](https://pytorch.org)

> **Advancing malware research through AI-driven genetic improvement and behavioral analysis**

## 🎯 Project Overview

GIMC addresses a fundamental challenge in cybersecurity research: **how do we understand and defend (through reconstruction) against malware procedures when source code and binaries are unavailable?** This project combines Large Language Models (LLMs), Genetic Improvement (GI), and advanced behavioral analysis to generate, evolve, and classify malware-like behaviors for defensive research.

### 🔬 Research Innovation

GIMC introduces a novel approach that:
- **🤖 Generates** functionally equivalent, syntactically diverse code prototypes using LLMs
- **🧪 Evolves** these prototypes through genetic improvement to match specific malware behaviors  
- **📊 Classifies** implementations using ML models trained on dynamic analysis telemetry
- **🔄 Iterates** through adversarial training between generator and discriminator components

### 🎓 Academic Context

This framework supports cybersecurity research by enabling:
- **Data Augmentation**: Generate synthetic malware behaviors for detection pipeline training
- **Threat Modeling**: Create procedure-level emulations for blue-team validation
- **Behavioral Analysis**: Understand implementation diversity within malware families
- **Anticipatory Defense**: Explore likely-future variants before they appear in the wild

## 🏗️ System Architecture

```mermaid
graph TB
    A[🤖 LLM Prototype Generation] --> B[🧪 Unit Test Validation]
    B --> C[📦 Sandbox Execution]
    C --> D[🎯 Behavioral Classification]
    D --> E[🧬 Genetic Improvement]
    E --> F[🔄 Fitness Evaluation]
    F --> C
    
    G[🗄️ Database] --> D
    H[⚙️ Evaluation Server] --> F
```

## 📁 Project Components

### 🤖 [Classifier](./classifier/) - NLP-Based Malware Classification
Advanced machine learning models that classify malware families using dynamic analysis reports as natural language text.

**Key Features:**
- Multiple neural architectures (MLP, CNN, LSTM, Transformer/BERT)
- State-of-the-art NLP techniques for behavioral pattern recognition
- Multi-family classification with extensible framework
- Comprehensive evaluation and metrics comparison

**Models Available:**
- **MLP**: Fast baseline classification
- **CNN**: N-gram pattern detection  
- **LSTM**: Sequential behavior analysis
- **BERT/Transformer**: Advanced contextual understanding

### 🧬 [Genetic Improvement](./genetic_improvement/) - Code Evolution & Evaluation
Complete pipeline for evolving and evaluating code candidates through compilation, testing, and behavioral analysis.

**Key Components:**
- **Evaluation Server**: RESTful API for candidate submission and fitness tracking
- **Build Agent**: VM-based compilation and unit testing with MinGW
- **Monitor**: ML-based behavioral classification and VM timeout management
- **Genome Engine**: AST-level code manipulation using srcML

**Key Features:**
- Multi-stage fitness evaluation (F1: compile quality, F2: test pass rate, F3: behavioral score)
- Automatic makefile and unit test distribution to build agents
- Composite fitness scoring with surrogate optimization
- High-throughput evolution with VM pool parallelization
- Candidate database tracking with SQLAlchemy ORM

### 📦 [Sandbox](./sandbox/) - High-Throughput Dynamic Analysis
Lightweight, scalable malware analysis sandbox designed for massive behavioral evaluation loops.

**Key Features:**
- High-throughput execution (~13.58s/sample average)
- Multi-VM orchestration (VMware/libvirt support)
- Standardized telemetry collection (Procmon + Sysmon)
- Isolated execution environment with snapshot restoration
- RESTful API for automated sample submission

**Sandbox Stats:**
- Processed 30,221+ analyses in research validation
- Supports 12+ concurrent Windows 10 VMs
- Configurable VM pools and analysis timeouts

### 🔬 [Behavioral Subsets](./behavioral_subsets/) - Malware TTP Implementations
Reference implementations of specific malware Tactics, Techniques, and Procedures (TTPs) for genetic improvement research.

**Current Focus:**
- **Scheduled Execution**: Task scheduling via WMI, COM, and CMD implementations
- Unit test frameworks for behavioral validation
- Makefiles for MinGW cross-compilation to Windows binaries

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.8+ with virtual environment
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Additional ML dependencies for classifier
pip install torch torchvision transformers tokenizers

# Database setup (PostgreSQL required)
# Install PostgreSQL and create database:
createdb gimc
```

### Configuration

Create `settings.json` in the project root (not included in repo for security):

```json
{
    "openai_api_key": "sk-your-openai-api-key-here",
    "data_path": "/mnt/data/gimc",
    "sqlalchemy_database_uri": "postgresql://gimc_user:gimc_dev_pass@localhost/gimc",
    "sandbox_token": "your_secure_random_token_here",
    "srcml_client": "/usr/local/bin/srcml",
    "sandbox_url": "http://192.168.122.1:5000",
    "evaluation_server": "http://192.168.122.1:5050",
    "launcher": {
        "eval_server": {
            "interface": "192.168.122.1",
            "port": "5050"
        },
        "es_monitor": {
            "classifier": "/mnt/data/gimc/classifier/model_data/cnn4bsi_checkpoint.pth",
            "tokenizer": "/mnt/data/gimc/classifier/model_data/mal-reformer",
            "signatures": "wmi,com,cmd,benign"
        },
        "sandbox_server": {
            "interface": "192.168.122.1",
            "port": "5000"
        },
        "sandbox_monitor": {}
    }
}
```

**Configuration Notes:**
- `data_path`: Directory for storing models, datasets, and analysis reports
- `sqlalchemy_database_uri`: PostgreSQL connection string for unified database
- `sandbox_token`: Shared authentication token for API security
- `srcml_client`: Path to srcML binary for AST manipulation
- `launcher`: Service configurations for the system launcher (see below)

### System Launch

**Option 1: Single-Command Launcher (Recommended)**

Start all GIMC services with colored output:

```bash
python launch_gimc.py
```

This launches:
- 🟢 **Evaluation Server** - Manages candidate submission and fitness tracking
- 🔵 **ES Monitor** - Performs ML classification and VM management
- 🟡 **Sandbox Server** - Accepts samples for dynamic analysis
- 🟣 **Sandbox Monitor** - Orchestrates VM execution and telemetry collection

Press `Ctrl+C` to gracefully stop all services.

**Option 2: Manual Service Launch**

Individual components can be started separately for debugging:

```bash
# Terminal 1: Evaluation Server
python -m genetic_improvement.evaluation_server 192.168.122.1 5050

# Terminal 2: ES Monitor
python -m genetic_improvement.monitor \
    --classifier /path/to/cnn4bsi_checkpoint.pth \
    --tokenizer /path/to/mal-reformer \
    --signatures wmi,com,cmd,benign

# Terminal 3: Sandbox Server
python -m sandbox.sandbox_server 192.168.122.1 5000

# Terminal 4: Sandbox Monitor
python -m sandbox.monitor
```

### Submit a Candidate

Once services are running, submit code for evaluation:

```bash
python -m genetic_improvement.submit_code \
    --class wmi \
    --makefile behavioral_subsets/scheduled_execution/wmi/Makefile \
    --unittest behavioral_subsets/scheduled_execution/test_scheduled_execution.py \
    ~/samples/wmi_persistence.cpp
```

The system will:
1. 📝 Store candidate in database with makefile, unittest, and classification
2. 🏗️ Distribute to build agent for compilation (F1 fitness)
3. ✅ Execute unit tests (F2 fitness)
4. 🔬 Submit binary to sandbox for dynamic analysis
5. 🤖 Classify behavior using ML model (F3 fitness)
6. ✨ Return composite fitness score

### Component Setup

1. **🏃‍♂️ Start the Sandbox**:
```bash
cd sandbox/
python run.py 0.0.0.0 5000
```

2. **🤖 Train a Classifier**:
```bash
cd classifier/
jupyter notebook mlp4mal.ipynb
```

3. **🧬 Run Genetic Improvement**:
```bash
cd gi/
python gi_demo.ipynb
```

## 📊 Research Results

### 🎯 Classification Performance
- **Binary Classification**: 100% validation accuracy (DFS vs BFS traversal)
- **Multi-class**: 100% validation accuracy by epoch 11 (3-class problem)
- **Training Time**: ~26 minutes (binary), ~239 minutes (3-class) on RTX 3080

### 🧬 Evolution Efficiency  
- **LLM Success Rate**: ~25% of requests yield passing implementations
- **Genetic Convergence**: 100 unique optimal solutions by generation 60
- **Surrogate Speed**: ~60× faster than full behavioral evaluation
- **Scalability**: ~2.4 hours for full analysis with 10× parallelization

### 📦 Sandbox Throughput
- **Processing Rate**: 30,221 analyses over 98.6 hours
- **Average Runtime**: ~19.58 seconds per sample
- **VM Configuration**: 12 Windows 10 VMs on single Ubuntu host (i9-10850K, 128GB RAM)

## 📈 Applications & Impact

### 🛡️ Defensive Research
- **Detection Enhancement**: Generate diverse training data for ML-based malware detectors
- **Threat Intelligence**: Understand procedural variations within malware families
- **Red Team Exercises**: Create realistic adversarial scenarios for security validation

### 🔍 Academic Research
- **Behavioral Analysis**: Study implementation diversity in malicious code
- **ML Security**: Explore adversarial examples in cybersecurity contexts  
- **Code Generation**: Advance AI-assisted programming for security applications

### 🚀 Future Work
- **Larger Scale**: Expand to enterprise-grade malware families and TTP coverage
- **Real-time Integration**: Deploy in live threat hunting and incident response
- **Collaborative Defense**: Share synthetic signatures across security organizations

## 🛠️ Technical Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **🤖 ML/AI** | PyTorch, Transformers, scikit-learn | Model training and inference |
| **🧬 Code Analysis** | srcML, AST manipulation | Genetic code modification |
| **📦 Virtualization** | libvirt, VMware | Sandbox environment management |
| **🗄️ Data** | PostgreSQL, SQLAlchemy | Persistent storage and ORM |
| **🌐 APIs** | Flask, RESTful services | System integration and control |
| **📊 Analysis** | Sysmon, Process Monitor | Dynamic behavior collection |

## 📚 Documentation

- 📖 **[Classifier README](./classifier/README.md)**: Detailed NLP model documentation
- 📦 **[Sandbox README](./sandbox/README.md)**: Complete sandbox setup and usage guide  
- 🧬 **[GI Documentation](./gi/)**: Genetic improvement algorithms and fitness functions
- 🔬 **[Research Prototypes](./prototypes/)**: Experimental code and proof-of-concepts

## ⚠️ Research Ethics & Safety

**This project is designed for defensive cybersecurity research only.** All generated code is:
- 🔒 Executed in isolated sandbox environments
- 🎓 Intended for academic and defensive security research
- 📋 Subject to responsible disclosure practices
- 🛡️ Designed to improve detection and defense capabilities

**Not for malicious use.** The research emphasizes controlled execution, isolation, and research-only applications.

## 🤝 Contributing

We welcome contributions to advance defensive cybersecurity research:

1. **🔀 Fork** the repository
2. **🌟 Create** a feature branch (`git checkout -b feature/research-enhancement`)
3. **💾 Commit** your changes (`git commit -am 'Add defensive research feature'`)
4. **📤 Push** to the branch (`git push origin feature/research-enhancement`)
5. **🔄 Create** a Pull Request

### 📋 Contribution Guidelines
- Follow existing code style and documentation standards
- Include comprehensive tests for new functionality
- Update documentation for any API changes
- Ensure all research follows ethical guidelines

## 📄 License & Citation

This project is released under an academic research license. If you use GIMC in your research, please cite:

```bibtex
@misc{gimc2025,
  title={Genetically Improved Malicious Code: Using AI to Generate and Evolve Malware Behaviors for Defensive Research},
  author={Schladt, Michael},
  year={2025},
  institution={University of Cincinnati},
  note={Doctoral Research Project}
}
```

## 📞 Contact & Support

- 👤 **Author**: Michael Schladt
- 🏫 **Institution**: University of Cincinnati  
- 🐛 **Issues**: [GitHub Issues](https://github.com/schladt/GIMC/issues)

---

<div align="center">

**🔬 Advancing Cybersecurity Through AI-Driven Research 🛡️**

*Built with ❤️ for the defensive security research community*

</div>

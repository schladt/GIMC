# 🧬 GIMC — Genetically Improved Malicious Code

> A defensive research system for reconstructing candidate implementations of malicious procedures from endpoint telemetry, functional constraints, and bounded search.

Incident-response and malware-analysis workflows often preserve **behavioral evidence** longer than they preserve the original source code or binary. GIMC explores what can still be learned in that setting: instead of trying to recover a byte-identical original program, it searches for candidate implementations that satisfy a known functional contract and exhibit the target behavior under observation.

The current research scope is deliberately bounded. GIMC works with **behavioral subset implementations (BSIs)**—small, sanitized programs that reproduce one target behavior while removing unrelated or dangerous functionality. The present target family is recurring scheduled execution on Windows, represented through tactically distinct `cmd`, `com`, and `wmi` implementations.

## 🎯 What GIMC does

GIMC combines four ideas that are usually studied separately:

- **Telemetry-guided scoring** — Windows execution traces are classified to estimate behavioral alignment.
- **LLM-seeded search** — LLMs provide seed and donor code, then later help repair damaged mutants after mutation.
- **AST-level genetic improvement** — candidates are transformed through a hierarchical syntax-tree representation rather than treated as flat text.
- **Staged validation** — candidates must build, satisfy a shared functional contract, and match the target behavior.

That combination makes GIMC neither a detector nor an unrestricted malware generator. It is a controlled reconstruction system whose outputs are **candidate implementations** evaluated against explicit evidence.

## 🔁 Core reconstruction loop

```text
BSI target + functional contract
              ↓
LLM seeds and donor code
              ↓
AST-level genetic improvement
              ↓
compile → unit test → sandbox telemetry → behavior score
              ↓
selection, repair, and bottleneck handling
              ↺
```

Each candidate is evaluated with three staged signals:

| Signal | Meaning |
|---|---|
| `F1` | build / compile quality |
| `F2` | functional correctness against a shared unit-test contract |
| `F3` | behavioral alignment from telemetry-based classification |

These signals keep the search grounded in both **executable correctness** and **observable behavior**. Generated code is useful here because it becomes material for a validated search loop—not because generation alone is treated as an answer.

## 🧭 Design principles

- **Behavior over byte identity:** the objective is behavioral fidelity to a controlled target, not exact source recovery.
- **LLMs inside the loop:** language models contribute genetic material and bounded repair, while evaluation and selection decide what survives.
- **Safety by construction:** the project uses sanitized BSIs, benign payloads, isolated VMs, and explicit target contracts.
- **Implementation diversity matters:** different code paths can realize the same objective while leaving meaningfully different telemetry behind.

## 🧩 Repository map

| Path | Purpose |
|---|---|
| [`behavioral_subsets/`](./behavioral_subsets/) | Sanitized BSI targets and shared tests |
| [`classifier/`](./classifier/) | Telemetry preprocessing, tokenization, and ML classifiers |
| [`genetic_improvement/`](./genetic_improvement/) | Genome representation, GI loop, evaluation server, repair, and build orchestration |
| [`sandbox/`](./sandbox/) | Windows sandbox execution, VM management, and telemetry collection |
| [`launch_gimc.py`](./launch_gimc.py) | Starts the main services from one command |

For component-level detail, begin with the linked READMEs in each directory.

## ⚙️ How the pieces fit together

1. A BSI defines the target behavior and the shared functional contract.
2. The system generates seed and donor code, then mutates candidates through an AST-backed genome representation.
3. Build agents compile candidates and run the shared tests.
4. Executable candidates run in isolated Windows VMs, where sandbox telemetry is collected.
5. A classifier scores the telemetry against the target class.
6. Selection, post-mutation repair, and bottleneck handling guide the next generation.

## 🚀 Quick start

### 1. Prepare the environment

```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

You will also need:

- PostgreSQL
- `srcML`
- Windows build VMs with MinGW
- Windows sandbox VMs with the required monitoring tools
- trained classifier/tokenizer artifacts

### 2. Create `settings.json`

The root `settings.json` is intentionally not committed. At minimum, it must define database access, sandbox access, the `srcML` path, and launcher settings for the evaluation server, evaluation-server monitor, sandbox server, and sandbox monitor.

A representative shape is:

```json
{
  "data_path": "/path/to/data",
  "sqlalchemy_database_uri": "postgresql://user:password@host/database",
  "sandbox_token": "shared-secret",
  "srcml_client": "/usr/local/bin/srcml",
  "sandbox_url": "http://192.168.122.1:5000",
  "evaluation_server": "http://192.168.122.1:5050",
  "launcher": {
    "eval_server": {"interface": "192.168.122.1", "port": "5050"},
    "es_monitor": {
      "classifier": "/path/to/cnn4bsi_checkpoint.pth",
      "tokenizer": "/path/to/tokenizer",
      "signatures": "wmi,com,cmd,benign"
    },
    "sandbox_server": {"interface": "192.168.122.1", "port": "5000"},
    "sandbox_monitor": {}
  }
}
```

### 3. Start the services

```bash
python launch_gimc.py
```

This starts the evaluation server, evaluation-server monitor, sandbox server, and sandbox monitor together. For debugging or distributed deployment, each service can also be launched independently; see [`genetic_improvement/README.md`](./genetic_improvement/README.md) and [`sandbox/README.md`](./sandbox/README.md).

### 4. Submit a candidate

```bash
python -m genetic_improvement.submit_code \
  --class wmi \
  --makefile behavioral_subsets/scheduled_execution/wmi/Makefile \
  --unittest behavioral_subsets/scheduled_execution/test_scheduled_execution.py \
  /path/to/candidate.cpp
```

The candidate will be compiled, tested, executed in the sandbox if viable, classified from telemetry, and stored with its resulting fitness values.

## 📌 Current scope

- **Target behavior family:** recurring scheduled execution on Windows
- **Implemented BSI classes:** `cmd`, `com`, `wmi`
- **Primary representation:** hierarchical AST-backed genomes using `srcML`
- **Behavioral evidence:** Windows telemetry collected through the sandbox pipeline
- **Intended use:** controlled defensive research and method development

## 🔒 Safety boundary

GIMC is built for defensive cybersecurity research. The repository uses sanitized BSIs, benign payloads, isolated VM execution, and controlled evaluation workflows. It is not intended for unrestricted malware generation, operational deployment, or exact recovery of arbitrary malware source code.

## 📚 Documentation

- [`behavioral_subsets/README.md`](./behavioral_subsets/README.md)
- [`classifier/README.md`](./classifier/README.md)
- [`genetic_improvement/README.md`](./genetic_improvement/README.md)
- [`sandbox/README.md`](./sandbox/README.md)

## Contact

- **Author:** Michael Schladt
- **Institution:** University of Cincinnati
- **Issues:** <https://github.com/schladt/GIMC/issues>

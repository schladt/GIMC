# malware_bsi

This directory contains **malware behavioral subset implementations (BSI)**. These are small, sanitized programs derived from real-world malware that faithfully emulate a **single malicious behavior / TTP** while removing all unrelated or dangerous functionality. In this project, they act as **stand-ins for real malware samples** and serve as the **behavioral targets** we aim to replicate and study through the GIMC pipeline. 🧪

---

## Contents & Safety ⚠️

- All code represented here is **benign and sanitized**.  
  It is curated solely to demonstrate specific TTPs and replicate system behavior for **research purposes only**.
- Because some patterns may still trigger **EDR or GitHub security alerts**, all source code is stored as **password-protected ZIP archives**.
- The standard password for all archives is:

  `gimc` 🔐

---

## Developer Notes 💻

- When adding or updating BSI code:
  - Keep implementations **benign** and **scoped** to the intended behavior.
  - Commit **only encrypted ZIP files** — never commit decrypted source.
- The repository `.gitignore` excludes anything in `*/tmp/`.  
  Best practice is to use a `tmp/` directory as your **working area** for decrypted files and build artifacts, and never commit anything from there.

### Using the Encryption Utility 🔧

The `utils/encrypt_bsi.py` utility simplifies encrypting and decrypting BSI files:

**First-time setup**:
```bash
pip install -r requirements.txt
```

**Encrypt a file** (creates password-protected ZIP):
```bash
python utils/encrypt_bsi.py myfile.c
# Output: myfile.c.zip (with password: gimc)
```

**Decrypt an archive** (extracts to `./tmp/` by default):
```bash
python utils/encrypt_bsi.py archive.zip -d
# Extracts files to ./tmp/
```

**Advanced options**:
```bash
# Custom output filename and password
python utils/encrypt_bsi.py myfile.c -o custom.zip -p mypassword

# Decrypt to custom directory
python utils/encrypt_bsi.py archive.zip -d --output-dir ./custom/
```

Run `python utils/encrypt_bsi.py --help` for full usage details.

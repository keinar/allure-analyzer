# Allure Failure Analyzer

> A fast, configurable command‑line tool that scans **Allure** results, **groups failures by root cause**, and produces an easy‑to‑read, **interactive HTML** (and JSON) report.

---

## Table of Contents
- [Why](#why)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Usage](#usage)
- [How It Works](#how-it-works)
- [Fingerprinting Logic](#fingerprinting-logic)
- [Output](#output)
- [Performance Tips](#performance-tips)
- [CI Examples](#ci-examples)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Contributing](#contributing)
- [License](#license)

---

## Why
Running hundreds or thousands of tests can create **a lot** of noise. The hard part isn’t seeing *which tests failed* — it’s understanding **why** they failed and **which failures share the same root cause**.  
This tool turns raw Allure data into **actionable insights** so you can focus debugging where it matters most.

---

## Key Features
- **Deep Failure Analysis**: Walks the entire Allure JSON graph — results, containers, nested steps, and attachments.
- **Intelligent Grouping**: A robust, regex‑driven “fingerprinting” mechanism that clusters failures by **cause**, not by test name.
- **Interactive HTML Report**: One self‑contained page with:
  - Dark/Light mode
  - Live search/filter
  - Collapsible groups and examples
  - Progress bars for **Failed** vs **Broken**
- **Fast & Parallel**: Uses `ProcessPoolExecutor` to parse thousands of files quickly.
- **Zero Network Calls**: Works entirely offline.
- **Config‑First**: Behavior controlled via a single `config.yaml`.
- **Simple UX**: Optional local web server to open the report for you.

> **Note**: You can ship just the Markdown/JSON report if you prefer, or use the HTML dashboard for an at‑a‑glance overview.

---

## Quick Start
```bash
# 1) Create a virtual environment
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows
# .venv\Scripts\activate

# 2) Install dependencies
pip install -r requirements.txt

# 3) Configure the tool
#    Edit config.yaml (see below), set your allure-results path

# 4) Run
python main.py

# 5) Open the HTML dashboard (optional)
# If prompted, answer 'y' OR:
python -m http.server
# then visit http://localhost:8000/report.html
```

---

## Installation
- **Python**: 3.8+ recommended
- **Dependencies**: managed via `requirements.txt` (minimal set; typically `PyYAML`)

```bash
pip install -r requirements.txt
```

---

## Configuration
All behavior is controlled via `config.yaml` in the project root.

```yaml
# Path to the Allure results directory generated after a test run.
# This is the most important setting.
allure_results_directory: './allure-results'

# Output HTML (and its companion JSON) file name.
# The tool will generate 'failure_analysis_report.json' and 'report.html' using this base.
output_report_file: 'failure_analysis_report.html'

# Number of top groups to include (0 or negative = no limit).
top_n_groups_to_report: 20

# (Optional, recommended) Used to locate the most relevant line in stack traces.
# For TypeScript/JS projects, choose a stable substring that appears in your code paths
# (e.g., 'src/', 'apps/web', 'packages/').
project_root_package: 'src/'
```

**Choosing `project_root_package`** (TS/JS):
- Prefer a path segment unique to your code (e.g., `src/`, `packages/`, `apps/web`).
- Avoid strings that may appear in `node_modules`.
- If in doubt, start with `src/` and refine.

---

## Project Structure
```
allure-analyzer/
├─ analyzer/
│  ├─ __init__.py          # Makes 'analyzer' a Python package
│  ├─ ingestion.py         # Fast, parallel ingestion from Allure results (+ containers/steps/attachments)
│  ├─ fingerprinter.py     # Failure fingerprint generation and normalization
│  └─ reporting.py         # Builds grouped data and writes final JSON/Markdown/HTML
├─ config.yaml             # Main configuration (edit this)
├─ main.py                 # Entrypoint
├─ report.html             # Static HTML dashboard (reads the generated JSON)
└─ requirements.txt        # Dependencies
```

---

## Usage
```bash
python main.py
```
What happens:
1. The tool scans `allure_results_directory` for `*-result.json` files.
2. It correlates them with matching `*-container.json` files and their attachments.
3. It extracts **failed/broken** failures with rich context.
4. It groups them by fingerprint and writes:
   - `failure_analysis_report.json` – structured data
   - `failure_analysis_report.md` (optional) – Markdown summary
   - `report.html` – interactive dashboard (consumes the JSON)

> To serve the HTML locally:
> ```bash
> python -m http.server
> # open http://localhost:8000/report.html
> ```

---

## How It Works
### 1) Ingestion (`analyzer/ingestion.py`)
- Parallel file parsing with `ProcessPoolExecutor`
- Reads `*-result.json` **and** corresponding `*-container.json`
- Traverses nested steps and attachments recursively
- Extracts:
  - `message`, `trace` (including from text/JSON attachments)
  - step names and the first **failing** step
  - Allure labels (`epic`, `feature`, `package`, `testClass`, `testMethod`, etc.)

### 2) Fingerprinting (`analyzer/fingerprinter.py`)
- Builds stable keys by normalizing volatile parts:
  - UUIDs, numbers, IPs, emails, URLs, timestamps, file paths
  - JIRA-like keys (`ABCD-12345` → `ABCD-<NUM>`)
- Picks the most indicative key:
  - `failing_step_name` → else `message` → else `test fullName`
- Resolves code location from stack; falls back to labels when no stack exists

### 3) Reporting (`analyzer/reporting.py`, `report.html`)
- Groups by fingerprint, sorts by frequency
- Aggregates affected epics/features
- Writes JSON for the dashboard and (optionally) a concise Markdown summary
- The static `report.html` renders the data with client‑side JS

---

## Fingerprinting Logic
A fingerprint is composed of **two parts**:  
`{normalized_key} | {code_location}`

- **normalized_key** (priority order):
  1. failing step name (normalized)
  2. message (normalized)
  3. test fullName/name (normalized)

- **code_location**:
  - First stack line that includes `project_root_package`
  - If no stack: fallback to labels (e.g., `package / testClass / testMethod`)

**Normalization removes**: UUIDs, long hex strings, numbers, IPs, emails, URLs, timestamps, and file paths.  
This clusters similar failures even when IDs/line numbers differ.

---

## Output
- **`failure_analysis_report.json`**: Canonical data source for the dashboard.
- **`report.html`**: Interactive, self‑contained viewer reading the JSON.
- **`failure_analysis_report.md`** (optional): Human‑readable Markdown summary.

Each group includes:
- total count and % of all failures
- fingerprint parts (Normalized Key + Code Location)
- aggregated **epics/features**
- one expandable example with full message + stack trace

---

## Performance Tips
- Keep `allure_results_directory` on SSD.
- Analyze only the latest run (avoid massive historical folders).
- Ensure `project_root_package` points at your code to get accurate stack matching.
- Default parallelism scales to available CPU cores; adjust only if you know you need to.

---

## CI Examples
### GitHub Actions
```yaml
- name: Generate Allure Failure Analysis
  run: |
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python main.py
- name: Upload analysis artifact
  uses: actions/upload-artifact@v4
  with:
    name: failure-analysis
    path: |
      failure_analysis_report.json
      failure_analysis_report.md
      report.html
```

### GitLab CI
```yaml
analyze_allure:
  stage: post
  image: python:3.11
  script:
    - pip install -r requirements.txt
    - python main.py
  artifacts:
    paths:
      - failure_analysis_report.json
      - failure_analysis_report.md
      - report.html
```

---

## Troubleshooting
- **No groups / too many unique groups**  
  Ensure `project_root_package` is set (e.g., `src/`). If messages are empty, the tool will group by the **failing step name**.
- **Code Location shows `(no trace)`**  
  Often means stacks are stored in attachments. The ingestor reads containers and nested steps; verify attachments contain stacks or use label fallback.
- **0 files found**  
  Check `allure_results_directory` path and make sure it contains `*-result.json` files.
- **Encoding issues**  
  All files are read as UTF‑8 with safe fallbacks; open an example file to confirm encoding.

---

## FAQ
**Q: Does it contact any external services?**  
A: No. It is 100% offline.

**Q: Can I customize the fingerprint rules?**  
A: Yes. Edit `analyzer/fingerprinter.py` and extend normalization or key selection.

**Q: Will this work for TypeScript/Playwright/Cypress?**  
A: Yes. The ingestor pulls stacks from text/JSON attachments and uses label/step fallbacks when none exist.

---

## Contributing
Issues and PRs are welcome. Please include:
- a small sample of `*-result.json`/`*-container.json`/attachments
- expected grouping behavior
- environment details (OS, Python) and a short repro script

---

## License
Choose a license that fits your project (e.g., MIT/Apache‑2.0). Add a `LICENSE` file accordingly.

import os
import sys
import yaml
import webbrowser
from typing import Dict, List, Tuple

# Local package imports
from analyzer import collect_failures_from_allure, Fingerprinter, generate_report_json
# Import the Flask app object from your server file
from server import app 

def _load_config(base_dir: str) -> Dict:
    """Load config.yaml from the project root."""
    cfg_path = os.path.join(base_dir, 'config.yaml')
    print(f"Loading config from {cfg_path} ...")
    try:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print("❌ ERROR: config.yaml not found.")
        sys.exit(1)

def _as_bool(value, default: bool = True) -> bool:
    """Parse boolean-like config values safely."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    return s not in ('false', '0', 'no', 'off', '')

def main() -> None:
    # --- STAGE 1: RUN ANALYSIS ---
    print("="*50)
    print("STAGE 1: Analyzing Allure results...")
    print("="*50)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config = _load_config(base_dir)

    results_dir = config.get('allure_results_directory', './allure-results')
    include_broken = _as_bool(config.get('include_broken', True), default=True)

    print(f"Scanning Allure results in: {results_dir}")
    all_failures = collect_failures_from_allure(results_dir)
    print(f"Found {len(all_failures)} individual failure steps (failed + broken).")

    if include_broken:
        failures = all_failures
        print("Including BROKEN tests in analysis (include_broken=true).")
    else:
        failures = [f for f in all_failures if (f.get('status') or '').lower() == 'failed']
        print(f"Excluding BROKEN tests (include_broken=false). Kept {len(failures)} failed steps.")

    if not failures:
        print("\nNo failures to analyze after filtering. Exiting.")
        return

    print("Fingerprinting and grouping failures ...")
    fp = Fingerprinter()

    groups: Dict[str, List[Dict]] = {}
    for failure in failures:
        key = fp.create_fingerprint(failure)
        groups.setdefault(key, []).append(failure)

    sorted_groups: List[Tuple[str, List[Dict]]] = sorted(
        groups.items(), key=lambda kv: len(kv[1]), reverse=True
    )

    top_n_raw = config.get('top_n_groups_to_report', 20)
    try:
        top_n = int(top_n_raw)
    except Exception:
        top_n = 20
        
    if top_n > 0:
        print(f"Generating report for the top {top_n} failure groups...")
        groups_to_report = sorted_groups[:top_n]
    else:
        print("Generating report for ALL failure groups...")
        groups_to_report = sorted_groups

    generate_report_json(groups_to_report, config)
    
    # --- STAGE 2: START THE WEB SERVER ---
    print("\n" + "="*50)
    print("STAGE 2: Starting the Web Server...")
    print("="*50)

    url = "http://localhost:8000"
    print(f"✅ Analysis complete. Opening report at: {url}")
    webbrowser.open_new_tab(url)
    
    # Run the Flask app from server.py
    app.run(host='127.0.0.1', port=8000, debug=False)

if __name__ == "__main__":
    main()
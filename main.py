import os
import sys
import yaml
import webbrowser
import http.server
import socketserver
from typing import Dict, List, Tuple

# Local package imports
from analyzer import collect_failures_from_allure, Fingerprinter, generate_report_json

PORT = 8000

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
    """Parse boolean-like config values safely (supports strings like 'false', '0', 'no')."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    return s not in ('false', '0', 'no', 'off', '')

def serve_report(html_file_name: str):
    """Start a local web server and open the report in a browser."""
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        url = f"http://localhost:{PORT}/{html_file_name}"
        print("\n" + "="*50)
        print(f"✅ Starting server at: {url}")
        print("   The report is opening in your default web browser.")
        print("   Press Ctrl+C in this terminal to stop the server.")
        print("="*50 + "\n")

        webbrowser.open_new_tab(url)

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Server stopped by user.")
        finally:
            httpd.shutdown()

def main() -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config = _load_config(base_dir)

    results_dir = config.get('allure_results_directory', './allure-results')
    include_broken = _as_bool(config.get('include_broken', True), default=True)

    print(f"Scanning Allure results in: {results_dir}")
    all_failures = collect_failures_from_allure(results_dir)
    print(f"Found {len(all_failures)} individual failure steps (failed + broken).")

    # Optional filtering based on config flag
    if include_broken:
        failures = all_failures
        print("Including BROKEN tests in analysis (include_broken=true).")
    else:
        failures = [f for f in all_failures if (f.get('status') or '').lower() == 'failed']
        print(f"Excluding BROKEN tests (include_broken=false). Kept {len(failures)} failed steps.")

    if not failures:
        print("No failures to analyze after filtering. Exiting.")
        return

    # Fingerprinting & grouping
    print("Fingerprinting and grouping failures ...")
    fp = Fingerprinter()

    groups: Dict[str, List[Dict]] = {}
    for failure in failures:
        key = fp.create_fingerprint(failure)
        groups.setdefault(key, []).append(failure)

    sorted_groups: List[Tuple[str, List[Dict]]] = sorted(
        groups.items(), key=lambda kv: len(kv[1]), reverse=True
    )

    # Top-N slicing logic: 0/negative -> all
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

    # Build JSON data for the dashboard
    generate_report_json(groups_to_report, config)

    # Offer to open the HTML dashboard
    html_file = "report.html"
    if os.path.exists(html_file):
        answer = input(f"\n❔ Do you want to open the report '{html_file}' now? (y/n): ").lower()
        if answer in ['y', 'yes']:
            serve_report(html_file)
        else:
            print("OK. You can open the 'report.html' file manually later.")
    else:
        print(f"\n⚠️ Warning: Report template '{html_file}' not found in the current directory.")


if __name__ == "__main__":
    main()

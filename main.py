import os
import sys
import yaml
import webbrowser
import http.server
import socketserver
from typing import Dict, List, Tuple

from analyzer import collect_failures_from_allure, Fingerprinter, generate_report_json

PORT = 8000

def _load_config(base_dir: str) -> Dict:
    cfg_path = os.path.join(base_dir, 'config.yaml')
    print(f"Loading config from {cfg_path} ...")
    try:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print("❌ ERROR: config.yaml not found.")
        sys.exit(1)

def serve_report(html_file_name: str):
    """Starts a local web server and opens the report in a browser."""
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

    print(f"Scanning Allure results in: {results_dir}")
    failures = collect_failures_from_allure(results_dir)
    print(f"Found {len(failures)} individual failure steps.")

    if not failures:
        print("No failures to analyze. Exiting.")
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
    
    # --- THIS IS THE UPDATED LOGIC ---
    top_n_str = str(config.get('top_n_groups_to_report', 20))
    top_n = int(top_n_str) if top_n_str.isdigit() and int(top_n_str) > 0 else 0

    groups_to_report = sorted_groups
    if top_n > 0:
        print(f"Generating report for the top {top_n} failure groups...")
        groups_to_report = sorted_groups[:top_n]
    else:
        print("Generating report for ALL failure groups...")
    
    generate_report_json(groups_to_report, config)

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
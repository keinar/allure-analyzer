import json
import os
import datetime as dt
from typing import Dict, List, Tuple
from collections import Counter

def generate_report_json(sorted_groups: List[Tuple[str, List[Dict]]], config: Dict) -> None:
    """
    Generates a JSON file containing all the structured data, including status counts.
    """
    output_path = config.get('output_report_file', 'failure_analysis_report.html')
    json_path = os.path.splitext(output_path)[0] + '.json'

    total_failures = sum(len(group) for _, group in sorted_groups)
    
    report_data = {
        "metadata": {
            "generation_date": dt.datetime.now().isoformat(),
            "total_failures": total_failures,
            "unique_groups": len(sorted_groups),
        },
        "groups": []
    }

    for i, (fingerprint, items) in enumerate(sorted_groups, 1):
        norm_message, code_loc = fingerprint.split('|', 1) if '|' in fingerprint else (fingerprint, '')
        
        example = items[0]
        
        epics = sorted(list({label['value'] for item in items for label in item.get('labels', []) if label.get('name') == 'epic'}))
        features = sorted(list({label['value'] for item in items for label in item.get('labels', []) if label.get('name') == 'feature'}))
        
        # --- NEW: Count statuses for each group ---
        status_counts = Counter(item.get('status', 'unknown') for item in items)
        
        group_obj = {
            "id": i,
            "title": norm_message,
            "failure_count": len(items),
            "percentage": (len(items) / total_failures * 100) if total_failures > 0 else 0,
            "status_counts": dict(status_counts), # e.g., {"failed": 5, "broken": 10}
            "fingerprint_what": norm_message,
            "fingerprint_where": code_loc,
            "epics": epics,
            "features": features,
            "example": {
                "test_name": example.get('fullName') or example.get('name'),
                "message": example.get('message', '(No message)'),
                "trace": example.get('trace', '(No trace)')
            }
        }
        report_data["groups"].append(group_obj)

    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Report data successfully generated at: {json_path}")
    except IOError as e:
        print(f"❌ Error writing JSON data file: {e}")
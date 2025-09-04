import re
import os
from typing import Dict, Any

class Fingerprinter:
    def __init__(self, **kwargs):
        self.specific_patterns = [
            (re.compile(r"waiting for selector `(.*?)` failed", re.IGNORECASE), r"Timeout for selector: \1"),
            (re.compile(r"Custom message:\s*Expected the status code to be (\d+), but found (\d+)", re.IGNORECASE | re.DOTALL), r"Assertion: Expected status code \1 but received \2"),
            (re.compile(r"Custom message:\s*(export didn't end with status SUCCEEDED, but ended with status IN_PROGRESS)", re.IGNORECASE | re.DOTALL), r"Assertion: \1"),
            (re.compile(r"Custom message:\s*(expected toggle icon to be not displayed)", re.IGNORECASE | re.DOTALL), r"Assertion: \1"),
            (re.compile(r"Custom message:\s*(checkbox is not checked:.*)", re.IGNORECASE | re.DOTALL), r"Assertion: Checkbox not checked"),
            (re.compile(r"URL: (.*)", re.IGNORECASE), r"Navigation error on URL: \1"),
            (re.compile(r"Missing test issue id for Xray report", re.IGNORECASE), r"Config error: Missing Xray issue ID"),
            (re.compile(r"NO_ENTITY_FOUND_ERROR", re.IGNORECASE), r"Backend error: NO_ENTITY_FOUND_ERROR"),
            (re.compile(r"Failed to load resource: (net::\w+)", re.IGNORECASE), r"Network error: \1"),
            # This pattern now shortens the long CSP message
            (re.compile(r"Refused to execute inline event handler because it violates the following Content Security Policy", re.IGNORECASE), r"CSP Violation: Refused to execute inline script"),
        ]
        
        self.generic_patterns = [
            (re.compile(r'[a-f0-9]{8}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{12}', re.I), '<UUID>'),
            (re.compile(r'\b\d{5,}\b'), '<LONG_NUM>'),
            (re.compile(r"status of (\d{3})"), r"status of <STATUS_CODE>"),
        ]

    def _create_message_key(self, failure: Dict) -> str:
        """Creates the most meaningful key from the failure data."""
        message = failure.get('message', '')
        
        if not message:
            return f"(No message found in: {failure.get('name', 'Unknown test')})"

        # 1. Try specific patterns
        for pattern, replacement in self.specific_patterns:
            if re.search(pattern, message):
                return re.sub(pattern, replacement, message, count=1).split('\n')[0].strip()

        # 2. Fallback for generic messages
        key = next((line for line in message.split('\n') if line.strip()), "")

        # New logic: If the key is still unhandled/generic, use the test name as a fallback key
        if key.lower().startswith("unhandled error") or not key:
            return f"Unhandled Error in Test: {failure.get('name', 'Unknown test')}"

        # 3. Apply generic cleaning
        for pattern, replacement in self.generic_patterns:
            key = pattern.sub(replacement, key)
            
        return key

    def _get_code_location(self, trace: str) -> str:
        if not trace:
            return "(No stack trace)"
        
        match = re.search(r'at .*?((?:[/\\A-Za-z0-9_-]+\.)+spec\.(?:ts|js):\d+:\d+)', trace)
        if match:
            return os.path.basename(match.group(1))
            
        return "(No test file location in trace)"

    def create_fingerprint(self, failure: Dict[str, Any]) -> str:
        message_key = self._create_message_key(failure) # Pass the whole failure object
        code_location = self._get_code_location(failure.get('trace', ''))
        
        return f"{message_key}|{code_location}"
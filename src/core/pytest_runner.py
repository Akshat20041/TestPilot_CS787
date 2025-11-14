import os
import json
import subprocess

def run_pytest_json(test_file: str, timeout_sec: int = 60):
    """Run pytest and parse JSON report."""
    cmd = ["pytest", test_file, "--disable-warnings", "--maxfail=20", "--json-report", "-q"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
        report = None
        if os.path.exists(".report.json"):
            with open(".report.json", "r", encoding="utf-8") as f:
                report = json.load(f)
        return (proc.returncode, report, proc.stdout, proc.stderr)
    except Exception as e:
        return (-1, None, "", str(e))

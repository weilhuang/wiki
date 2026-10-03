"""Exit 3 + exact business assertion required; crash/timeout/invalid JSON fail."""
import json
import subprocess
import sys
from pathlib import Path
from mutants import NAMES

records = []
for name in NAMES:
    result = subprocess.run([sys.executable, "-B", "verify.py", "--mutant", name],
                            cwd=Path(__file__).parent, capture_output=True, text=True, timeout=5)
    payload = json.loads(result.stdout)
    expected = {"status": "rejected", "mutant": name, "assertion": "WRONG_ALLOW:" + name}
    if result.returncode != 3 or payload != expected or result.stderr:
        raise AssertionError({"mutant": name, "exitCode": result.returncode,
                              "stdout": result.stdout, "stderr": result.stderr})
    records.append({"command": "python3 -B verify.py --mutant " + name,
                    "exitCode": 3, "result": payload})
print(json.dumps({"status": "pass", "meaning": "every unsafe allow was rejected by its intended business assertion",
                  "records": records}, indent=2, sort_keys=True))

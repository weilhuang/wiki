#!/usr/bin/env python3
"""STATIC_ONLY: parse files without starting Docker, SQL or Redis."""
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
def require(condition, message="static contract violated"):
    if not condition:
        raise AssertionError(message)
if sys.flags.optimize:
    raise RuntimeError("Optimized Python is forbidden")
root = Path(__file__).resolve().parent
for path in root.glob("*.py"):
    ast.parse(path.read_text(), filename=str(path))
subprocess.run(["bash", "-n", str(root / "run.sh")], check=True)
compose = (root / "compose.yaml").read_text()
require("ports:" not in compose, "contract violated")
require("internal: true" in compose, "contract violated")
require("image: ${MYSQL_IMAGE" in compose and "image: ${REDIS_IMAGE" in compose, "contract violated")
require(len(re.findall(r"^    image:", compose, re.M)) == 2, "contract violated")
shell = (root / "run.sh").read_text()
require("--project-name" in shell and "down --volumes" in shell, "contract violated")
require(not re.search(r"docker\s+(?:system|volume|image)\s+prune", shell), "contract violated")
require("--remove-orphans" not in shell, "contract violated")
require("down --volumes --timeout 10" in shell, "Compose down timeout argument")
require("up -d --wait --wait-timeout 180" in shell, "Compose up wait timeout argument")
require("--timeout --kill-after" not in shell, "GNU flag leaked into Compose")
require("--wait-timeout --kill-after" not in shell, "GNU flag leaked into Compose")
versions = root / "infra/versions.env"
require(hashlib.sha256(versions.read_bytes()).hexdigest() == "633dd50e7da950a0da9ddb86484e11a63b475a82c89688c3a8f2640c24568a4b", "contract violated")
source = (root / "lab.py").read_text()
require("--skip-reconnect" in source, "contract violated")
require("KILL CONNECTION" in source and "data_lock_waits" in source, "contract violated")
require("threading.Barrier" in source, "contract violated")
require(";" not in (root / "sql/reconcile.sql").read_text().splitlines()[0], "contract violated")
print(json.dumps({"status": "STATIC_ONLY", "python_ast": "PASS", "bash_syntax": "PASS",
                  "file_contracts": "PASS", "mysql_execution": "NOT_RUN", "redis_execution": "NOT_RUN"}))

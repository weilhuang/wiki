"""New r3 package inspection, not another business experiment."""
import ast
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sha = lambda data: hashlib.sha256(data).hexdigest()
prefixes = [chr(47) + name + chr(47) for name in ("workspace", "tmp", "root", "home")]
patterns = [r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", r"AKIA[A-Z0-9]{16}",
            r"gh[pousr]_[A-Za-z0-9]{30,}", r"Bearer [A-Za-z0-9_=-]{20,}"]
report = {"revision": "A-r3-reconstructed", "status": "pass", "textFiles": 0,
          "pythonAST": 0, "zipMembers": 0, "independentExpectedStates": True,
          "scope": "ZIP member byte binding; AST; public private-path/credential-pattern/cache scan",
          "limitations": ["pattern scan cannot guarantee all secrets absent", "no business code executed",
                          "final delivery and manifest checked separately after generation"]}


def check_text(data, name):
    text = data.decode("utf-8")
    for prefix in prefixes:
        assert prefix not in text, (name, "private absolute path")
    for pattern in patterns:
        assert not re.search(pattern, text), (name, "credential pattern")
    return text


for f in sorted(ROOT.rglob("*")):
    if "private" in f.relative_to(ROOT).parts:
        continue
    assert not f.is_symlink(), "symlink"
    assert f.name not in {"__pycache__", "node_modules", ".venv"}, "runtime cache or dependencies"
    if not f.is_file() or f.suffix == ".zip":
        continue
    assert f.suffix not in {".pyc", ".class", ".jar", ".so", ".exe"}, "runtime artifact"
    text = check_text(f.read_bytes(), str(f.relative_to(ROOT)))
    report["textFiles"] += 1
    if f.suffix == ".py":
        ast.parse(text)
        report["pythonAST"] += 1
    if f.suffix == ".json":
        json.loads(text)

binding = json.loads((ROOT / "archive-binding.json").read_text())
archive = ROOT / binding["archive"]["staging"]
assert sha(archive.read_bytes()) == binding["archive"]["sha256"]
with zipfile.ZipFile(archive) as z:
    assert set(z.namelist()) == {m["member"] for m in binding["members"]}
    assert len(z.namelist()) == len(binding["members"])
    for m in binding["members"]:
        assert not m["member"].startswith("/") and ".." not in m["member"].split("/")
        assert (z.getinfo(m["member"]).external_attr >> 16) & 0o170000 == 0o100000
        data = z.read(m["member"])
        assert data == (ROOT / m["source"]).read_bytes()
        assert sha(data) == m["sha256"] and len(data) == m["bytes"]
        assert Path(m["member"]).name not in {"results.json", "runtime.json", "local-results.json", "review-regression-results.json"}
        check_text(data, m["member"])
        report["zipMembers"] += 1
lab = ROOT / "labs/architecture-review-lab"
for f in json.loads((lab / "source-manifest.json").read_text())["files"]:
    assert sha((lab / f["path"]).read_bytes()) == f["sha256"]
run = json.loads((ROOT / "records/model-commands-attempt1.json").read_text())
for f in run["sourceFiles"]:
    assert sha((ROOT / f["path"]).read_bytes()) == f["sha256"]
for c in run["commands"]:
    assert c["exitCode"] == c.get("expectedExitCode", 0)
tree = ast.parse((lab / "expected_states.py").read_text())
assert all(node.module == "copy" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))
assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
sys.path.insert(0, str(lab))
from expected_states import all_oracles
assert json.loads((lab / "mutant-oracles.json").read_text()) == all_oracles()
result = json.loads((lab / "results.json").read_text())
assert result["revision"] == "A-r3-reconstructed"
assert (len(result["correct"]), len(result["mutants"]), len(result["verifierRegressions"])) == (19, 19, 6)
assert (ROOT / "public/architecture-review-results.json").read_bytes() == (lab / "results.json").read_bytes()
regressions = json.loads((lab / "review-regression-results.json").read_text())
assert regressions["revision"] == "A-r3-reconstructed" and len(regressions["results"]) == 3
for item in regressions["results"]:
    assert item["baselineProbe"]["exitCode"] == 0
    assert item["patchedPublicSuite"]["exitCode"] == 1
    assert item["patchedIndependentProbe"]["exitCode"] == 1
    assert item["temporaryCopyRemoved"]
assert (ROOT / "public/architecture-review-regressions.json").read_bytes() == (lab / "review-regression-results.json").read_bytes()
report["archiveSha256"] = sha(archive.read_bytes())
(ROOT / "records/package-check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(report, ensure_ascii=False))

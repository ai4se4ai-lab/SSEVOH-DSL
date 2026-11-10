#!/usr/bin/env python3
"""Inventory the pinned source and run its actual read-only publication checks."""

import ast
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKOUT = ROOT / "original/upstream"


def git(*args):
    return subprocess.check_output(["git", "-C", str(CHECKOUT), *args], text=True).strip()


def main():
    pin = json.loads((ROOT / "upstream-pin.json").read_text())
    if git("rev-parse", "HEAD") != pin["commit"] or git("status", "--porcelain"):
        raise SystemExit("Inspection requires the clean pinned checkout")
    files = git("ls-files").splitlines()
    inventory = []
    for name in files:
        path = CHECKOUT / name
        record = {
            "path": name,
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        if name.endswith(".py"):
            tree = ast.parse(path.read_text())
            record.update(
                module_doc=ast.get_docstring(tree),
                definitions=[n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))],
            )
        inventory.append(record)
    out = ROOT / "evidence"
    out.mkdir(exist_ok=True)
    checks = []
    for script, args in [
        ("build_evidence.py", ["--check"]),
        ("build_site_data.py", ["--check"]),
        ("check_consistency.py", []),
    ]:
        command = [sys.executable, "scripts/" + script, *args]
        result = subprocess.run(command, cwd=CHECKOUT, capture_output=True, text=True)
        log = out / (script + ".txt")
        log.write_text(result.stdout + result.stderr)
        checks.append(
            {
                "command": command,
                "returncode": result.returncode,
                "log": str(log.relative_to(ROOT)),
                "sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
                "scope": "publication/data consistency, not agent evolution or safety",
            }
        )
    report = {
        "schema": "ssevoh-upstream-reconnaissance-v1",
        "utc": datetime.now(UTC).isoformat(),
        "repository": pin["repository"],
        "commit": pin["commit"],
        "published_refs": git("ls-remote", "--heads", "--tags", "origin").splitlines(),
        "files": inventory,
        "tracked_file_count": len(files),
        "python_files": [r["path"] for r in inventory if r["path"].endswith(".py")],
        "reviewed_kind": pin["reviewed_kind"],
        "runtime_present": False,
        "interception_boundary": None,
        "baseline_C0_executable": False,
        "finding_basis": [
            "README.md describes companion materials for a survey",
            "CONTRIBUTING.md specifies paper/evidence/site maintenance",
            "all three Python modules generate/check publication data; JS is the reading-list browser",
        ],
        "checks": checks,
        "upstream_clean_after_checks": not git("status", "--porcelain"),
    }
    (out / "reconnaissance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "files"}, indent=2))
    return 0 if all(r["returncode"] == 0 for r in checks) and report["upstream_clean_after_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

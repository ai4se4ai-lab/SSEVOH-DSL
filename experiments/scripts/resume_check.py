"""Verify append-and-skip recovery without generating duplicate records."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--results", required=True)
p.add_argument("--repeats", type=int, required=True)
a = p.parse_args()
root = Path(a.results)
path = root / "deterministic/records.jsonl"
expected = hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(
    [
        sys.executable,
        "-m",
        "ssevoh.benchmark",
        "--output",
        str(path),
        "--baseline",
        "all",
        "--repeats",
        str(a.repeats),
    ],
    check=True,
)
actual = hashlib.sha256(path.read_bytes()).hexdigest()
result = {
    "ok": expected == actual,
    "scope": "deterministic record append-and-skip; not a real Slurm preemption test",
    "before": expected,
    "after": actual,
}
(root / "analysis").mkdir(exist_ok=True)
(root / "analysis/resume-check.json").write_text(json.dumps(result, indent=2) + "\n")
if not result["ok"]:
    raise SystemExit(1)

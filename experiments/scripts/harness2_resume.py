"""Job-side append-and-skip check for the actual controlled comparison worker."""

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
before = hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(
    [
        sys.executable,
        "experiments/scripts/harness2_deterministic.py",
        "--output",
        str(path),
        "--repeats",
        str(a.repeats),
    ],
    check=True,
)
after = hashlib.sha256(path.read_bytes()).hexdigest()
report = {
    "ok": before == after,
    "before": before,
    "after": after,
    "scope": "actual deterministic append-and-skip; not a durable service restart or Slurm preemption proof",
}
(root / "analysis").mkdir(exist_ok=True)
(root / "analysis/resume-check.json").write_text(json.dumps(report, indent=2) + "\n")
if not report["ok"]:
    raise SystemExit(1)

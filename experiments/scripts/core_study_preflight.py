#!/usr/bin/env python3
"""Source-scoped primary-study worker release, separate from core soundness claims."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "experiments/evidence/core-study-readiness.json"


def current(report):
    return report.get("passed") is True and all(
        (ROOT / p).is_file() and hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h
        for p, h in report["source_sha256"].items()
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    core = json.loads((ROOT / "formal/assurance/results/readiness.json").read_text())
    if not current(core):
        raise SystemExit("Core formal evidence is absent or stale")
    if args.record:
        names = [
            "experiments/scripts/llm.py", "experiments/scripts/runtime.py",
            "experiments/scripts/analyze.py", "experiments/scripts/scale.py",
            "experiments/scripts/ablations.py", "experiments/scripts/resume_check.py",
            "experiments/scripts/core_study_preflight.py",
            "hpc/config/profiles/ssevoh-original.json", "hpc/config/models.json",
            "benchmark/scenarios/heartbench-v1.json",
            "experiments/experiment-plan.json",
            "experiments/scripts/qualification_analyze.py",
            "experiments/scripts/request_fidelity.py",
        ]
        names += [str(p.relative_to(ROOT)) for p in sorted((ROOT / "experiments/tests").glob("test_*.py"))]
        hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in names}
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        run = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "experiments/tests", "-v"],
            cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        (REPORT.parent / "primary-worker-tests.txt").write_text(run.stdout)
        report = {
            "schema": "ssevoh-core-study-readiness-v1", "utc": datetime.now(UTC).isoformat(),
            "passed": run.returncode == 0, "source_sha256": hashes,
            "core_readiness_sha256": hashlib.sha256((ROOT / "formal/assurance/results/readiness.json").read_bytes()).hexdigest(),
            "scope": "primary synthetic metadata study; independent operational-reference oracle; no empirical result",
        }
        report["passed"] = current(report)
        REPORT.write_text(json.dumps(report, indent=2) + "\n")
    report = json.loads(REPORT.read_text())
    if not current(report):
        raise SystemExit("Primary experiment worker evidence is absent or stale")
    print(json.dumps({"passed": True, "scope": report["scope"]}))


if __name__ == "__main__":
    main()

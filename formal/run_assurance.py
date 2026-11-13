#!/usr/bin/env python3
"""Reproduce the core readiness evidence. Never enables empirical submission."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from bootstrap_tlc import ensure_tlc

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "formal/assurance/results"


def source_hashes():
    paths = [
        *ROOT.glob("src/ssevoh/*.py"),
        *ROOT.glob("tests/test*.py"),
        *ROOT.glob("formal/**/*.py"),
        *ROOT.glob("formal/model/*"),
        ROOT / "pyproject.toml",
        *ROOT.glob("docs/language/*"),
        ROOT / "formal/assurance/contracts.md",
    ]
    return {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(paths)
        if p.is_file()
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tlc-jar", default=".cache/tla2tools.jar")
    a = p.parse_args()
    jar = ensure_tlc(a.tlc_jar)
    OUT.mkdir(parents=True, exist_ok=True)
    before = source_hashes()
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    commands = [
        ("unit-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
        ("temporal", [sys.executable, "formal/check.py", "--tlc-jar", str(jar)]),
        ("conformance", [sys.executable, "formal/assurance/check_conformance.py"]),
        ("sequences", [sys.executable, "formal/assurance/check_sequences.py"]),
    ]
    runs = []
    for name, command in commands:
        print("Running " + name, flush=True)
        log = OUT / (name + ".log")
        with log.open("w") as stream:
            run = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        runs.append(
            {
                "name": name,
                "command": command,
                "returncode": run.returncode,
                "log": str(log.relative_to(ROOT)),
                "sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
            }
        )
        if run.returncode:
            break
    stable = before == source_hashes()
    passed = len(runs) == len(commands) and all(r["returncode"] == 0 for r in runs) and stable
    reports = {}
    for name, path in [
        ("conformance", "conformance.json"),
        ("sequences", "sequences.json"),
        ("temporal", "temporal/tlc-manifest.json"),
    ]:
        if passed:
            value = json.loads((OUT / path).read_text())
            passed &= value["passed"] and (value.get("complete_domain", True))
            reports[name] = {
                "path": str((OUT / path).relative_to(ROOT)),
                "sha256": hashlib.sha256((OUT / path).read_bytes()).hexdigest(),
            }
    report = {
        "schema": "ssevoh-core-readiness-v1",
        "version": "0.2.0",
        "utc": datetime.now(UTC).isoformat(),
        "passed": passed,
        "source_stable_during_verification": stable,
        "source_sha256": before,
        "runs": runs,
        "evidence": reports,
        "scope": "stable metadata sandbox API; bounded relative soundness/completeness, temporal safety and replay evidence; no machine-checked unbounded refinement theorem",
        "empirical_allowed": False,
        "integration_reconnaissance_allowed": passed,
        "unsupported": [
            "arbitrary artifact/code semantic safety",
            "OS-enforced verifier isolation",
            "multi-component atomic transactions",
            "durable crash recovery",
            "distributed commits",
            "provenance release",
            "liveness",
            "unbounded mechanized refinement proof",
        ],
    }
    (OUT / "readiness.json").write_text(json.dumps(report, indent=2) + "\n")
    gate_path = ROOT / "hpc/config/research-readiness.json"
    gate = json.loads(gate_path.read_text())
    gate.update(
        empirical_allowed=False,
        integration_allowed=passed,
        status="bounded_metadata_core_verified" if passed else "formal_assurance_failed",
        readiness_report=str((OUT / "readiness.json").relative_to(ROOT)),
        reason="Empirical work remains locked. Integration reconnaissance may proceed only for the verified metadata-core scope."
        if passed
        else "Core assurance failed or source changed during verification.",
    )
    gate_path.write_text(json.dumps(gate, indent=2) + "\n")
    print(
        json.dumps(
            {
                "passed": passed,
                "source_stable": stable,
                "report": str(OUT / "readiness.json"),
                "empirical_allowed": False,
            },
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

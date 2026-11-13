#!/usr/bin/env python3
"""Fail closed when the pinned target cannot support a real harness integration."""

import hashlib
import json
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]


def assess(core, pin, inspection, actual_commit, dirty, source_current):
    reasons = []
    if not core.get("passed") or not source_current:
        reasons.append("Core verification absent, failed, or stale")
    if dirty or actual_commit != pin["commit"] or inspection.get("commit") != pin["commit"]:
        reasons.append("Upstream checkout/inspection does not match the clean pinned revision")
    if not pin.get("executable_agent_runtime") or not inspection.get("runtime_present"):
        reasons.append("Pinned upstream is a survey companion with no executable agent evolution runtime")
    if not pin.get("proposal_boundary") or not pin.get("deployment_boundary"):
        reasons.append("No real proposal interception and controlled deployment boundaries identified")
    return {
        "decision": "READY_FOR_INTEGRATION" if not reasons else "BLOCKED_UPSTREAM_TARGET",
        "integration_implementation_allowed": not reasons,
        "empirical_allowed": False,
        "reasons": reasons,
    }


def main():
    core = json.loads((REPO / "formal/assurance/results/readiness.json").read_text())
    pin = json.loads((BASE / "upstream-pin.json").read_text())
    inspection = json.loads((BASE / "evidence/reconnaissance.json").read_text())
    checkout = BASE / "original/upstream"

    def git(*args):
        return subprocess.check_output(["git", "-C", str(checkout), *args], text=True).strip()

    current = all(
        (REPO / p).is_file() and hashlib.sha256((REPO / p).read_bytes()).hexdigest() == h
        for p, h in core["source_sha256"].items()
    )
    report = assess(
        core, pin, inspection, git("rev-parse", "HEAD"), bool(git("status", "--porcelain")), current
    )
    print(json.dumps(report, indent=2))
    return 0 if report["integration_implementation_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

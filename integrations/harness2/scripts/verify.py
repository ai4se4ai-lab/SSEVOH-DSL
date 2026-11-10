#!/usr/bin/env python3
"""Source-scoped verification gate for the real upstream integration; never submits experiments."""

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def hashes():
    paths = [
        *ROOT.glob("adapter/**/*.py"),
        *ROOT.glob("tests/*.py"),
        *ROOT.glob("formal/*"),
        *ROOT.glob("scripts/*.py"),
        ROOT / "upstream-pin.json",
        ROOT / "upstream-runtime.json",
        ROOT / "upstream-runtime.tar.gz",
        *REPO.glob("experiments/scripts/harness2_*.py"),
        *REPO.glob("experiments/scripts/humaneval*.py"),
        REPO / "experiments/scripts/test_humaneval_support.py",
        REPO / "experiments/humaneval/public-v0.1.10.jsonl",
        REPO / "experiments/humaneval/dataset-manifest.json",
        REPO / "experiments/humaneval/protocol.json",
        REPO / "experiments/humaneval/vendor/manifest.json",
        REPO / "hpc/config/profiles/humaneval-smoke.json",
        REPO / "hpc/config/profiles/humaneval-full.json",
        REPO / "hpc/config/profiles/humaneval-evaluate.json",
        REPO / "experiments/scripts/runtime.py",
        REPO / "experiments/scripts/gpu_bootstrap.py",
        REPO / "hpc/slurm/hooks/all.sh",
        REPO / "hpc/scripts/manifest.py",
        REPO / "hpc/scripts/fleet.py",
        REPO / "hpc/scripts/submit_humaneval_preflight.py",
        REPO / "hpc/scripts/humaneval_campaign.py",
        *REPO.glob("hpc/tests/*.py"),
        REPO / "hpc/config/profiles/harness2.json",
        REPO / "hpc/config/profiles/harness2-pilot-v2.json",
        REPO / "hpc/config/profiles/toolrepair-v1.json",
        *REPO.glob("experiments/scripts/toolrepair_*.py"),
        *REPO.glob("experiments/scripts/test_toolrepair_*.py"),
        REPO / "experiments/toolrepair/protocol.json",
        REPO / "hpc/scripts/hpclib.py",
        REPO / "hpc/scripts/harness2_campaign.py",
        REPO / "hpc/scripts/campaign.py",
        REPO / "hpc/scripts/campaignctl.py",
        REPO / "hpc/scripts/measure.py",
        REPO / "hpc/config/models.json",
        REPO / "hpc/config/models.frozen.json",
    ]
    return {
        str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()
    }


def main():
    core = json.loads((REPO / "formal/assurance/results/readiness.json").read_text())
    core_current = core["passed"] and all(
        (REPO / p).exists() and hashlib.sha256((REPO / p).read_bytes()).hexdigest() == h
        for p, h in core["source_sha256"].items()
    )
    if not core_current:
        raise SystemExit("Core verification missing or stale; run make verify first")
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--tlc-jar", required=True)
    a = parser.parse_args()
    up = ROOT / "original/upstream"
    pin = json.loads((ROOT / "upstream-pin.json").read_text())

    def git(*args):
        return subprocess.check_output(["git", "-C", str(up), *args], text=True).strip()

    if git("rev-parse", "HEAD") != pin["commit"] or git("status", "--porcelain"):
        raise SystemExit("Clean pinned upstream required")
    before = hashes()
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(map(str, [REPO, REPO / "src", up, ROOT / "adapter", REPO / "experiments/scripts"])))
    commands = [
        ("upstream-tests", [sys.executable, "-m", "unittest", "discover", "-s", str(up / "tests"), "-v"]),
        (
            "integration-tests",
            [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"],
        ),
        ("coding-adapter-tests", [sys.executable, "-m", "unittest", "discover", "-s", str(REPO / "experiments/scripts"), "-p", "test_humaneval_support.py", "-v"]),
        ("toolrepair-tests", [sys.executable, "-m", "unittest", "discover", "-s", str(REPO / "experiments/scripts"), "-p", "test_toolrepair_*.py", "-v"]),
        ("hpc-pipeline-tests", [sys.executable, "-m", "unittest", "discover", "-s", str(REPO / "hpc/tests"), "-v"]),
        (
            "publication-model",
            [sys.executable, str(ROOT / "formal/check.py"), "--tlc-jar", str(Path(a.tlc_jar).resolve())],
        ),
    ]
    entries = []
    for name, command in commands:
        print("Verifying " + name, flush=True)
        log = ROOT / "evidence" / (name + ".txt")
        with log.open("w") as stream:
            result = subprocess.run(command, cwd=REPO, env=env, stdout=stream, stderr=subprocess.STDOUT)
        match = re.search(r"Ran (\d+) tests", log.read_text())
        entries.append(
            {
                "name": name,
                "command": command,
                "returncode": result.returncode,
                "tests": int(match[1]) if match else None,
                "log": str(log.relative_to(REPO)),
                "sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
            }
        )
        if result.returncode:
            break
    publication = ROOT / "evidence/publication-verification.json"
    passed = (
        len(entries) == len(commands)  # every verification step ran (fail closed on early break)
        and all(r["returncode"] == 0 for r in entries)
        and before == hashes()
        and json.loads(publication.read_text())["passed"]
    )
    report = {
        "schema": "ssevoh-harness2-readiness-v1",
        "utc": datetime.now(UTC).isoformat(),
        "passed": passed,
        "core_current": core_current,
        "upstream_commit": pin["commit"],
        "source_stable": before == hashes(),
        "source_sha256": before,
        "core_readiness_sha256": hashlib.sha256(
            (REPO / "formal/assurance/results/readiness.json").read_bytes()
        ).hexdigest(),
        "runs": entries,
        "scope": "actual unmodified upstream recursion/probe/selection/library with catalog-restricted ledger or data-only non-executable coding adapter and data-only proposers; no generated-code grading isolation is verified here",
        "unsupported": [
            "general OpenCode/Codex executor isolation",
            "arbitrary generated executable behavior",
            "durable automatic recovery",
            "arbitrary multi-target metadata transactions",
            "published professional benchmark replication",
        ],
        "submits_experiments": False,
        "release_authority": "hpc/config/research-readiness.json",
        "next_gate": "source-pinned study preflight, complete smoke graph and measured qualification; no submission by this verifier",
    }
    (ROOT / "evidence/readiness.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ["source_sha256", "runs"]}, indent=2))
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Job-side source/pin verification and an actual admitted upstream execution, before task inference."""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from harness2_support import INTEGRATION, ROOT, ensure_runtime


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    a = p.parse_args()
    if sys.version_info < (3, 12):
        raise SystemExit("Pinned Harness² requires Python >=3.12")
    ensure_runtime()
    for report_path in [
        ROOT / "formal/assurance/results/readiness.json",
        INTEGRATION / "evidence/readiness.json",
    ]:
        report = json.loads(report_path.read_text())
        if not report.get("passed"):
            raise SystemExit("Readiness did not pass: " + str(report_path))
        changed = [
            name
            for name, sha in report["source_sha256"].items()
            if not (ROOT / name).is_file() or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != sha
        ]
        if changed:
            raise SystemExit("Readiness is stale: " + repr(changed))
    from harness2.demo import DemoAdapter
    from ssevoh_harness2.authority import FIXED_SCRIPT, Authority

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        original = DemoAdapter(root / "upstream")
        authority = Authority(root / "authority", original)
        files = {**authority.base, "scripts/summarize.py": FIXED_SCRIPT}
        version = authority.admit(1, files)
        run = authority.execute(version, files, "ledger-1", "preflight")
        answer = (run / "answer.txt").read_text()
        if answer != "Total: 85.15\n":
            raise SystemExit("Admitted executor did not reproduce the independent test answer")
    output = Path(a.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "passed": True,
                "python": sys.version,
                "upstream_commit": json.loads((INTEGRATION / "upstream-pin.json").read_text())["commit"],
                "scope": "source-scoped formal/integration readiness and real catalog execution; no task model prompt",
            },
            indent=2,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

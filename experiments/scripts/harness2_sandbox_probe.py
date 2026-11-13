#!/usr/bin/env python3
"""Critical setup step: prove live Bubblewrap isolation on this compute node before any v2 stream.

Unlike the unit suite, a skipped live test is a failure here: the sandboxed_evidence policy may
only run where the qualified isolation profile actually works.
"""

import argparse
import json
import platform
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

from harness2_support import INTEGRATION, ensure_runtime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    ensure_runtime()
    sys.path.insert(0, str(INTEGRATION / "tests"))
    from ssevoh_harness2.sandbox import available

    diagnostics = []
    report = {"utc": datetime.now(UTC).isoformat(), "host": platform.node(),
              "available": available(diagnostics), "diagnostics": diagnostics}
    if report["available"]:
        import test_sandboxed_evidence as module

        suite = unittest.defaultTestLoader.loadTestsFromTestCase(module.LiveIsolationTests)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        report.update(
            tests=result.testsRun,
            failures=len(result.failures) + len(result.errors),
            skipped=len(result.skipped),
        )
    report["passed"] = bool(
        report["available"] and report.get("tests") and not report.get("failures") and not report.get("skipped")
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    if not report["passed"]:
        raise SystemExit("Live isolation unavailable or failing; sandboxed_evidence streams must not run")


if __name__ == "__main__":
    main()

"""Fresh transfers and stale scheduler observations must remain distinguishable."""

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from live import render  # noqa: E402


class SnapshotFreshness(unittest.TestCase):
    def test_a_recent_fetch_does_not_make_an_old_audit_fresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "hpc/fetched/narval"
            run = folder / "ssevoh-h2-smoke-test"
            run.mkdir(parents=True)
            (folder / "fetch-status.json").write_text(json.dumps({"state": "complete", "last_success_utc": "2026-11-09T22:00:00+00:00"}))
            (run / "audit.json").write_text(json.dumps({"time": "2026-11-09 21:00:00", "rows": [{"state": "PENDING"}]}))
            report = render(root, datetime(2026, 11, 9, 22, 0, 10, tzinfo=UTC))
            self.assertIn("| narval | complete | 10s |", report)
            self.assertIn("3610s **STALE/UNKNOWN**", report)
            self.assertIn("{'PENDING': 1}", report)


if __name__ == "__main__":
    unittest.main()

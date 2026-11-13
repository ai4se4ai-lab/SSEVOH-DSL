"""No live SSH: validate collection isolation, bounded calls and observable freshness."""

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "fleet_monitoring", Path(__file__).resolve().parents[1] / "scripts/fleet.py"
)
fleet = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fleet)


class MonitoringTests(unittest.TestCase):
    def test_one_failed_site_does_not_skip_other_collections(self):
        attempted = []

        def fetch(site, cfg):
            attempted.append(site)
            if site == "narval":
                raise subprocess.TimeoutExpired("rsync", 120)

        with patch.object(fleet, "fetch", fetch):
            self.assertFalse(fleet.fetch_sites(["fir", "narval", "rorqual"], {}))
        self.assertEqual(set(attempted), {"fir", "narval", "rorqual"})

    def test_timeout_preserves_prior_success_and_exposes_partial_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hpc/fetched/narval"
            path.mkdir(parents=True)
            (path / "fetch-status.json").write_text(json.dumps({"last_success_utc": "earlier"}))
            cfg = {
                "username": "test",
                "clusters": {"narval": {"host": "host", "remote_dir": "/project/example"}},
            }
            with (
                patch.object(fleet, "ROOT", Path(tmp)),
                patch.object(fleet, "ssh_args", return_value=["ssh", "host"]),
                patch.object(fleet, "event"),
                patch.object(
                    fleet.subprocess, "run", side_effect=subprocess.TimeoutExpired("rsync", 120)
                ) as run,
            ):
                with self.assertRaises(subprocess.TimeoutExpired):
                    fleet.fetch("narval", cfg)
            status = json.loads((path / "fetch-status.json").read_text())
            self.assertEqual(status["state"], "failed")
            self.assertEqual(status["last_success_utc"], "earlier")
            self.assertTrue(status["partial_refresh"])
            self.assertEqual(run.call_args.kwargs["timeout"], 120)
            self.assertIn("--timeout=45", run.call_args.args[0])

    def test_success_records_fresh_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {"username": "test", "clusters": {"fir": {"host": "host", "remote_dir": "/home/test"}}}
            with (
                patch.object(fleet, "ROOT", Path(tmp)),
                patch.object(fleet, "ssh_args", return_value=["ssh", "host"]),
                patch.object(fleet, "event"),
                patch.object(fleet.subprocess, "run"),
            ):
                fleet.fetch("fir", cfg)
            status = json.loads((Path(tmp) / "hpc/fetched/fir/fetch-status.json").read_text())
            self.assertEqual(status["state"], "complete")
            self.assertFalse(status["partial_refresh"])
            self.assertEqual(status["last_success_utc"], status["finished_utc"])

"""Check unique cached ownership and reject incomplete collected studies; no live SSH."""

import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import harness2_campaign as controller


class CampaignTests(unittest.TestCase):
    def test_lost_submission_acknowledgement_never_retries_automatically(self):
        state = {"phase": "qualification", "qualification_runs": {"fir": ["run"]}, "full_runs": []}
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            controller.validate_resume(state, {"runs": [{"cluster": "fir", "run_id": "run", "submission_state": "requested"}]})
        state["full_runs"] = [{"cluster": "fir", "run_id": "full"}]
        with self.assertRaisesRegex(RuntimeError, "forbidden"):
            controller.validate_resume(state, {"runs": []})

    def test_resumed_controller_executes_one_monitor_cycle_without_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, ledger = root / "campaign.json", root / "fleet.json"
            runs = {site: [site + str(n) for n in range(3)] for site in controller.SITES}
            state = {"phase": "qualification", "started_utc": "2026-11-09T21:00:00+00:00", "deployed": dict.fromkeys(controller.SITES, True), "qualification_runs": runs, "full_runs": [], "caches": {}}
            path.write_text(json.dumps(state))
            ledger.write_text(json.dumps({"runs": [{"cluster": site, "run_id": run, "submission_state": "submitted"} for site, values in runs.items() for run in values]}))
            args = SimpleNamespace(profile="harness2", cycles=1, auto_full=False, interval=60, qualification_minutes=45)
            with (
                patch.object(controller, "PATH", path), patch.object(controller, "STATE", ledger),
                patch.object(controller, "source_current"), patch.object(controller, "config", return_value={}),
                patch.object(controller, "available_models", return_value=[]),
                patch.object(controller, "refresh") as refresh,
                patch.object(controller, "observations", return_value=[]),
                patch.object(controller, "refresh_report"), patch.object(controller, "submit") as submit,
            ):
                controller.run(args)
            refresh.assert_called_once()
            submit.assert_not_called()
            self.assertIn("controller_finished_utc", json.loads(path.read_text()))

    def test_cached_models_have_exactly_one_qualified_owner(self):
        models = json.loads((controller.ROOT / "hpc/config/models.json").read_text())["models"]
        scores = {"fir": {"score": 1}, "rorqual": {"score": 2}}
        caches = {"fir": models, "rorqual": models[:2]}
        with patch.object(controller, "qualify_score", return_value=scores):
            plan = controller.plan_from([], caches)
        owners = [m for values in plan["assignment"].values() for m in values]
        self.assertEqual(sorted(owners), sorted(models))
        self.assertEqual(len(set(owners)), len(models))
        self.assertTrue(all(m in caches[s] for s, values in plan["assignment"].items() for m in values))
        self.assertTrue(all(plan["assignment"].values()))
        self.assertEqual(plan["primary"], "rorqual")

    def test_full_collection_requires_two_task_outcomes_per_stream(self):
        source = controller.ROOT
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "hpc/config").mkdir(parents=True)
            for name in ["models.json", "models.frozen.json"]:
                (root / "hpc/config" / name).write_bytes((source / "hpc/config" / name).read_bytes())
            models = json.loads((root / "hpc/config/models.frozen.json").read_text())["models"]
            streams = [
                {"schema": "harness2-model-stream-v1", "model": model, "model_digest": value["digest"],
                 "repeat": repeat, "status": "ok", "fully_gpu": True, "tasks": []}
                for model, value in models.items() for repeat in range(5)
            ]
            folder = root / "hpc/fetched/fir/run/results"
            folder.mkdir(parents=True)
            with tarfile.open(folder / "deterministic.tar.gz", "w:gz"):
                pass
            state = {"plan": {"primary": "fir"}, "full_runs": [{"cluster": "fir", "run_id": "run"}]}
            with patch.object(controller, "ROOT", root), patch.object(controller, "records", return_value=streams):
                with self.assertRaisesRegex(RuntimeError, "matrix is incomplete"):
                    controller.aggregate(state, {})
            observed = json.loads((root / "artifacts/benchmark-results/harness2-full/completeness.json").read_text())
            self.assertFalse(observed["complete"])
            self.assertEqual(observed["records"], 25)
            self.assertEqual(observed["task_outcomes"], 0)


if __name__ == "__main__":
    unittest.main()

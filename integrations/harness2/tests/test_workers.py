"""Protocol and offline source contracts, with no live model calls or empirical runs."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "experiments/scripts"))
import runtime  # noqa: E402
from harness2.core import tree as ht  # noqa: E402
from harness2.demo import DemoAdapter  # noqa: E402
from harness2_support import ensure_runtime, independent_oracle  # noqa: E402
from ssevoh_harness2.authority import FIXED_SCRIPT  # noqa: E402
from ssevoh_harness2.models import ModelProposer  # noqa: E402


class WorkerContracts(unittest.TestCase):
    def test_executor_prompts_offer_no_copyable_answer_placeholder(self):
        from ssevoh_harness2.models import ModelAdapter

        prompts = []

        def client(prompt, label):
            prompts.append(prompt)
            if label.endswith(".action"):
                return {"response": json.dumps({"action": "run_summary"})}
            return {"response": json.dumps({"answer": "Total: 1.00"})}

        with tempfile.TemporaryDirectory() as directory:
            adapter = ModelAdapter(Path(directory), client)
            task = adapter.tasks()[0]
            adapter.execute(task, None, "placeholder-check")
        self.assertEqual(len(prompts), 2)
        for prompt in prompts:
            self.assertNotIn("final deliverable", prompt)
            self.assertNotIn('"answer":"', prompt.replace(" ", ""))

    def test_model_stream_routes_selection_and_reflection_through_model_client(self):
        source = (REPO / "experiments/scripts/harness2_models.py").read_text()
        self.assertIn("selector_prop=proposer", source)

    def test_analysis_keeps_authority_only_lifecycle_denominators_separate(self):
        import harness2_analyze as analysis

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [
                {"schema": "harness2-controlled-comparison-v1", "condition": "C3", "oracle_allowed": True, "accepted": True, "unsafe_deployed": False, "task_success": True, "seconds": 0.01},
                {"schema": "harness2-controlled-lifecycle-v1", "condition": "C3", "oracle_allowed": False, "accepted": False, "unsafe_deployed": False, "task_success": False, "seconds": 0.01},
            ]
            (root / "fixture.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            with patch.object(sys, "argv", ["analysis", "--root", str(root), "--output", str(root / "analysis")]):
                self.assertEqual(analysis.main(), 0)
            summaries = {r["condition"]: r for r in json.loads((root / "analysis/summary.json").read_text())["summaries"]}
            self.assertEqual(summaries["C3"]["unsafe_attempts"], 0)
            self.assertEqual(summaries["C3:lifecycle"]["unsafe_attempts"], 1)
            self.assertEqual(summaries["C3"]["records"], 1)
            self.assertEqual(summaries["C3"]["legitimate_observations"], 1)
            self.assertAlmostEqual(summaries["C3"]["mean_legitimate_seconds"], 0.01)
            self.assertIsNone(summaries["C3:lifecycle"]["mean_legitimate_seconds"])

    def test_offline_runtime_archive_matches_every_pinned_file(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"SLURM_TMPDIR": directory}):
            target = ensure_runtime()
            self.assertTrue((target / "harness2/core/recursion.py").is_file())
            (target / "unlisted.py").write_text('raise RuntimeError("unverified")')
            with self.assertRaisesRegex(ValueError, "Unpinned"):
                ensure_runtime()

    def test_data_only_retry_does_not_inherit_a_rejected_path_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = DemoAdapter(root / "demo")
            context = root / "context"
            files = ht.read_tree(adapter.substrate.surface(), adapter.base_harness())
            ht.write_tree(adapter.substrate.surface(), files, context / "harness")
            responses = iter(
                [
                    {"response": json.dumps({"files": {"../../policy.json": "bypass"}})},
                    {"response": json.dumps({"files": {"scripts/summarize.py": FIXED_SCRIPT}})},
                ]
            )
            proposer = ModelProposer("stub", lambda prompt, label: next(responses))
            first = proposer.call("Propose a change", context, "inv1.a1")
            second = proposer.call("Repair your rejected change", context, "inv1.a2")
            self.assertTrue((first.workspace / "REJECTED-PATH.json").exists())
            self.assertFalse((second.workspace / "REJECTED-PATH.json").exists())
            self.assertFalse((context / "harness/REJECTED-PATH.json").exists())
            self.assertEqual((second.workspace / "scripts/summarize.py").read_text(), FIXED_SCRIPT)

    def test_policy_oracle_does_not_equate_wrong_task_output_with_unsafe_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter = DemoAdapter(Path(directory))
            base = ht.read_tree(adapter.substrate.surface(), adapter.base_harness())
            self.assertTrue(independent_oracle(base, {}))  # baseline bug is trusted, not a policy escalation
            self.assertTrue(independent_oracle(base, {"scripts/summarize.py": FIXED_SCRIPT}))
            self.assertFalse(independent_oracle(base, {"guardrails.md": "remove constraints"}))
            self.assertFalse(
                independent_oracle(base, {"scripts/summarize.py": 'import os\nos.system("anything")'})
            )
            self.assertIsNone(independent_oracle(base, None))

    def test_larger_context_is_preloaded_before_any_task_prompt(self):
        with patch.object(
            runtime, "api", side_effect=[{}, {"models": [{"digest": "pin", "size": 5, "size_vram": 5}]}]
        ) as api:
            runtime.load_on_gpu("model", "pin", num_ctx=16384)
        self.assertEqual(api.call_args_list[0].args[1]["options"]["num_ctx"], 16384)
        self.assertNotIn("prompt", api.call_args_list[0].args[1])
        with patch.object(
            runtime, "api", side_effect=[{}, {"models": [{"digest": "pin", "size": 5, "size_vram": 4}]}]
        ):
            with self.assertRaises(SystemExit):
                runtime.load_on_gpu("model", "pin", num_ctx=16384)

    def _run_worker_with(self, api, root):
        import harness2_models as worker

        lock = root / "lock.json"
        lock.write_text(json.dumps({"models": {"stub": {"digest": "pin"}}}))
        output = root / "model.jsonl"
        argv = ["worker", "--model", "stub", "--output", str(output), "--lock", str(lock), "--repeats", "2"]
        with (
            patch.object(sys, "argv", argv),
            patch.object(worker, "require_allocation"),
            patch.object(worker, "load_on_gpu"),
            patch.object(worker, "api", api),
            patch.dict(os.environ, {"SLURM_JOB_ID": "verification", "SLURM_TMPDIR": str(root / "node")}),
        ):
            code = worker.main()
        return code, [json.loads(line) for line in output.read_text().splitlines()] if output.exists() else []

    @staticmethod
    def _serving_api(failure):
        def api(endpoint, body=None):
            if endpoint == "tags":
                return {"models": [{"name": "stub", "digest": "pin"}]}
            if endpoint == "ps":
                return {"models": [{"digest": "pin", "size": 10, "size_vram": 10}]}
            raise failure

        return api

    def test_model_server_errors_are_recorded_failures_for_every_seed(self):
        import io
        import urllib.error

        error = urllib.error.HTTPError("http://x/api/generate", 500, "Internal Server Error", {}, io.BytesIO())
        with tempfile.TemporaryDirectory() as directory:
            code, rows = self._run_worker_with(self._serving_api(error), Path(directory))
            raw = sorted((Path(directory) / "model-seed-0" / "raw").glob("*.json"))
            self.assertGreaterEqual(len(raw), 4)  # failed attempts are never overwritten
            self.assertTrue(all(json.loads(f.read_text())["state"] == "failed" for f in raw))
        self.assertEqual(code, 0)
        self.assertEqual([r["repeat"] for r in rows], [0, 1])  # every seed is attempted
        for row in rows:
            self.assertFalse(row["workflow_ok"])
            self.assertTrue(all("HTTPError" in e for e in row["frozen_errors"].values()))
            self.assertFalse(any(t["task_success"] or t["frozen_success"] for t in row["tasks"]))

    def test_lost_model_server_connection_still_aborts(self):
        import urllib.error

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(urllib.error.URLError):
                self._run_worker_with(self._serving_api(urllib.error.URLError("refused")), Path(directory))

    def test_complete_worker_reads_seeded_outputs_and_preserves_incomplete_attempts(self):
        import harness2_models as worker

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "model.jsonl"
            lock = root / "lock.json"
            lock.write_text(json.dumps({"models": {"stub": {"digest": "pin"}}}))
            partial = root / "model-seed-0"
            partial.mkdir()
            (partial / "failed-request.json").write_text("preserve me")

            def api(endpoint, body=None):
                if endpoint == "tags":
                    return {"models": [{"name": "stub", "digest": "pin"}]}
                if endpoint == "ps":
                    return {"models": [{"digest": "pin", "size": 10, "size_vram": 10}]}
                prompt = body["prompt"]
                if prompt.startswith("You are a ledger agent"):
                    response = {"action": "run_summary"}
                elif prompt.startswith("The permitted summary tool returned:"):
                    response = {"answer": prompt.splitlines()[1]}
                elif prompt.startswith('Return JSON {"edits"'):
                    response = {"no_entry": True}
                else:
                    response = {
                        "files": {"scripts/summarize.py": FIXED_SCRIPT},
                        "notes": "Include signed values",
                    }
                return {
                    "response": json.dumps(response),
                    "eval_count": 10,
                    "eval_duration": 1000000,
                    "prompt_eval_count": 100,
                }

            argv = [
                "worker",
                "--model",
                "stub",
                "--output",
                str(output),
                "--lock",
                str(lock),
                "--repeats",
                "1",
            ]
            with (
                patch.object(sys, "argv", argv),
                patch.object(worker, "require_allocation"),
                patch.object(worker, "load_on_gpu"),
                patch.object(worker, "api", api),
                patch.dict(os.environ, {"SLURM_JOB_ID": "verification", "SLURM_TMPDIR": str(root / "node")}),
            ):
                self.assertEqual(worker.main(), 0)
                rows = [json.loads(line) for line in output.read_text().splitlines()]
                self.assertTrue(all(t["task_success"] for t in rows[0]["tasks"]))
                self.assertEqual(rows[0]["frozen_errors"], {})
                self.assertTrue(
                    any(
                        (p / "failed-request.json").read_text() == "preserve me"
                        for p in root.glob("model-seed-0.incomplete-*")
                    )
                )
                before = output.read_bytes()
                self.assertEqual(worker.main(), 0)
                self.assertEqual(output.read_bytes(), before)

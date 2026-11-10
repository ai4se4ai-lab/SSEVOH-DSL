import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ssevoh.benchmark import append_record, evaluate_case, load_cases, read_records
from ssevoh.verification import lifecycle_graph

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hpc/scripts"))
sys.path.insert(0, str(ROOT / "experiments/scripts"))
import fleet  # noqa: E402
from llm import independent_oracle, task_instances  # noqa: E402

from ssevoh.benchmark import proposal  # noqa: E402
from ssevoh.compiler import Parser  # noqa: E402


class ExperimentTests(unittest.TestCase):
    def test_hand_labeled_states_and_decisions(self):
        for case in load_cases():
            for row in evaluate_case(case):
                with self.subTest(scenario=case["id"], step=row["step"]):
                    self.assertTrue(row["correct"])
                    self.assertTrue(row["state_matches"])
                    self.assertTrue(row["reason_matches"])

    def test_independent_oracle_on_known_proposals(self):
        for case, index, step, engine in task_instances():
            spec = Parser(proposal(engine.state, step)).parse()
            with self.subTest(scenario=case["id"], step=index):
                self.assertEqual(
                    independent_oracle(spec, engine, step.get("principal", "alice")),
                    step["expect"] == "accept",
                )

    def test_stale_approval_record_retains_original_proposal_and_journal(self):
        case = next(c for c in load_cases() if c["id"] == "HB09")
        rows = evaluate_case(case)
        self.assertEqual(rows[0]["source"], rows[2]["source"])
        self.assertEqual(rows[1]["journal"], rows[2]["journal"])
        self.assertFalse(rows[2]["accepted"])

    def test_generation_repeats_are_isolated_and_resumable(self):
        import llm
        import runtime

        from ssevoh.benchmark import make_engine

        case = load_cases()[0]
        context = make_engine(case)
        text = proposal(context.state, case["steps"][0])
        prompts = []

        def fake_api(endpoint, body=None):
            if endpoint == "tags":
                return {"models": [{"name": "qwen2.5-coder:7b", "digest": "test-pin"}]}
            if endpoint == "ps":
                return {"models": [{"digest": "test-pin", "size": 100, "size_vram": 100}]}
            if endpoint == "generate":
                if "prompt" not in body:
                    return {"done": True}
                prompts.append(body["prompt"])
                return {"response": text, "eval_count": 42, "eval_duration": 1000000000, "done": True}
            raise AssertionError(endpoint)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "records.jsonl"
            lock = Path(tmp) / "models.json"
            lock.write_text(
                json.dumps(
                    {
                        "models": {"qwen2.5-coder:7b": {"digest": "test-pin"}},
                        "version": "test-runtime",
                        "gpu": "simulated transport only",
                    }
                )
            )
            with (
                patch.object(llm, "api", fake_api),
                patch.object(runtime, "api", fake_api),
                patch.dict(
                    os.environ,
                    {
                        "SLURM_JOB_ID": "test",
                        "CUDA_VISIBLE_DEVICES": "0",
                        "CLUSTER": "test",
                        "RUN_ID": "test",
                    },
                ),
            ):
                llm.run("qwen2.5-coder:7b", out, lock, 2, 1, True)
                self.assertEqual(len(read_records(out)), 2)
                self.assertTrue(all(r["accepted"] and r["oracle_safe"] for r in read_records(out)))
                llm.run("qwen2.5-coder:7b", out, lock, 2, 1, True)
                self.assertEqual(len(prompts), 2)
            self.assertTrue(all("expected_state" not in p and "provenance_events" not in p for p in prompts))

    def test_cpu_fallback_never_receives_a_task_prompt(self):
        import runtime

        calls = []

        def fake_api(endpoint, body=None):
            calls.append((endpoint, body))
            if endpoint == "generate":
                return {"done": True}
            if endpoint == "ps":
                return {"models": [{"digest": "pin", "size": 100, "size_vram": 0}]}
            raise AssertionError(endpoint)

        with patch.object(runtime, "api", fake_api):
            with self.assertRaisesRegex(SystemExit, "no task prompt"):
                runtime.load_on_gpu("qwen2.5-coder:7b", "pin")
        self.assertTrue(all(not body or "prompt" not in body for _, body in calls))

    def test_campaign_requires_completed_steps_not_just_scheduler_label(self):
        from campaign import complete, terminal_failure

        row = {"state": "OK", "slurm_state": "COMPLETED", "steps_ok": 0, "steps_total": 2}
        self.assertFalse(complete({"rows": [row]}))
        row.update(state="PARTIAL", slurm_state="FAILED", steps_ok=1)
        self.assertTrue(terminal_failure({"rows": [row]}))

    def test_paired_analysis_clusters_repeated_generations(self):
        from analyze import paired_comparisons

        groups = {
            model: [
                {
                    "model": model,
                    "scenario": f"task-{task}",
                    "step": 0,
                    "repeat": seed,
                    "task_completion": model == "A",
                    "accepted": True,
                    "oracle_safe": True,
                    "seconds": 1 if model == "A" else 2,
                }
                for task in range(2)
                for seed in range(5)
            ]
            for model in ["A", "B"]
        }
        rows = paired_comparisons(groups)
        completion = next(r for r in rows if r["metric"] == "task_completion")
        self.assertEqual(completion["matched_records"], 10)
        self.assertEqual(completion["matched_tasks"], 2)
        self.assertEqual(completion["effect_mean_task_difference"], 1)
        self.assertIsNone(completion["task_sign_flip_p"])

    def test_empirical_ablation_failures_are_exposed(self):
        from ablations import MODES, evaluate_ablation

        metrics = {}
        for mode in MODES:
            rows = [r for case in load_cases() for r in evaluate_ablation(case, mode)]
            metrics[mode] = (sum(r["false_accept"] for r in rows), sum(r["state_violation"] for r in rows))
        self.assertEqual(metrics["full"], (0, 0))
        for mode in ["dependency_closure", "provenance_checks", "revalidation"]:
            self.assertTrue(any(metrics[mode]), mode)
        # Construction plus independent recovery guards still prevent bad deployment here.
        self.assertEqual(metrics["withdrawal_validation"], (0, 0))
        self.assertEqual(metrics["rollback_conflicts"], (0, 0))

    def test_tlc_python_exact_graph_conformance(self):
        from formal.check import ACTION, parse_dot

        for a, e in [(True, True), (False, True), (True, False), (False, False)]:
            path = ROOT / f"formal/assurance/results/temporal/tlc-{int(a)}-{int(e)}.dot"
            if not path.exists():
                self.skipTest("TLC graphs not available; run make verify")
            nodes, edges = parse_dot(path.read_text())
            expected_nodes, expected_edges = lifecycle_graph(a, e)
            self.assertEqual(nodes, expected_nodes)
            self.assertEqual(edges, {(u, ACTION[action], v) for u, action, v in expected_edges})

    def test_partial_record_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.jsonl"
            path.write_text('{"task":1}\n{"task":')
            self.assertEqual(read_records(path), [{"task": 1}])
            append_record(path, {"task": 2})
            self.assertEqual(read_records(path), [{"task": 1}, {"task": 2}])

    def test_complete_record_without_final_newline_resumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.jsonl"
            path.write_text('{"task":1}')
            self.assertEqual(read_records(path), [{"task": 1}])
            append_record(path, {"task": 2})
            self.assertEqual(read_records(path), [{"task": 1}, {"task": 2}])

    def measurements(self, sites=("fir", "narval", "rorqual")):
        return [
            dict(
                cluster=site,
                run_id=f"{site}-{i}",
                model=model,
                success=True,
                fully_gpu=True,
                recovery_ok=True,
                transfer_ok=True,
                queue_seconds=10,
                startup_seconds=5,
                generation_seconds=10,
                transfer_seconds=2,
            )
            for site in sites
            for i in range(3)
            for model in ["qwen2.5-coder:7b", "phi4:14b"]
        ]

    def test_no_fabricated_qualification(self):
        self.assertEqual(fleet.qualify_score([]), {})
        with self.assertRaises(ValueError):
            fleet.make_plan([])

    def test_repeats_are_not_independent_queue_trials(self):
        rows = self.measurements(("fir",))
        for row in rows:
            row["run_id"] = "one-allocation"
        self.assertEqual(fleet.qualify_score(rows), {})

    def test_qualification_failure_excludes_site(self):
        rows = self.measurements(("fir",))
        rows[0]["transfer_ok"] = False
        self.assertEqual(fleet.qualify_score(rows), {})

    def test_disjoint_plan(self):
        plan = fleet.make_plan(self.measurements())
        assigned = [m for models in plan["assignment"].values() for m in models]
        self.assertEqual(len(assigned), 5)
        self.assertEqual(len(set(assigned)), 5)
        self.assertTrue(all(plan["assignment"].values()))


if __name__ == "__main__":
    unittest.main()

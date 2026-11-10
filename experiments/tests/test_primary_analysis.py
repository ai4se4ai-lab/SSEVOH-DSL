"""Scaling observations must survive analysis beside admission/model records."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze import analyze  # noqa: E402
from scale import trial  # noqa: E402


class PrimaryAnalysis(unittest.TestCase):
    def test_invalid_or_empty_outputs_are_not_evaluable_unsafe_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [
                {"model": "stub", "scenario": "case", "repeat": 0, "accepted": False, "oracle_safe": None,
                 "false_accept": False, "false_reject": False, "seconds": 1, "syntax_valid": False,
                 "raw": {"response": "", "thinking": "still reasoning", "done_reason": "length"}},
                {"model": "stub", "scenario": "case", "repeat": 1, "accepted": False, "oracle_safe": None,
                 "false_accept": False, "false_reject": False, "seconds": 1, "syntax_valid": False,
                 "raw": {"response": "```dsl\nwrong format\n```", "done_reason": "stop"}},
            ]
            (root / "rows.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            result = analyze(root, root / "analysis")[0]
            self.assertEqual(result["unsafe_n"], 0)
            self.assertIsNone(result["false_accept_rate"])
            self.assertEqual(result["independently_labelled_n"], 0)
            self.assertEqual(result["empty_response_n"], 1)
            self.assertEqual(result["fenced_response_n"], 1)
            self.assertEqual(result["length_limited_n"], 1)

    def test_concurrent_scaling_trial_keeps_one_winner_and_all_conflicts(self):
        row = trial(5, "chain", 0, 4)
        self.assertEqual(row["commit_winners"], 1)
        self.assertEqual(row["conflicts_rejected"], 3)
        self.assertEqual(row["inactive"], 4)

    def test_scaling_only_input_retains_shapes_and_repeats(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [
                {"scenario": shape + "-10", "size": 10, "shape": shape, "repeat": repeat,
                 "seconds": 0.02 + repeat * 0.02, "compile_assurance_seconds": 0.01,
                 "deploy_seconds": 0.01 + repeat * 0.02, "peak_tracemalloc_bytes": 1024 + repeat,
                 "inactive": 9}
                for shape in ["chain", "star"] for repeat in range(2)
            ]
            (root / "rows.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            self.assertEqual(analyze(root, root / "analysis"), [])
            summary = json.loads((root / "analysis/summary.json").read_text())
            self.assertEqual(len(summary["scaling"]), 2)
            self.assertTrue(all(r["n"] == 2 for r in summary["scaling"]))
            self.assertAlmostEqual(summary["scaling"][0]["median_seconds"], 0.03)
            self.assertEqual(summary["scaling"][0]["max_peak_tracemalloc_bytes"], 1025)
            self.assertTrue((root / "analysis/scaling.csv").is_file())


if __name__ == "__main__":
    unittest.main()

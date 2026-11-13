"""Independent jobs and comparable samples must not be inflated by repeated outputs."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from qualification_analyze import analyze  # noqa: E402


class QualificationAnalysis(unittest.TestCase):
    def test_three_generations_are_one_job_and_invalid_agreement_is_explicit(self):
        measurement = {"study": "core", "cluster": "fir", "run_id": "run", "model": "model",
                       "success": True, "fully_gpu": True, "transfer_ok": True, "recovery_ok": True,
                       "queue_seconds": 1, "job_elapsed_seconds": 10, "transfer_seconds": 1}
        sample = {"model": "model", "trial": 1, "scenario": "case", "step": 0, "repeat": 0,
                  "model_digest": "digest", "worker_source": "source", "prompt_hash": "prompt",
                  "options": {"seed": 1}, "runtime": "runtime", "response_sha256": "response",
                  "accepted": False, "syntax_valid": False}
        value = {"measurements": [measurement] * 3, "core_samples": [dict(sample, cluster="fir"), dict(sample, cluster="rorqual")], "selection_frozen": {}}
        result = analyze(value)
        self.assertEqual(result["infrastructure"][0]["independent_jobs"], 1)
        self.assertEqual(result["matched_core_outputs"][0]["both_syntax_invalid"], 1)
        value["core_samples"][1]["model_digest"] = "different"
        result = analyze(value)
        self.assertEqual(result["matched_core_outputs"], [])
        self.assertEqual(len(result["excluded_pairs"]), 1)


if __name__ == "__main__":
    unittest.main()

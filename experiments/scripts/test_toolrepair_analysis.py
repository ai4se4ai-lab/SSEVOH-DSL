"""Prespecified ToolRepair analysis on synthetic records (no model data)."""

import unittest

import toolrepair_analyze as an
import toolrepair_families as tr

ARMS = an.ARMS


def rows(success, injected_exec, natural_unsafe=0):
    out = []
    for f in tr.FAMILIES:
        for arm in ARMS:
            for seed in range(3):
                out.append({
                    "schema": "toolrepair-stream-v1", "family": f.name, "arm": arm, "model": "m", "repeat": seed,
                    "tasks": [{"task_success": success(f.name, arm, seed, i), "frozen_success": False,
                               "value_correct": success(f.name, arm, seed, i)} for i in range(3)],
                    "proposal_assessments": [{"injected": False, "unsafe_executed": arm == "original" and natural_unsafe}],
                    "injection": {"executed": injected_exec(arm), "limitation_probe": False},
                })
    return out


class AnalysisContracts(unittest.TestCase):
    def test_designed_effects_are_detected(self):
        success = lambda f, arm, seed, i: arm != "catalog" and i > 0  # noqa: E731
        result = an.analyze(rows(success, lambda arm: arm == "original", natural_unsafe=1))
        self.assertTrue(result["complete_design"])
        self.assertTrue(result["H1_superiority_A3_vs_A2"]["supported"])
        self.assertTrue(result["H3_noninferiority_A3_vs_A1"]["supported"])
        self.assertTrue(result["H2_safety"]["supported"])
        self.assertLess(result["H4_learning_A3_by_task_position"][0], result["H4_learning_A3_by_task_position"][2])

    def test_null_and_harm_are_not_called_supported(self):
        worse = lambda f, arm, seed, i: arm == "original"  # noqa: E731
        result = an.analyze(rows(worse, lambda arm: True))
        self.assertFalse(result["H1_superiority_A3_vs_A2"]["supported"])
        self.assertFalse(result["H3_noninferiority_A3_vs_A1"]["supported"])
        self.assertFalse(result["H2_safety"]["supported"])

    def test_clopper_pearson_upper_bound(self):
        self.assertAlmostEqual(an.clopper_pearson_upper(0, 60), 0.0487, places=3)


if __name__ == "__main__":
    unittest.main()

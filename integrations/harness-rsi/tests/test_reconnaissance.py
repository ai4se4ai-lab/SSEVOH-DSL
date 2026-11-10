"""Verify target identity and fail-closed prerequisites, not an agent integration."""

import importlib.util
import json
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("target_readiness", BASE / "scripts/check_readiness.py")
readiness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readiness)


class ReconnaissanceTests(unittest.TestCase):
    def setUp(self):
        self.pin = json.loads((BASE / "upstream-pin.json").read_text())
        self.inspection = json.loads((BASE / "evidence/reconnaissance.json").read_text())

    def test_every_pinned_python_source_has_reviewed_publication_role(self):
        self.assertEqual(self.inspection["tracked_file_count"], 42)
        self.assertEqual(
            set(self.inspection["python_files"]),
            {"scripts/build_evidence.py", "scripts/build_site_data.py", "scripts/check_consistency.py"},
        )
        self.assertEqual(self.inspection["commit"], self.pin["commit"])
        self.assertFalse(self.inspection["runtime_present"])
        self.assertFalse(self.inspection["baseline_C0_executable"])

    def test_original_checks_are_preserved_and_passed(self):
        self.assertEqual(len(self.inspection["checks"]), 3)
        self.assertTrue(all(c["returncode"] == 0 for c in self.inspection["checks"]))
        self.assertTrue(self.inspection["upstream_clean_after_checks"])

    def test_survey_target_never_authorizes_adapter_or_experiments(self):
        result = readiness.assess(
            {"passed": True}, self.pin, self.inspection, self.pin["commit"], False, True
        )
        self.assertEqual(result["decision"], "BLOCKED_UPSTREAM_TARGET")
        self.assertFalse(result["integration_implementation_allowed"])
        self.assertFalse(result["empirical_allowed"])

    def test_stale_core_is_reported_as_a_separate_blocker(self):
        result = readiness.assess(
            {"passed": True}, self.pin, self.inspection, self.pin["commit"], False, False
        )
        self.assertTrue(any("stale" in r for r in result["reasons"]))
        self.assertFalse(result["integration_implementation_allowed"])

    def test_unreviewed_upstream_cannot_inherit_inspection(self):
        result = readiness.assess({"passed": True}, self.pin, self.inspection, "different", True, True)
        self.assertTrue(any("pinned revision" in r for r in result["reasons"]))
        self.assertFalse(result["integration_implementation_allowed"])

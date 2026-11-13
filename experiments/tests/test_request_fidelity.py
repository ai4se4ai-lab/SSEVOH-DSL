"""Evidence omission and unrelated snapshot changes cannot count as full request fidelity."""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from request_fidelity import contexts, matches  # noqa: E402


class RequestFidelity(unittest.TestCase):
    def test_evidence_omission_changes_fidelity_even_when_transition_fields_match(self):
        key, (_, evolution, source) = next((k, v) for k, v in contexts().items() if v[1].requires)
        row = {"scenario": key[0], "step": key[1], "raw": {"response": source}}
        self.assertTrue(evolution.requires)
        self.assertTrue(matches(row))  # a faithfully requested forbidden change is still forbidden
        row["raw"]["response"] = re.sub(r"requires \[[^]]*\];", "requires [];", source)
        self.assertFalse(matches(row))

    def test_snapshot_and_conditions_are_checked_without_enforcing_arbitrary_names(self):
        key, (state, evolution, source) = next(iter(contexts().items()))
        row = {"scenario": key[0], "step": key[1], "raw": {"response": source.replace("harness heartbench", "harness another_name")}}
        self.assertTrue(matches(row))
        row["raw"]["response"] = source.replace("mutable true", "mutable false", 1)
        self.assertFalse(matches(row))
        self.assertNotIn(evolution.target, state.inactive)
        row["raw"]["response"] = source.replace("expect any", "expect inactive")
        self.assertFalse(matches(row))


if __name__ == "__main__":
    unittest.main()

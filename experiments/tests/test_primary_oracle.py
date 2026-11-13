"""Primary-study labels must reflect protected dependents and version history."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/scripts"))
from llm import independent_oracle  # noqa: E402

from ssevoh.assurance import Rejected, SandboxEngine  # noqa: E402
from ssevoh.benchmark import load_cases, make_engine, proposal  # noqa: E402
from ssevoh.compiler import Parser  # noqa: E402
from ssevoh.model import Component, State  # noqa: E402
from ssevoh.policy import Policy  # noqa: E402


class PrimaryOracle(unittest.TestCase):
    def test_every_fixture_prefix_matches_the_reference_label(self):
        checked = 0
        for case in load_cases():
            engine = make_engine(case)
            for step in case["steps"]:
                if step.get("mode", "normal") != "normal":
                    continue
                source = proposal(engine.state, step)
                principal = step.get("principal", "alice")
                label = independent_oracle(Parser(source).parse(), engine, principal)
                self.assertEqual(label, step["expect"] == "accept", case["id"])
                if label:
                    engine.deploy(engine.approve(source, principal))
                checked += 1
        self.assertEqual(checked, 20)

    def test_mutable_verifier_dependent_is_still_protected(self):
        engine = SandboxEngine(
            State((Component("a", "tool", 1), Component("v", "verifier", 1, depends=("a",)))),
            Policy(frozenset({("alice", "a", "update")})),
        )
        source = proposal(engine.state, {"target": "a"})
        self.assertFalse(independent_oracle(Parser(source).parse(), engine, "alice"))
        with self.assertRaises(Rejected):
            engine.approve(source, "alice")

    def test_clean_name_does_not_launder_a_withdrawn_version_origin(self):
        components = (Component("a", "tool", 1), Component("b", "skill", 1))
        grants = frozenset(("alice", c.name, op) for c in components for op in ("update", "withdraw", "rollback"))
        engine = SandboxEngine(State(components), Policy(grants))
        for step in [
            {"target": "b", "parents": ["a"]},
            {"target": "a", "operation": "withdraw"},
            {"target": "b", "operation": "rollback", "version": 1},
        ]:
            engine.deploy(engine.approve(proposal(engine.state, step), "alice"))
        source = proposal(engine.state, {"target": "b", "operation": "rollback", "version": 2})
        self.assertFalse(independent_oracle(Parser(source).parse(), engine, "alice"))
        with self.assertRaises(Rejected):
            engine.approve(source, "alice")


if __name__ == "__main__":
    unittest.main()

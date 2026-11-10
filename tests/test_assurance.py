"""Security regressions for the trusted metadata service and its replay boundary."""

import json
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

from test_framework import engine, source

from ssevoh.assurance import Rejected, replay_journal, validate_journal
from ssevoh.model import Component, State, digest
from ssevoh.policy import Policy

ROOT = Path(__file__).resolve().parents[1]


class AssuranceTests(unittest.TestCase):
    def test_host_inputs_are_frozen_and_canonical(self):
        names = ["b", "a"]
        cs = [Component("x", "skill", 1, capabilities=names)]
        state = State(cs)
        grants = {("alice", "x", "update")}
        policy = Policy(grants)
        names.append("root")
        cs.clear()
        grants.clear()
        self.assertEqual(state.components[0].capabilities, ("a", "b"))
        self.assertIn(("alice", "x", "update"), policy.grants)
        self.assertEqual(
            State((Component("b", "skill", 1), Component("a", "skill", 1))),
            State((Component("a", "skill", 1), Component("b", "skill", 1))),
        )
        with self.assertRaises(ValueError):
            Component("x", "skill", True)

    def test_protected_kind_dependent_is_not_quarantined(self):
        for kind in ["policy", "verifier"]:
            e = engine((Component("a", "skill", 1), Component("b", kind, 1, True, ("a",))))
            before = e.state
            with self.assertRaisesRegex(Rejected, "protected dependent"):
                e.approve(source(e.state), "alice")
            self.assertEqual(before, e.state)

    def test_reentrant_validator_cannot_rebind_approval(self):
        def nested(candidate, proposal):
            if proposal.target == "a":
                e.deploy(e.approve(source(e.state, "b"), "alice"))
            return True

        e = engine((Component("a", "skill", 1), Component("b", "skill", 1)), {"nested": nested})
        with self.assertRaisesRegex(Rejected, "context"):
            e.approve(source(e.state, requires=("nested",)), "alice")
        self.assertEqual(e.state.mapping()["a"].version, 1)
        self.assertEqual(e.state.mapping()["b"].version, 2)
        self.assertEqual(len(e.journal), 1)

    def test_policy_change_during_validation_rejected(self):
        def mutate(candidate, proposal):
            e._policy = Policy(frozenset())
            return True

        e = engine(validators={"guard": mutate})
        with self.assertRaisesRegex(Rejected, "context"):
            e.approve(source(e.state, requires=("guard",)), "alice")
        self.assertEqual(e.state.revision, 0)

    def test_registry_replacement_invalidates_approval(self):
        e = engine()
        a = e.approve(source(e.state), "alice")
        e._validators = MappingProxyType({"structure": lambda s, p: True})
        with self.assertRaisesRegex(Rejected, "REVALIDATION"):
            e.deploy(a)
        self.assertEqual(e.state.revision, 0)

    def test_history_change_invalidates_approval(self):
        e = engine()
        a = e.approve(source(e.state), "alice")
        e._history[("a", 7)] = Component("a", "skill", 7)
        with self.assertRaisesRegex(Rejected, "REVALIDATION"):
            e.deploy(a)

    def test_candidate_and_origins_are_bound(self):
        for field in ["candidate", "origins"]:
            e = engine()
            a = e.approve(source(e.state), "alice")
            if field == "candidate":
                stored, candidate, ev, p = e._approvals[a.token]
                e._approvals[a.token] = (stored, replace(candidate, revision=99), ev, p)
            else:
                e._approved_origins[a.token] = frozenset()
            with self.assertRaisesRegex(Rejected, "binding"):
                e.deploy(a)
            self.assertEqual(e.state.revision, 0)

    def test_withdrawn_version_cannot_be_laundered_through_parent_name(self):
        e = engine((Component("a", "memory", 1), Component("b", "skill", 1, parents=("a",))))
        initial = e.state
        for text in [source(e.state)]:
            e.deploy(e.approve(text, "alice"))
        e.deploy(e.approve(source(e.state, "b"), "alice"))
        e.deploy(e.approve(source(e.state, operation="withdraw", version=2), "alice"))
        e.deploy(e.approve(source(e.state, operation="rollback", version=1), "alice"))
        # a's name now points at clean a1; b2 still derives from withdrawn a2.
        with self.assertRaisesRegex(Rejected, "withdrawn version in active provenance"):
            e.approve(source(e.state, "b"), "alice")
        e.deploy(e.approve(source(e.state, "b", "rollback", 1), "alice"))
        self.assertEqual(e.state.inactive, frozenset())
        self.assertEqual(
            replay_journal(initial, e.journal, e._policy, expected_head=e.journal[-1]["hash"]), e.state
        )

    def test_journal_replay_rejects_rehashed_semantic_forgery(self):
        e = engine()
        initial = e.state
        e.deploy(e.approve(source(e.state), "alice"))
        journal = json.loads(json.dumps(e.journal))
        journal[0]["source"] = journal[0]["source"].replace("to 2;", "to 3;")
        journal[0]["hash"] = digest({k: v for k, v in journal[0].items() if k != "hash"})
        self.assertTrue(validate_journal(journal))
        self.assertFalse(validate_journal(journal, e.journal[-1]["hash"]))
        with self.assertRaisesRegex(Rejected, "source/policy"):
            replay_journal(initial, journal, e._policy)

    def test_journal_enforces_state_continuity(self):
        e = engine()
        initial = e.state
        e.deploy(e.approve(source(e.state), "alice"))
        e.deploy(e.approve(source(e.state, "b"), "alice"))
        journal = json.loads(json.dumps(e.journal))
        journal[1]["before"] = "bad"
        journal[1]["hash"] = digest({k: v for k, v in journal[1].items() if k != "hash"})
        self.assertFalse(validate_journal(journal, initial_state_hash=initial.fingerprint()))
        self.assertEqual(
            replay_journal(initial, e.journal, e._policy, expected_head=e.journal[-1]["hash"]), e.state
        )

    def test_rejection_is_audited_without_deployment(self):
        e = engine()
        with self.assertRaises(ValueError):
            e.approve(source(e.state), "mallory")
        self.assertEqual(e.decision_log[-1]["status"], "REJECTED")
        self.assertFalse(e.journal)
        event = e.decision_log[-1]
        self.assertEqual(event["hash"], digest({k: v for k, v in event.items() if k != "hash"}))

    def test_invalid_approval_type_fails_closed(self):
        e = engine()
        for obj in [None, {}, "approval"]:
            with self.assertRaisesRegex(Rejected, "invalid approval"):
                e.deploy(obj)
        self.assertEqual(e.state.revision, 0)

    def test_empirical_submit_remains_locked(self):
        config = json.loads((ROOT / "hpc/config/research-readiness.json").read_text())
        if config["empirical_allowed"]:
            self.skipTest("explicit empirical readiness enabled")
        result = subprocess.run(
            [sys.executable, "hpc/slurm/submit.py", "--help"], cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        result = subprocess.run(
            [sys.executable, "hpc/scripts/campaignctl.py", "start"], cwd=ROOT, capture_output=True, text=True
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("formal", result.stdout + result.stderr)

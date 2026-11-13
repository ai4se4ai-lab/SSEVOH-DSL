import concurrent.futures
import random
import unittest
from dataclasses import replace
from pathlib import Path

from ssevoh.assurance import Rejected, SandboxEngine, validate_journal
from ssevoh.compiler import Diagnostic, compile_source
from ssevoh.model import Component, State, structural_errors
from ssevoh.policy import Policy
from ssevoh.verification import verification_suite


def source(
    state,
    target="a",
    operation="update",
    version=None,
    requires=(),
    depends=None,
    parents=None,
    capabilities=None,
    precondition="any",
):
    c = state.mapping()[target]

    def listing(xs):
        return "[" + ",".join(xs) + "]"

    lines = ["harness test {"]
    for x in state.components:
        lines.append(
            f"component {x.name} {x.kind} {{ version {x.version}; mutable {str(x.mutable).lower()}; "
            f"depends {listing(x.depends)}; parents {listing(x.parents)}; "
            f"capabilities {listing(x.capabilities)}; }}"
        )
    version = version if version is not None else c.version + 1
    lines.append(
        f"evolution change {{ operation {operation}; target {target}; from {c.version}; to {version}; "
        f"depends {listing(c.depends if depends is None else depends)}; "
        f"parents {listing(c.parents if parents is None else parents)}; "
        f"capabilities {listing(c.capabilities if capabilities is None else capabilities)}; "
        f"requires {listing(requires)}; expect {precondition}; "
        f"ensure {'inactive' if operation == 'withdraw' else 'active'}; }} }}"
    )
    return "\n".join(lines)


def engine(components=None, validators=None, grants=None):
    components = components or (Component("a", "skill", 1), Component("b", "workflow", 1, depends=("a",)))
    if grants is None:
        grants = frozenset(
            ("alice", c.name, op) for c in components for op in ["update", "withdraw", "rollback"]
        )
    return SandboxEngine(State(tuple(components)), Policy(grants), validators)


class CompilerTests(unittest.TestCase):
    def test_examples(self):
        for path in Path("examples").glob("*/*.sse"):
            with self.subTest(path=path):
                self.assertTrue(compile_source(path.read_text()).evolution)

    def test_syntax_location(self):
        with self.assertRaises(Diagnostic) as ctx:
            compile_source("harness x {\n @ }")
        self.assertEqual((ctx.exception.category, ctx.exception.line, ctx.exception.column), ("syntax", 2, 2))

    def test_types(self):
        text = source(engine().state).replace("version 1", "version false", 1)
        with self.assertRaisesRegex(Diagnostic, "type"):
            compile_source(text)

    def test_unknown_type(self):
        with self.assertRaisesRegex(Diagnostic, "type"):
            compile_source(source(engine().state).replace("a skill", "a executable"))

    def test_unknown_reference(self):
        with self.assertRaisesRegex(Diagnostic, "semantic"):
            compile_source(source(engine().state, depends=("missing",)))

    def test_duplicate_component(self):
        text = source(engine().state).replace("component b workflow", "component a workflow")
        with self.assertRaises(Diagnostic):
            compile_source(text)

    def test_unknown_field(self):
        with self.assertRaisesRegex(Diagnostic, "unknown field"):
            compile_source(
                source(engine().state).replace("operation update;", "operation update; grant admin;")
            )

    def test_cycle(self):
        with self.assertRaisesRegex(Rejected, "cycle"):
            e = engine()
            e.approve(source(e.state, depends=("b",)), "alice")

    def test_static_policy(self):
        e = engine()
        with self.assertRaisesRegex(Diagnostic, "policy"):
            compile_source(source(e.state), e._policy, "mallory")

    def test_rename_metamorphism(self):
        e = engine()
        spec = compile_source(source(e.state))
        renamed = compile_source(
            source(e.state)
            .replace("component a ", "component x ")
            .replace("target a;", "target x;")
            .replace("[a]", "[x]")
        )
        self.assertEqual(len(spec.components), len(renamed.components))


class EnforcementTests(unittest.TestCase):
    def test_end_to_end(self):
        e = engine()
        approval = e.approve(source(e.state), "alice")
        e.deploy(approval)
        self.assertEqual(e.state.mapping()["a"].version, 2)
        self.assertIn("b", e.state.inactive)
        self.assertTrue(validate_journal(e.journal))

    def test_unauthorized(self):
        e = engine()
        with self.assertRaisesRegex(Diagnostic, "permission"):
            e.approve(source(e.state), "mallory")

    def test_protected(self):
        e = engine((Component("a", "configuration", 1, False),))
        with self.assertRaisesRegex(Diagnostic, "immutable"):
            e.approve(source(e.state), "alice")

    def test_policy_component_even_mutable(self):
        e = engine((Component("a", "policy", 1),))
        with self.assertRaisesRegex(Diagnostic, "protected"):
            e.approve(source(e.state), "alice")

    def test_missing_evidence(self):
        e = engine()
        with self.assertRaisesRegex(Rejected, "missing independent"):
            e.approve(source(e.state, requires=("llm_claim",)), "alice")

    def test_negative_evidence(self):
        e = engine(validators={"test": lambda s, p: False})
        with self.assertRaisesRegex(Rejected, "negative"):
            e.approve(source(e.state, requires=("test",)), "alice")

    def test_validator_exception(self):
        def fail(s, p):
            raise RuntimeError("failure")

        e = engine(validators={"test": fail})
        with self.assertRaisesRegex(Rejected, "validator failed"):
            e.approve(source(e.state, requires=("test",)), "alice")

    def test_forged_approval(self):
        e = engine()
        a = e.approve(source(e.state), "alice")
        with self.assertRaisesRegex(Rejected, "forged"):
            e.deploy(replace(a, proposal_hash="forged"))
        self.assertEqual(e.state.revision, 0)

    def test_replay(self):
        e = engine()
        a = e.approve(source(e.state), "alice")
        e.deploy(a)
        with self.assertRaisesRegex(Rejected, "consumed"):
            e.deploy(a)

    def test_stale_approval(self):
        e = engine()
        a = e.approve(source(e.state), "alice")
        b = e.approve(source(e.state, "b"), "alice")
        e.deploy(a)
        with self.assertRaisesRegex(Rejected, "REVALIDATION"):
            e.deploy(b)

    def test_withdrawal_descendants_and_mixed_parent(self):
        e = engine(
            (
                Component("a", "memory", 1),
                Component("b", "memory", 1),
                Component("c", "skill", 1, parents=("a", "b")),
            )
        )
        e.deploy(e.approve(source(e.state, operation="withdraw", version=1), "alice"))
        self.assertEqual(e.state.inactive, {"a", "c"})
        self.assertIn("c", e.state.mapping())
        self.assertNotIn("b", e.state.inactive)

    def test_rollback_withdrawn(self):
        e = engine()
        e.deploy(e.approve(source(e.state, operation="withdraw", version=1), "alice"))
        with self.assertRaisesRegex(Rejected, "withdrawn"):
            e.approve(source(e.state, operation="rollback", version=1), "alice")

    def test_safe_rollback(self):
        e = engine()
        e.deploy(e.approve(source(e.state), "alice"))
        e.deploy(e.approve(source(e.state, operation="rollback", version=1), "alice"))
        self.assertEqual(e.state.mapping()["a"].version, 1)

    def test_invalid_rollback_ancestor(self):
        e = engine()
        e.deploy(e.approve(source(e.state, operation="withdraw", version=1), "alice"))
        with self.assertRaisesRegex(Rejected, "inactive dependency"):
            e.approve(source(e.state, "b", "rollback", 1), "alice")

    def test_rollback_cannot_restore_reduced_capabilities(self):
        e = engine((Component("a", "tool", 1, capabilities=("read", "write")),))
        e.deploy(e.approve(source(e.state, capabilities=("read",)), "alice"))
        with self.assertRaisesRegex(Rejected, "expand capabilities"):
            e.approve(source(e.state, operation="rollback", version=1), "alice")
        self.assertEqual(e.state.mapping()["a"].capabilities, ("read",))

    def test_concrete_verifier_uses_trusted_base_capabilities(self):
        from ssevoh.verification import verify_instance

        e = engine((Component("a", "tool", 1, capabilities=("read",)),))
        spec = compile_source(source(e.state))
        candidate = State((Component("a", "tool", 2, capabilities=("read", "write")),), revision=1)
        result = verify_instance(candidate, e._policy, "alice", spec.evolution, e.state)
        self.assertFalse(result["safe"])
        self.assertIn("privilege", result["counterexample"])

    def test_privilege_expansion(self):
        e = engine()
        with self.assertRaisesRegex(Diagnostic, "capability"):
            e.approve(source(e.state, capabilities=("root",)), "alice")

    def test_protected_dependent(self):
        e = engine((Component("a", "skill", 1), Component("b", "workflow", 1, False, ("a",))))
        with self.assertRaisesRegex(Rejected, "protected dependent"):
            e.approve(source(e.state), "alice")

    def test_partial_failure_and_retry(self):
        e = engine()
        a = e.approve(source(e.state), "alice")
        before = e.state
        with self.assertRaises(Rejected):
            e.deploy(a, fail_before_commit=True)
        self.assertEqual(e.state, before)
        self.assertEqual(e.journal, ())
        e.deploy(a)
        self.assertEqual(e.state.revision, 1)

    def test_concurrency_one_winner(self):
        e = engine()
        approvals = [e.approve(source(e.state), "alice") for _ in range(8)]

        def run(a):
            try:
                e.deploy(a)
                return True
            except Rejected:
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(run, approvals)), 1)
        self.assertEqual(e.state.revision, 1)

    def test_journal_tampering(self):
        e = engine()
        e.deploy(e.approve(source(e.state), "alice"))
        journal = list(e.journal)
        journal[0]["target"] = "other"
        self.assertFalse(validate_journal(journal))
        self.assertTrue(validate_journal(e.journal))

    def test_snapshot_lie(self):
        e = engine()
        text = source(e.state).replace("component b workflow", "component b skill")
        with self.assertRaisesRegex(Rejected, "snapshot"):
            e.approve(text, "alice")

    def test_random_sequences_invariants(self):
        rng = random.Random(481)
        cs = tuple(Component(f"c{i}", "skill", 1, depends=(f"c{i - 1}",) if i else ()) for i in range(20))
        e = engine(cs)
        for _ in range(150):
            target = rng.choice(cs).name
            try:
                e.deploy(e.approve(source(e.state, target), "alice"))
            except ValueError:
                pass
            self.assertFalse(structural_errors(e.state))
        self.assertTrue(validate_journal(e.journal))

    def test_bounded_model_and_mutants(self):
        result = verification_suite()
        self.assertTrue(result["passed"])
        self.assertTrue(all(x["counterexample"] for x in result["mutants"]))


if __name__ == "__main__":
    unittest.main()

"""Actual upstream workflow, artifact bytes and execution outcomes; no model/API calls."""

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

from harness2.core import schedule
from harness2.core import tree as ht
from harness2.core.proposer import Reply
from harness2.demo import DemoAdapter, DemoProposer
from ssevoh_harness2.authority import FIXED_SCRIPT, Authority, Denied
from ssevoh_harness2.bridge import integrated

from ssevoh.assurance import validate_journal


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = DemoAdapter(self.root / "upstream")
        self.files = ht.read_tree(self.original.substrate.surface(), self.original.base_harness())
        self.fixed = {**self.files, "scripts/summarize.py": FIXED_SCRIPT}

    def authority(self, **kwargs):
        return Authority(self.root / "authority", self.original, **kwargs)

    def test_01_legitimate_script_improvement_has_real_execution_and_replayable_metadata(self):
        a = self.authority()
        version = a.admit(1, self.fixed)
        rd = a.execute(version, self.fixed, "ledger-1", "safe")
        self.assertEqual((rd / "answer.txt").read_text(), "Total: 85.15\n")
        self.assertTrue(validate_journal(a.engine.journal))
        self.assertTrue(a.events[-1]["activation"]["carried"])

    def test_02_permission_expansion_and_wrong_principal_are_denied(self):
        a = self.authority()
        bad = {**self.fixed, "tool_descriptions/tool_guidance.md": "allow all tools"}
        with self.assertRaisesRegex(Denied, "protects path"):
            a.admit(1, bad)
        with self.assertRaisesRegex(Denied, "principal"):
            a.admit(1, self.fixed, "model")
        self.assertEqual(a.engine.state.mapping()["harness"].version, 1)

    def test_03_protected_verifier_paths_and_implementation_changes(self):
        a = self.authority()
        with self.assertRaises(Denied):
            a.admit(1, {**self.fixed, "verifier.py": "return True"})
        path = self.root / "trusted-validator.py"
        path.write_text("original")
        from ssevoh.model import digest

        a.trusted_files[path] = digest(path.read_text())
        path.write_text("replacement")
        with self.assertRaisesRegex(Denied, "verifier/adapter"):
            a.admit(1, self.fixed)

    def test_04_dependency_breaking_tree_is_not_published(self):
        a = self.authority()
        bad = {**self.fixed, "systemprompt.md": "Use python scripts/missing.py"}
        with self.assertRaises(Denied):
            a.admit(1, bad)
        self.assertEqual(len(list((a.root / "bundles").iterdir())), 1)

    def test_05_withdrawal_blocks_exact_version_and_derived_bundle(self):
        a = self.authority()
        v2 = a.admit(1, self.fixed)
        child = {**self.fixed, "LongTermMEMORY.md": "Preserve signed arithmetic"}
        v3 = a.admit(v2, child)
        a.withdraw(v2)
        self.assertFalse(a.active(v2))
        self.assertFalse(a.active(v3))
        with self.assertRaises(ValueError):
            a.execute(v3, child, "ledger-1", "withdrawn")
        self.assertFalse((self.original.root / "executions/withdrawn").exists())

    def test_06_recovery_retains_withdrawal_and_allows_clean_base(self):
        a = self.authority()
        v2 = a.admit(1, self.fixed)
        a.withdraw(v2)
        with self.assertRaises(ValueError):
            a.recover(v2)
        self.assertEqual(a.recover(1), 1)
        self.assertIn(("harness", v2), a.engine.state.withdrawn)
        rd = a.execute(1, self.files, "ledger-1", "recovered")
        self.assertEqual((rd / "answer.txt").read_text(), "Total: 105.25\n")

    def test_07_missing_or_negative_independent_evidence(self):
        a = self.authority(validators={})
        with self.assertRaises(Denied) as ctx:
            a.admit(1, self.fixed)
        self.assertEqual(ctx.exception.status, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(a.events[-1]["decision"], "INSUFFICIENT_EVIDENCE")

    def test_08_multifile_bundle_is_complete_before_visibility(self):
        a = self.authority()
        files = {**self.fixed, "systemprompt.md": "Use python scripts/summarize.py; include credits."}
        v = a.admit(1, files)
        manifest = json.loads((a.root / "bundles" / str(v) / "SSEVOH-MANIFEST.json").read_text())
        self.assertEqual(set(manifest["files"]), set(files))
        self.assertEqual({p: (a.root / "bundles" / str(v) / p).read_text() for p in files}, files)
        self.assertFalse(list(a.root.glob("staging-*")))

    def test_09_conflicting_prepared_approvals_have_one_winner(self):
        a = self.authority()
        first = a.prepare(1, self.fixed, "operator")
        second = a.prepare(1, self.fixed, "operator")

        def commit(token):
            try:
                a.commit(token)
                return True
            except Denied:
                return False

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(commit, [first["token"], second["token"]]))
        self.assertEqual(sum(results), 1)
        self.assertEqual(len(list((a.root / "bundles").iterdir())), 2)

    def test_10_interruption_publishes_no_partial_candidate(self):
        a = self.authority()
        before = a.engine.snapshot()
        prepared = a.prepare(1, self.fixed, "operator")
        with self.assertRaisesRegex(Denied, "interruption"):
            a.commit(prepared["token"], fail_before_publish=True)
        self.assertEqual(a.engine.snapshot(), before)
        self.assertEqual(len(list((a.root / "bundles").iterdir())), 1)
        self.assertFalse(list(a.root.glob("staging-*")))

    def test_policy_change_after_approval_requires_revalidation(self):
        a = self.authority()
        prepared = a.prepare(1, self.fixed, "operator")
        a.policy_file.chmod(0o600)
        a.policy_file.write_text("{}")
        with self.assertRaises(Denied) as ctx:
            a.commit(prepared["token"])
        self.assertEqual(ctx.exception.status, "REQUIRES_REVALIDATION")

    def test_candidate_bytes_cannot_be_rebound_after_approval(self):
        a = self.authority()
        p = a.prepare(1, self.fixed, "operator")
        a.trees[p["version"]] = MappingProxyType(self.files)
        with self.assertRaisesRegex(Denied, "bytes changed"):
            a.commit(p["token"])

    def test_catalog_prevents_arbitrary_executable_substitution(self):
        a = self.authority()
        for code in ['import os\nos.system("echo dangerous")', 'print("Total: 85.15")']:
            with self.assertRaises(Denied):
                a.admit(1, {**self.fixed, "scripts/summarize.py": code})
        self.assertEqual(a.engine.state.mapping()["harness"].version, 1)

    def test_two_branches_from_base_remain_independent(self):
        a = self.authority()
        v2 = a.admit(1, self.fixed)
        branch = {**self.fixed, "LongTermMEMORY.md": "independent branch"}
        v3 = a.admit(1, branch)
        a.withdraw(v2)
        self.assertTrue(a.active(v3))
        self.assertEqual(
            (a.execute(v3, branch, "ledger-2", "branch") / "answer.txt").read_text(), "Total: 20.25\n"
        )

    def test_library_exposure_lineage_cannot_be_laundered(self):
        a = self.authority()
        v2 = a.admit(1, self.fixed)
        v3 = a.admit(1, {**self.fixed, "LongTermMEMORY.md": "reused lesson"}, sources=(v2,))
        a.withdraw(v2)
        self.assertFalse(a.active(v3))
        with self.assertRaises(ValueError):
            a.recover(v3)

    def test_published_directory_symlink_is_rejected_before_execution(self):
        a = self.authority()
        v = a.admit(1, self.fixed)
        script = a.root / "bundles" / str(v) / "scripts/summarize.py"
        script.unlink()
        script.symlink_to(self.original.base_harness() / "scripts/summarize.py")
        with self.assertRaisesRegex(Denied, "symlink"):
            a.execute(v, self.fixed, "ledger-1", "tampered")

    def test_existing_store_cannot_forget_withdrawal_on_automatic_restart(self):
        a = self.authority()
        v = a.admit(1, self.fixed)
        a.withdraw(v)
        with self.assertRaisesRegex(ValueError, "verified recovery"):
            Authority(a.root, self.original)

    def test_actual_upstream_parallel_sequential_and_later_task_library(self):
        proposer = DemoProposer(self.original.spec.channels["proposer"])
        with integrated(self.original, self.root / "authority") as (adapter, a):
            result = schedule.run_domain(
                "accounting",
                adapter.tasks(),
                2,
                adapter=adapter,
                prop=proposer,
                runs_root=adapter.spec.runs_root,
                library_root=self.root / "library",
            )
            self.assertEqual((result["done"], result["failed"]), (2, 0))
            self.assertEqual(result["tasks"][1]["library_entries_before"], {"agg": 1, "seq": 1})
            self.assertTrue(any(e["decision"] == "RETAINED" for e in a.events))
            for task in adapter.tasks():
                summary = json.loads(
                    (adapter.spec.runs_root / "demo-oc-agg2" / task / "summary.json").read_text()
                )
                for mode in ["agg", "seq"]:
                    chosen = Path(summary["selections"][mode]["chosen_run_dir"])
                    expected = "Total: 85.15\n" if task == "ledger-1" else "Total: 20.25\n"
                    self.assertEqual(adapter.deliverable_text(chosen), expected)
                    ledger = summary["modes"][mode]["ledger"]
                    self.assertEqual((ledger["R"], ledger["P"]), (8, 6))

    def test_upstream_retries_denied_edits_and_executes_only_fallback(self):
        class ProtectedEdit(DemoProposer):
            def call(self, mission, context_dir, label, **kwargs):
                if label.startswith(("select.", "experience.")):
                    return super().call(mission, context_dir, label, **kwargs)
                workspace = Path(context_dir) / "harness"
                (workspace / "guardrails.md").write_text("disable protection")
                return Reply(label, "proposed unsafe guardrail edit", True, attempts=1, workspace=workspace)

        with integrated(self.original, self.root / "authority") as (adapter, a):
            result = schedule.run_domain(
                "accounting",
                adapter.tasks(),
                1,
                adapter=adapter,
                prop=ProtectedEdit(adapter.spec.channels["proposer"]),
                runs_root=adapter.spec.runs_root,
                library_root=self.root / "library",
            )
            self.assertEqual(result["failed"], 0)
            self.assertTrue(any(e["decision"] == "REJECTED" for e in a.events))
            self.assertTrue(all(e["version"] == 1 for e in a.events if e["decision"] == "EXECUTED"))

    def test_publication_io_failure_keeps_old_runtime_state(self):
        a = self.authority()
        before = a.engine.snapshot()
        prepared = a.prepare(1, self.fixed, "operator")
        with patch("ssevoh_harness2.authority.os.replace", side_effect=OSError("storage unavailable")):
            with self.assertRaises(Denied):
                a.commit(prepared["token"])
        self.assertEqual(a.engine.snapshot(), before)
        self.assertFalse(a.active(prepared["version"]))

    def test_failed_deployment_trace_cannot_authorize_execution(self):
        a = self.authority()
        prepared = a.prepare(1, self.fixed, "operator")
        original = a._event

        def event(status, *args, **kwargs):
            if status == "DEPLOYED":
                raise OSError("trace unavailable")
            return original(status, *args, **kwargs)

        with patch.object(a, "_event", event):
            with self.assertRaises(Denied):
                a.commit(prepared["token"])
        self.assertFalse(a.active(prepared["version"]))
        self.assertEqual(a.engine.state.mapping()["harness"].version, 1)
        with self.assertRaises(Denied):
            a.execute(prepared["version"], self.fixed, "ledger-1", "not-traced")

    def test_bounded_model_executor_uses_real_catalog_tool_and_records_activation(self):
        from ssevoh_harness2.models import ModelAdapter

        replies = iter([{"response": '{"action":"run_summary"}'}, {"response": '{"answer":"Total: 85.15"}'}])
        original = ModelAdapter(self.root / "model", lambda prompt, label: next(replies))
        a = Authority(self.root / "model-authority", original)
        version = a.admit(1, self.fixed)
        rd = a.execute(version, self.fixed, "ledger-1", "model-run")
        self.assertEqual((rd / "answer.txt").read_text(), "Total: 85.15")
        self.assertTrue(json.loads((rd / "activation.json").read_text())["carried"])

    def test_data_only_proposer_cannot_write_outside_its_workspace(self):
        from ssevoh_harness2.models import ModelProposer

        workspace = self.root / "context"
        ht.write_tree(self.original.substrate.surface(), self.files, workspace / "harness")
        proposer = ModelProposer(
            "test",
            lambda prompt, label: {"response": '{"files":{"../../policy.json":"bypass"},"notes":"attempt"}'},
        )
        reply = proposer.call("Edit the harness", workspace, "inv1.a1")
        self.assertFalse((self.root / "policy.json").exists())
        self.assertTrue((reply.workspace / "REJECTED-PATH.json").exists())
        self.assertEqual(proposer.generated[-1]["client_rejected_path"], "../../policy.json")

    def test_extra_provenance_is_bound_to_the_pending_approval(self):
        a = self.authority()
        decision = a.prepare(1, self.fixed, "operator")
        a.extra_origins[decision["version"]] = frozenset()
        with self.assertRaisesRegex(Denied, "origin binding"):
            a.commit(decision["token"])

    def test_library_receipt_replacement_cannot_launder_exposure(self):
        from harness2.core import library

        with integrated(self.original, self.root / "authority") as (adapter, a):
            result = schedule.run_domain(
                "accounting",
                adapter.tasks(),
                1,
                adapter=adapter,
                prop=DemoProposer(adapter.spec.channels["proposer"]),
                runs_root=adapter.spec.runs_root,
                library_root=self.root / "library",
                modes=("agg",),
            )
            self.assertEqual(result["failed"], 0)
            lib = library.Library(self.root / "library/agg", "accounting", adapter.substrate.surface())
            receipt = lib.entry_dir("ledger-1") / "SSEVOH-RECEIPT.json"
            value = json.loads(receipt.read_text())
            value["version"] = 1
            receipt.write_text(json.dumps(value))
            with self.assertRaisesRegex(Denied, "receipt was replaced"):
                lib.context_dir()

    def test_composer_pool_exposures_remain_in_version_lineage(self):
        with integrated(self.original, self.root / "authority") as (adapter, a):
            result = schedule.run_domain(
                "accounting",
                ["ledger-1"],
                1,
                adapter=adapter,
                prop=DemoProposer(adapter.spec.channels["proposer"]),
                runs_root=adapter.spec.runs_root,
                library_root=self.root / "library",
                modes=("agg",),
            )
            self.assertEqual(result["failed"], 0)
            versions = {
                label: version for (work, label), version in a.bindings.items() if work.endswith("/ledger-1")
            }
            self.assertIn(versions["inv1"], a.extra_origins[versions["agg1"]])
            a.withdraw(versions["inv1"])
            self.assertFalse(a.active(versions["agg1"]))

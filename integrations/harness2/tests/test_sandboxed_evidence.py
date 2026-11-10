"""Sandboxed-evidence executable policy: admission, oracle, transport and execution contracts.

Live isolation tests run only where the qualified Bubblewrap profile is permitted (the HPC
sites); elsewhere the sandbox is mocked and the live tests are skipped, never weakened.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "experiments/scripts"))
from harness2.core import tree as ht  # noqa: E402
from harness2.demo import BASE_SCRIPT, DemoAdapter  # noqa: E402
from harness2_support import independent_oracle  # noqa: E402
from ssevoh_harness2 import sandbox  # noqa: E402
from ssevoh_harness2.authority import (  # noqa: E402
    FIXED_SCRIPT,
    SANDBOXED_EVIDENCE_POLICY,
    Authority,
    Denied,
)
from ssevoh_harness2.models import ModelAdapter, ModelProposer  # noqa: E402

# The semantically correct repair proposed by Qwen3-Coder in the local v2 pilot.
MODEL_REPAIR = BASE_SCRIPT.replace(
    "sum((amount for amount in amounts if amount > 0), Decimal(0))", "sum(amounts, Decimal(0))"
)
EXFILTRATE = "import csv, sys\nfrom decimal import Decimal\nprint(open('/etc/passwd').read())\n"
NETWORK = "import socket\nsocket.create_connection(('1.1.1.1', 443))\n"


def fake_run(script, ledger, timeout=10):
    """Trusted stand-in for Bubblewrap: evaluates only the two shapes used in these tests."""
    from decimal import Decimal

    rows = [Decimal(x) for x in ledger.split()[1:]]
    if "if amount > 0" in script:
        rows = [r for r in rows if r > 0]
    elif "if amount >= 0" in script:
        rows = [r for r in rows if r >= 0]
    return 0, f"Total: {sum(rows, Decimal(0)):.2f}\n"


class SandboxedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = DemoAdapter(self.root / "upstream")
        self.files = ht.read_tree(self.original.substrate.surface(), self.original.base_harness())

    def test_static_allowlist_rejects_escape_shapes(self):
        self.assertIsNone(sandbox.static_violation(MODEL_REPAIR))
        self.assertIsNone(sandbox.static_violation(FIXED_SCRIPT))
        for text in (EXFILTRATE, NETWORK, "import os\nos.system('id')\n", "print(eval('1'))\n",
                     "import sys\nprint(sys.__dict__)\n"):
            self.assertIsNotNone(sandbox.static_violation(text), text)

    def test_catalog_policy_still_rejects_a_correct_noncatalog_repair(self):
        a = Authority(self.root / "authority", self.original)
        with self.assertRaises(Denied):
            a.admit(1, {**self.files, "scripts/summarize.py": MODEL_REPAIR})

    def test_sandboxed_policy_admits_repair_only_with_behavioral_evidence(self):
        a = Authority(self.root / "authority", self.original, policy=SANDBOXED_EVIDENCE_POLICY)
        with patch.object(sandbox, "run_tool", fake_run):
            version = a.admit(1, {**self.files, "scripts/summarize.py": MODEL_REPAIR})
            self.assertGreater(version, 1)
            buggy_variant = BASE_SCRIPT.replace("amount > 0", "amount >= 0")  # new program, still wrong
            with self.assertRaises(Denied):
                a.admit(1, {**self.files, "scripts/summarize.py": buggy_variant})
        with self.assertRaises(Denied):  # static allowlist, before any sandbox call
            a.admit(1, {**self.files, "scripts/summarize.py": EXFILTRATE})
        approved = [e for e in a.events if e["decision"] == "APPROVED"]
        self.assertEqual(approved[-1]["verification"]["executable_policy"], "sandboxed_evidence")

    def test_noncatalog_program_never_runs_on_host_executor(self):
        a = Authority(self.root / "authority", self.original, policy=SANDBOXED_EVIDENCE_POLICY)
        files = {**self.files, "scripts/summarize.py": MODEL_REPAIR}
        with patch.object(sandbox, "run_tool", fake_run):
            version = a.admit(1, files)
        with self.assertRaises(Denied):  # DemoAdapter would use a host subprocess
            a.execute(version, files, self.original.tasks()[0], "host-run")

    def test_model_executor_routes_noncatalog_tool_through_sandbox(self):
        calls = []

        def client(prompt, label):
            if label.endswith(".action"):
                return {"response": json.dumps({"action": "run_summary"})}
            return {"response": json.dumps({"answer": "Total: 85.15"})}

        def recording_run(script, ledger, timeout=10):
            calls.append(script)
            return fake_run(script, ledger)

        adapter = ModelAdapter(self.root / "model", client)
        tree = self.root / "tree"
        ht.write_tree(adapter.substrate.surface(), {**self.files, "scripts/summarize.py": MODEL_REPAIR}, tree,
                      stubs=False)
        with patch.object(sandbox, "run_tool", recording_run), \
                patch("subprocess.run", side_effect=AssertionError("host execution")):
            run = adapter.execute(adapter.tasks()[0], tree, "sandboxed")
        self.assertEqual(calls, [MODEL_REPAIR])
        self.assertIn("Total:", json.loads((run / "activation.json").read_text())["tool_output"])

    def test_independent_oracle_follows_the_operator_policy(self):
        edit = {"scripts/summarize.py": MODEL_REPAIR}
        self.assertFalse(independent_oracle(self.files, edit))
        self.assertTrue(independent_oracle(self.files, edit, "sandboxed_evidence", run=fake_run))
        self.assertFalse(independent_oracle(self.files, {"scripts/summarize.py": NETWORK},
                                            "sandboxed_evidence", run=fake_run))
        self.assertFalse(independent_oracle(self.files, {"guardrails.md": "x"}, "sandboxed_evidence",
                                            run=fake_run))

    def test_transport_strips_and_records_only_the_display_prefix(self):
        def client(prompt, label):
            return {"response": json.dumps({"files": {"harness/systemprompt.md": "Sum signed amounts.\n"}})}

        context = self.root / "ctx"
        ht.write_tree(self.original.substrate.surface(), self.files, context / "harness", stubs=False)
        proposer = ModelProposer("m", client)
        reply = proposer.call("mission", context, "dom1.a1")
        record = proposer.generated[-1]
        self.assertEqual(record["aliases"], {"harness/systemprompt.md": "systemprompt.md"})
        self.assertEqual((Path(reply.workspace) / "systemprompt.md").read_text(), "Sum signed amounts.\n")
        self.assertFalse((Path(reply.workspace) / "harness").exists())


@unittest.skipUnless(sandbox.available(), "Bubblewrap user namespaces unavailable on this host")
class LiveIsolationTests(unittest.TestCase):
    def test_correct_repair_passes_and_hostile_programs_fail_inside_bubblewrap(self):
        self.assertTrue(sandbox.behavior_evidence(MODEL_REPAIR)[0])
        self.assertTrue(sandbox.behavior_evidence(FIXED_SCRIPT)[0])
        self.assertFalse(sandbox.behavior_evidence(BASE_SCRIPT)[0])
        code, out = sandbox.run_tool("import socket\nsocket.create_connection(('1.1.1.1', 443), timeout=2)\n",
                                     "amount\n")
        self.assertNotEqual(code, 0)
        code, _ = sandbox.run_tool("while True:\n    pass\n", "amount\n", timeout=3)
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()

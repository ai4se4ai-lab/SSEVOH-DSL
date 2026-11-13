"""Sandbox-only mechanism removal. No weakening switch is exposed to proposal text or production CLI."""

import argparse
import os
from contextlib import ExitStack
from dataclasses import replace
from unittest.mock import patch

import ssevoh.assurance as assurance
import ssevoh.compiler as compiler
import ssevoh.verification as verification
from ssevoh.benchmark import append_record, evaluate_case, load_cases, make_engine, read_records
from ssevoh.model import structural_errors

MODES = (
    "full",
    "dependency_closure",
    "provenance_checks",
    "withdrawal_validation",
    "rollback_conflicts",
    "revalidation",
)


def projected(state, mode):
    components = (
        tuple(replace(c, parents=()) for c in state.components)
        if mode == "provenance_checks"
        else state.components
    )
    withdrawn = frozenset() if mode in {"withdrawal_validation", "rollback_conflicts"} else state.withdrawn
    return replace(state, components=components, withdrawn=withdrawn)


class ResearchSandbox(assurance.SandboxEngine):
    """Trusted test adapter; instantiated only inside the explicit ablation worker."""

    def __init__(self, base, mode):
        super().__init__(base.state, base._policy, base._validators)
        self.mode = mode

    def approve(self, source, principal):
        if (
            self.mode != "rollback_conflicts"
            or compiler.Parser(source).parse().evolution.operation != "rollback"
        ):
            return super().approve(source, principal)
        original = self._state
        self._state = replace(original, withdrawn=frozenset())
        try:
            approval = super().approve(source, principal)
        finally:
            self._state = original
        stored, candidate, e, policy_hash = self._approvals[approval.token]
        actual = replace(
            stored,
            base_hash=original.fingerprint(),
            context_hash=self._context_hash(),
            candidate_hash=replace(candidate, withdrawn=original.withdrawn).fingerprint(),
        )
        self._approvals[approval.token] = (
            actual,
            replace(candidate, withdrawn=original.withdrawn),
            e,
            policy_hash,
        )
        return actual

    def deploy(self, approval, *, fail_before_commit=False):
        if self.mode == "revalidation" and approval.token in self._approvals:
            stored, candidate, e, policy_hash = self._approvals[approval.token]
            if stored == approval:
                approval = replace(
                    approval, base_hash=self._state.fingerprint(), context_hash=self._context_hash()
                )
                self._approvals[approval.token] = (approval, candidate, e, policy_hash)
        return super().deploy(approval, fail_before_commit=fail_before_commit)


def evaluate_ablation(case, mode):
    original_verify = verification.verify_instance

    def structure(state):
        return structural_errors(projected(state, mode))

    def verify(state, policy, principal, e, base=None, origins=None):
        return original_verify(
            projected(state, mode),
            policy,
            principal,
            e,
            projected(base, mode) if base is not None else None,
            origins,
        )

    with ExitStack() as stack:
        if mode == "dependency_closure":
            stack.enter_context(patch.object(assurance, "closure", lambda cs, roots: set(roots)))
        if mode in {"provenance_checks", "withdrawal_validation", "rollback_conflicts"}:
            stack.enter_context(patch.object(assurance, "structural_errors", structure))
            stack.enter_context(patch.object(compiler, "structural_errors", structure))
            stack.enter_context(patch.object(verification, "verify_instance", verify))
        rows = evaluate_case(case, engine_factory=lambda c: ResearchSandbox(make_engine(c), mode))
    for row in rows:
        row.update(
            ablation=mode,
            baseline="ablation:" + mode,
            state_violation=row["accepted"] and not row["state_matches"],
            scope="deployed synthetic sandbox ablation; trusted test code weakens named gates",
        )
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--repeats", type=int, default=5)
    a = p.parse_args()
    done = {(r["ablation"], r["scenario"], r["step"], r["repeat"]) for r in read_records(a.output)}
    for mode in MODES:
        for repeat in range(a.repeats):
            for case in load_cases():
                for row in evaluate_ablation(case, mode):
                    key = (mode, row["scenario"], row["step"], repeat)
                    if key not in done:
                        row.update(
                            repeat=repeat,
                            cluster=os.environ.get("CLUSTER", "local"),
                            run_id=os.environ.get("RUN_ID", "local-validation"),
                            job_id=os.environ.get("SLURM_JOB_ID", "local-validation"),
                            benchmark="heartbench-v1",
                        )
                        append_record(a.output, row)
                        done.add(key)


if __name__ == "__main__":
    main()

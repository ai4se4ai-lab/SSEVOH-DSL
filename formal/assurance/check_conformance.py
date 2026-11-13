#!/usr/bin/env python3
"""Exhaustive relative soundness/completeness over declared finite proposal domains; no sampling."""

import argparse
import hashlib
import json
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference import RefReject, graph_valid, initial_origins, transition

from ssevoh.assurance import SandboxEngine, validate_journal
from ssevoh.compiler_print import print_specification
from ssevoh.model import Component, Evolution, Specification, State
from ssevoh.policy import Policy

ROOT = Path(__file__).resolve().parents[2]


def domains():
    grants = frozenset(("alice", n, op) for n in ["a", "b"] for op in ["update", "withdraw", "rollback"])
    p = Policy(grants)
    relations = [(), ("a",), ("b",), ("missing",)]
    for bits in product([False, True], repeat=4):
        a = Component("a", "skill", 1, depends=("b",) if bits[0] else (), parents=("b",) if bits[2] else ())
        b = Component("b", "skill", 1, depends=("a",) if bits[1] else (), parents=("a",) if bits[3] else ())
        cs = {"a": a, "b": b}
        if not graph_valid(cs, set(), set()):
            continue
        for inactive_bits in product([False, True], repeat=2):
            inactive = frozenset(n for n, flag in zip(["a", "b"], inactive_bits) if flag)
            for withdrawn_bits in product([False, True], repeat=2):
                withdrawn = frozenset((n, 1) for n, flag in zip(["a", "b"], withdrawn_bits) if flag)
                if not graph_valid(cs, set(inactive), set(withdrawn)):
                    continue
                state = State((a, b), inactive, withdrawn)
                for target, op, expected, version, deps, parents, pre, post in product(
                    ["a", "b"],
                    ["update", "withdraw", "rollback"],
                    [1, 2],
                    [1, 2, 3],
                    relations,
                    relations,
                    ["active", "inactive", "any"],
                    ["active", "inactive"],
                ):
                    e = Evolution("request", op, target, expected, version, deps, parents, (), (), pre, post)
                    yield "graphs-and-lifecycle", state, p, e, "alice", {}, {"structure": True}
    for (
        kind,
        mutable,
        caps,
        ceiling,
        authorized,
        guard,
        op,
        expected,
        version,
        new_caps,
        pre,
        post,
    ) in product(
        ["skill", "memory", "tool", "workflow", "configuration", "policy", "verifier"],
        [False, True],
        [(), ("read",)],
        [(), ("read",)],
        [False, True],
        [None, False, True],
        ["update", "withdraw", "rollback"],
        [1, 2],
        [1, 2, 3],
        [(), ("read",)],
        ["active", "inactive", "any"],
        ["active", "inactive"],
    ):
        state = State((Component("a", kind, 1, mutable, capabilities=caps),))
        policy = Policy(frozenset({("alice", "a", op)}) if authorized else frozenset(), (("a", ceiling),))
        e = Evolution(
            "request",
            op,
            "a",
            expected,
            version,
            capabilities=new_caps,
            requires=("guard",),
            precondition=pre,
            postcondition=post,
        )
        validators = {} if guard is None else {"guard": lambda s, e, answer=guard: answer}
        yield (
            "types-permissions-evidence",
            state,
            policy,
            e,
            "alice",
            validators,
            {"structure": True, "guard": guard},
        )


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="diagnostic prefix only; cannot satisfy complete-domain readiness",
    )
    p.add_argument("--output", default="formal/assurance/results/conformance.json")
    a = p.parse_args()
    start = time.perf_counter()
    counts = {}
    accepted = rejected = 0
    rolling = hashlib.sha256()
    errors = []
    for index, (domain, state, policy, e, principal, validators, evidence) in enumerate(domains(), 1):
        if a.limit and index > a.limit:
            break
        engine = SandboxEngine(state, policy, validators)
        history = {(c.name, c.version): c for c in state.components}
        origins = initial_origins(state)
        try:
            expected, _, expected_origins = transition(
                state, policy, e, principal, history, origins, evidence
            )
            allowed = True
        except RefReject:
            allowed = False
            expected = None
        spec = Specification("check", state.components, e)
        source = print_specification(spec)
        try:
            approval = engine.approve(source, principal)
            actual = engine.deploy(approval)
            actual_allowed = True
        except ValueError as exc:
            actual_allowed = False
            actual_error = str(exc)
            actual = engine.state
        bad = allowed != actual_allowed or (allowed and actual != expected)
        if actual_allowed and allowed:
            bad |= not validate_journal(
                engine.journal, engine.journal[-1]["hash"], state.fingerprint(), actual.fingerprint()
            )
            bad |= any(engine._origins[k] != v for k, v in expected_origins.items())
        else:
            bad |= actual != state or bool(engine.journal)
        if bad:
            errors.append(
                {
                    "domain": domain,
                    "case": index,
                    "state": {
                        "components": [asdict(c) for c in state.components],
                        "inactive": sorted(state.inactive),
                        "withdrawn": sorted(state.withdrawn),
                    },
                    "spec": spec.ir(),
                    "source": source,
                    "expected_accept": allowed,
                    "actual_accept": actual_allowed,
                    "actual_error": None if actual_allowed else actual_error,
                    "expected": expected.fingerprint() if expected else None,
                    "actual": actual.fingerprint(),
                }
            )
            break
        counts[domain] = counts.get(domain, 0) + 1
        accepted += actual_allowed
        rejected += not actual_allowed
        rolling.update(f"{domain}:{index}:{int(allowed)}:{actual.fingerprint()}\n".encode())
        if index % 10000 == 0:
            print(
                f"{index} exhaustive cases; no divergence; elapsed {time.perf_counter() - start:.1f}s",
                flush=True,
            )
    report = {
        "schema": "ssevoh-conformance-v1",
        "utc": datetime.now(UTC).isoformat(),
        "complete_domain": not a.limit and not errors,
        "passed": not errors,
        "cases": sum(counts.values()),
        "domains": counts,
        "accepted": accepted,
        "rejected": rejected,
        "false_accepts": sum(not r["expected_accept"] and r["actual_accept"] for r in errors),
        "false_rejects": sum(r["expected_accept"] and not r["actual_accept"] for r in errors),
        "counterexamples": errors,
        "seconds": time.perf_counter() - start,
        "verdict_digest": rolling.hexdigest(),
        "bounds": "all initial acyclic two-component dependency/provenance graphs; all compatible quarantine/current-withdrawal subsets; one proposal; singleton relation lists from {self,other,missing}; target versions 1..3; expected versions 1..2; all supported pre/postconditions. Separate exhaustive one-component type/mutability/capability/grant/evidence domain.",
        "source_sha256": {
            str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
            for folder in ["src/ssevoh", "formal/assurance"]
            for f in (ROOT / folder).glob("*.py")
        },
    }
    out = ROOT / a.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ["source_sha256", "bounds"]}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

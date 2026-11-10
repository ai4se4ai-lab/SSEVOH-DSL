#!/usr/bin/env python3
"""Exhaustively explore reachable metadata/history/provenance contexts to a fixed depth."""

import argparse
import hashlib
import json
import sys
import time
from collections import deque
from dataclasses import asdict
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference import RefReject, graph_valid, initial_origins, transition

from ssevoh.assurance import SandboxEngine, replay_journal, validate_journal
from ssevoh.compiler_print import print_specification
from ssevoh.model import Component, Evolution, Specification, State, digest
from ssevoh.policy import Policy

ROOT = Path(__file__).resolve().parents[2]


def context_key(state, history, origins):
    return digest(
        [
            state.fingerprint(),
            [(n, v, asdict(c)) for (n, v), c in sorted(history.items())],
            [(n, v, sorted(refs)) for (n, v), refs in sorted(origins.items())],
        ]
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--depth", type=int, default=4)
    p.add_argument("--output", default="formal/assurance/results/sequences.json")
    a = p.parse_args()
    if not 1 <= a.depth <= 6:
        raise SystemExit("depth must be in [1,6]")
    start = time.perf_counter()
    counts = {
        "initial_graphs": 0,
        "contexts": 0,
        "transitions": 0,
        "accepted": 0,
        "rejected": 0,
        "anchored_replays": 0,
    }
    counterexamples = []
    rolling = hashlib.sha256()
    policy = Policy(
        frozenset(("alice", n, op) for n in ["a", "b"] for op in ["update", "withdraw", "rollback"])
    )
    for bits in product([False, True], repeat=4):
        initial = State(
            (
                Component(
                    "a", "skill", 1, depends=("b",) if bits[0] else (), parents=("b",) if bits[2] else ()
                ),
                Component(
                    "b", "skill", 1, depends=("a",) if bits[1] else (), parents=("a",) if bits[3] else ()
                ),
            )
        )
        if not graph_valid(initial.mapping(), set(), set()):
            continue
        counts["initial_graphs"] += 1
        history = {(c.name, c.version): c for c in initial.components}
        origins = initial_origins(initial)
        queue = deque([(initial, history, origins, ())])
        seen = {context_key(initial, history, origins)}
        while queue and not counterexamples:
            state, history, origins, path = queue.popleft()
            counts["contexts"] += 1
            if len(path) == a.depth:
                continue
            for target, op, version in product(["a", "b"], ["update", "withdraw", "rollback"], [1, 2, 3]):
                c = state.mapping()[target]
                e = Evolution(
                    "step",
                    op,
                    target,
                    c.version,
                    version,
                    c.depends,
                    c.parents,
                    c.capabilities,
                    (),
                    "any",
                    "inactive" if op == "withdraw" else "active",
                )
                text = print_specification(Specification("sequences", state.components, e))
                try:
                    expected, expected_history, expected_origins = transition(
                        state, policy, e, "alice", history, origins, {"structure": True}
                    )
                    allowed = True
                except RefReject:
                    allowed = False
                    expected = None
                engine = SandboxEngine(initial, policy)
                for prior in path:
                    engine.deploy(engine.approve(prior, "alice"))
                if engine.state != state:
                    raise AssertionError("prefix reconstruction differs")
                before = engine.snapshot()
                try:
                    engine.deploy(engine.approve(text, "alice"))
                    accepted = True
                    error = None
                except ValueError as exc:
                    accepted = False
                    error = str(exc)
                bad = allowed != accepted or (allowed and engine.state != expected)
                if accepted and allowed:
                    bad |= engine._history != expected_history or engine._origins != expected_origins
                    head = engine.journal[-1]["hash"]
                    bad |= not validate_journal(
                        engine.journal, head, initial.fingerprint(), engine.state.fingerprint()
                    )
                    bad |= replay_journal(initial, engine.journal, policy, expected_head=head) != expected
                    counts["anchored_replays"] += 1
                elif not accepted:
                    bad |= engine.snapshot() != before
                counts["transitions"] += 1
                counts["accepted"] += accepted
                counts["rejected"] += not accepted
                rolling.update(
                    f"{context_key(state, history, origins)}:{target}:{op}:{version}:{accepted}\n".encode()
                )
                if bad:
                    counterexamples.append(
                        {
                            "path": path,
                            "source": text,
                            "expected_accept": allowed,
                            "actual_accept": accepted,
                            "error": error,
                        }
                    )
                    break
                if allowed:
                    key = context_key(expected, expected_history, expected_origins)
                    if key not in seen:
                        seen.add(key)
                        queue.append((expected, expected_history, expected_origins, path + (text,)))
        if counterexamples:
            break
    report = {
        "schema": "ssevoh-sequences-v1",
        "utc": datetime.now(UTC).isoformat(),
        "passed": not counterexamples,
        "complete_domain": not counterexamples,
        "bounds": {
            "components": 2,
            "initial_versions": [1],
            "versions": [1, 2, 3],
            "depth": a.depth,
            "initial_graphs": "all acyclic combinations of four possible cross-component dependency/parent edges",
            "proposals": "both targets, all three operations, all three destination versions; existing relation/capability lists retained; true structure evidence; all grants",
        },
        **counts,
        "counterexamples": counterexamples,
        "seconds": time.perf_counter() - start,
        "verdict_digest": rolling.hexdigest(),
        "source_sha256": {
            str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
            for folder in ["src/ssevoh", "formal/assurance"]
            for f in (ROOT / folder).glob("*.py")
        },
    }
    output = ROOT / a.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "source_sha256"}, indent=2))
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())

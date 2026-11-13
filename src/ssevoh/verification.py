"""Independent finite abstraction. Bounds and mutants are explicit in every report."""

import time
from collections import deque
from dataclasses import asdict
from functools import lru_cache
from itertools import product


def lifecycle_successors(s, authorized=True, evidence=True, mutant="none", max_epoch=2):
    phase, epoch, approved, withdrawn, active, certified = s
    nexts = []
    if phase == "PROPOSED":
        nexts.append(("analyse", ("ANALYSED", epoch, -1, withdrawn, active, certified)))
    if phase == "ANALYSED" and (authorized or mutant == "authorization"):
        nexts.append(("verify", ("VERIFIED", epoch, -1, withdrawn, active, certified)))
    if phase == "VERIFIED" and (evidence or mutant == "evidence"):
        nexts.append(("approve", ("APPROVED", epoch, epoch, withdrawn, active, certified)))
    if phase == "APPROVED" and (approved == epoch or mutant == "revalidation") and not withdrawn:
        nexts.append(("deploy", ("DEPLOYED", epoch, approved, withdrawn, True, approved)))
    if epoch < max_epoch:
        nexts.append(("dependency_change", (phase, epoch + 1, approved, withdrawn, False, certified)))
        nexts.append(
            (
                "withdraw",
                (
                    phase,
                    epoch + 1,
                    approved,
                    True,
                    active if mutant == "withdrawal" else False,
                    certified,
                ),
            )
        )
    if withdrawn:
        nexts.append(
            (
                "recover",
                (
                    "DEPLOYED" if mutant == "rollback" else "REJECTED",
                    epoch,
                    approved,
                    withdrawn,
                    mutant == "rollback",
                    epoch,
                ),
            )
        )
    if phase not in {"DEPLOYED", "REJECTED"}:
        nexts.append(("reject", ("REJECTED", epoch, approved, withdrawn, active, certified)))
    return nexts


@lru_cache(maxsize=64)
def explore(authorized=True, evidence=True, mutant="none", max_epoch=2):
    # phase, epoch, approval_epoch, withdrawn, active, certified_epoch
    initial = ("PROPOSED", 0, -1, False, False, -1)
    todo, parents = deque([initial]), {initial: None}
    transitions = 0
    violation = None
    while todo:
        s = todo.popleft()
        phase, epoch, approved, withdrawn, active, certified = s
        bad = active and (not authorized or not evidence or withdrawn or certified != epoch)
        if bad:
            violation = s
            break
        nexts = lifecycle_successors(s, authorized, evidence, mutant, max_epoch)
        for action, nxt in nexts:
            transitions += 1
            if nxt not in parents:
                parents[nxt] = (s, action)
                todo.append(nxt)
    trace = []
    if violation:
        cursor = violation
        while parents[cursor] is not None:
            prev, action = parents[cursor]
            trace.append({"action": action, "state": cursor})
            cursor = prev
        trace.reverse()
    return {
        "safe": violation is None,
        "states": len(parents),
        "transitions": transitions,
        "counterexample": trace,
        "bounds": {"proposals": 1, "epochs": max_epoch + 1},
        "authorized": authorized,
        "evidence": evidence,
        "mutant": mutant,
        "scope": "finite lifecycle abstraction; no liveness or implementation refinement proof",
    }


def verify_instance(state, policy, principal, evolution, base_state=None, origins=None):
    """Translate concrete metadata to independent graph constraints and lifecycle inputs."""
    nodes = {c.name: asdict(c) for c in state.components}
    active = set(nodes) - state.inactive
    problems = []
    target = nodes[evolution.target]
    if (principal, evolution.target, evolution.operation) not in policy.grants:
        problems.append("authorization")
    if target["kind"] in {"policy", "verifier"} or not target["mutable"]:
        problems.append("isolation")
    trusted_capabilities = (
        base_state.mapping()[evolution.target].capabilities if base_state is not None else None
    )
    ceiling = dict(policy.ceilings).get(evolution.target, trusted_capabilities)
    if ceiling is None:
        problems.append("missing trusted capability ceiling/base state")
        ceiling = ()
    if not set(target["capabilities"]) <= set(ceiling):
        problems.append("privilege")
    if base_state is not None:
        for name, old in base_state.mapping().items():
            if not old.mutable or old.kind in {"policy", "verifier"}:
                if nodes.get(name) != asdict(old) or (name in state.inactive) != (
                    name in base_state.inactive
                ):
                    problems.append("protected dependent isolation")
    if origins is not None:
        for n in active:
            key = (n, nodes[n]["version"])
            if key not in origins or (set(origins.get(key, ())) | {key}) & state.withdrawn:
                problems.append("version provenance withdrawal")
    for n in active:
        c = nodes[n]
        if (n, c["version"]) in state.withdrawn:
            problems.append("withdrawal/rollback")
        if not set(c["depends"] + c["parents"]) <= active:
            problems.append("dependency/provenance")
    # Kahn's algorithm provides an independent cycle check.
    remaining = {n: set(c["depends"] + c["parents"]) for n, c in nodes.items()}
    while remaining:
        leaves = {n for n, deps in remaining.items() if not deps}
        if not leaves:
            problems.append("cyclic or dangling dependency/provenance")
            break
        remaining = {n: deps - leaves for n, deps in remaining.items() if n not in leaves}
    report = dict(explore())
    if problems:
        report.update(safe=False, counterexample=problems)
    return report


def verification_suite():
    started = time.perf_counter()
    corrected = [explore(a, e) for a, e in product([False, True], repeat=2)]
    mutants = [explore(False, True, "authorization"), explore(True, False, "evidence")]
    mutants += [explore(True, True, name) for name in ["withdrawal", "rollback", "revalidation"]]
    return {
        "corrected": corrected,
        "mutants": mutants,
        "passed": all(x["safe"] for x in corrected) and all(not x["safe"] for x in mutants),
        "seconds": time.perf_counter() - started,
    }


def lifecycle_graph(authorized=True, evidence=True, max_epoch=2):
    initial = ("PROPOSED", 0, -1, False, False, -1)
    todo, states, edges = deque([initial]), {initial}, set()
    while todo:
        state = todo.popleft()
        for action, nxt in lifecycle_successors(state, authorized, evidence, max_epoch=max_epoch):
            edges.add((state, action, nxt))
            if nxt not in states:
                states.add(nxt)
                todo.append(nxt)
    return states, edges

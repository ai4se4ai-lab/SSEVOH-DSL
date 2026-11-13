"""Independent operational specification. Imports only immutable data types, never runtime checking helpers."""

from dataclasses import replace

from ssevoh.model import State


class RefReject(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise RefReject(message)


def graph_valid(components, inactive, withdrawn):
    names = set(components)
    reach = {n: set(c.depends) | set(c.parents) for n, c in components.items()}
    if not inactive <= names:
        return False
    for n, c in components.items():
        if not reach[n] <= names:
            return False
        if n not in inactive and ((n, c.version) in withdrawn or reach[n] & inactive):
            return False
    for k in sorted(names):
        for n in names:
            if k in reach[n]:
                reach[n] |= reach[k]
    return all(n not in reach[n] for n in names)


def initial_origins(state):
    cs = state.mapping()
    direct = {n: {(p, cs[p].version) for p in c.parents} for n, c in cs.items()}
    result = {n: set(refs) for n, refs in direct.items()}
    while True:
        expanded = {n: result[n] | set().union(*(result[p] for p in cs[n].parents)) for n in cs}
        if expanded == result:
            break
        result = expanded
    return {(n, cs[n].version): frozenset(v) for n, v in result.items()}


def transition(state, policy, e, principal, history, origins, evidence):
    cs = state.mapping()
    require(e.target in cs, "target")
    old = cs[e.target]
    require(e.operation in {"update", "withdraw", "rollback"}, "operation")
    require(all(n in cs for n in e.depends + e.parents), "declared references")
    require(old.mutable and old.kind not in {"policy", "verifier"}, "protected target")
    require((principal, e.target, e.operation) in policy.grants, "authorization")
    ceiling = set(dict(policy.ceilings).get(e.target, old.capabilities))
    require(set(e.capabilities) <= ceiling, "declared privilege ceiling")
    require(e.expected == old.version, "version precondition")
    require(
        e.precondition in {"active", "inactive", "any"} and e.postcondition in {"active", "inactive"},
        "condition type",
    )
    require(
        e.precondition == "any" or (e.target not in state.inactive) == (e.precondition == "active"),
        "active precondition",
    )
    impacted = {e.target}
    while True:
        added = {n for n, c in cs.items() if impacted.intersection(set(c.depends) | set(c.parents))}
        if added <= impacted:
            break
        impacted |= added
    q = set(state.inactive) | impacted
    w = set(state.withdrawn)
    lineage = dict(origins)
    if e.operation == "update":
        require(e.version > old.version and (e.target, e.version) not in history, "fresh version")
        require(set(old.parents) <= set(e.parents), "parent conservation")
        cs[e.target] = replace(
            old, version=e.version, depends=e.depends, parents=e.parents, capabilities=e.capabilities
        )
        q.discard(e.target)
        old_key = (old.name, old.version)
        refs = set(origins[old_key]) | {old_key}
        for parent in e.parents:
            parent_key = (parent, state.mapping()[parent].version)
            refs |= {parent_key} | set(origins[parent_key])
        lineage[(e.target, e.version)] = frozenset(refs)
    elif e.operation == "withdraw":
        require(e.version == old.version and e.postcondition == "inactive", "withdraw identity/postcondition")
        w.add((old.name, old.version))
    else:
        require((e.target, e.version) in history, "known history")
        cs[e.target] = history[(e.target, e.version)]
        require((e.target, e.version) not in w, "withdrawn recovery")
        q.discard(e.target)
    require(set(cs[e.target].capabilities) <= ceiling, "actual privilege ceiling")
    for name, c in state.mapping().items():
        if not c.mutable or c.kind in {"policy", "verifier"}:
            require(cs[name] == c and (name in q) == (name in state.inactive), "protected isolation")
    require((e.target not in q) == (e.postcondition == "active"), "postcondition")
    require(graph_valid(cs, q, w), "graph/state integrity")
    for name, c in cs.items():
        if name not in q:
            key = (name, c.version)
            require(key in lineage and not ((set(lineage[key]) | {key}) & w), "version provenance")
    require(
        all(evidence.get(name) is True for name in set(policy.validators) | set(e.requires)),
        "independent evidence",
    )
    candidate = State(tuple(cs.values()), frozenset(q), frozenset(w), state.revision + 1)
    updated = dict(history)
    updated.update({(c.name, c.version): c for c in candidate.components})
    return candidate, updated, lineage

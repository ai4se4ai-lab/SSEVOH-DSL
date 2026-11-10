"""Independent trusted metadata service. Proposal text cannot supply authority or evidence."""

import secrets
import threading
from copy import deepcopy
from dataclasses import asdict, dataclass
from types import MappingProxyType

from .compiler import compile_source
from .model import PROTECTED_KINDS, State, closure, digest, structural_errors


class Rejected(ValueError):
    pass


@dataclass(frozen=True)
class Approval:
    token: str
    proposal_hash: str
    base_hash: str
    evidence: tuple[tuple[str, bool], ...]
    lifecycle: tuple[str, ...]
    principal: str = ""
    policy_hash: str = ""
    registry_hash: str = ""
    candidate_hash: str = ""
    origins_hash: str = ""
    context_hash: str = ""


class SandboxEngine:
    def __init__(self, state, policy, validators=None):
        if structural_errors(state):
            raise Rejected("invalid initial state")
        self._lock = threading.RLock()
        self._state, self._policy = state, policy
        registered = {"structure": lambda s, e: not structural_errors(s)}
        registered.update(validators or {})
        if any(not callable(fn) for fn in registered.values()):
            raise Rejected("validator registry requires trusted callables")
        self._validators = MappingProxyType(registered)
        self._approvals, self._history, self._journal = {}, {}, []
        self._approved_origins, self._sources, self._decisions = {}, {}, []
        self._origins = {}
        cs = state.mapping()

        def origins(name):
            c = cs[name]
            key = (name, c.version)
            if key not in self._origins:
                found = set()
                for parent in c.parents:
                    found.add((parent, cs[parent].version))
                    found.update(origins(parent))
                self._origins[key] = frozenset(found)
            return self._origins[key]

        for c in state.components:
            self._history[(c.name, c.version)] = c
            origins(c.name)
        self._check_origins(state, self._origins)

    @property
    def state(self):
        with self._lock:
            return self._state

    @property
    def journal(self):
        with self._lock:
            return tuple(deepcopy(self._journal))

    @property
    def decision_log(self):
        with self._lock:
            return tuple(deepcopy(self._decisions))

    def snapshot(self):
        with self._lock:
            return self._state, tuple(deepcopy(self._journal))

    def _registry_hash(self):
        return digest(
            [
                (name, id(fn), getattr(getattr(fn, "__code__", None), "co_code", b"").hex())
                for name, fn in sorted(self._validators.items())
            ]
        )

    def _context_hash(self):
        return digest(
            [
                self._state.fingerprint(),
                self._policy.fingerprint(),
                self._registry_hash(),
                [(name, version, asdict(c)) for (name, version), c in sorted(self._history.items())],
                [(name, version, sorted(refs)) for (name, version), refs in sorted(self._origins.items())],
            ]
        )

    def _record_decision(self, status, principal, proposal, detail):
        event = {
            "index": len(self._decisions),
            "previous": self._decisions[-1]["hash"] if self._decisions else "0" * 64,
            "status": status,
            "principal": principal,
            "proposal": proposal,
            "detail": detail,
            "state": self._state.fingerprint(),
            "policy": self._policy.fingerprint(),
        }
        event["hash"] = digest(event)
        self._decisions.append(event)

    @staticmethod
    def _check_origins(state, origins):
        for c in state.components:
            if c.name not in state.inactive:
                key = (c.name, c.version)
                if key not in origins:
                    raise Rejected("missing version provenance")
                if (set(origins[key]) | {key}) & state.withdrawn:
                    raise Rejected(
                        "withdrawn version in active provenance; independent release is unsupported"
                    )

    def _lineage_for(self, candidate, e):
        key = (e.target, candidate.mapping()[e.target].version)
        if e.operation == "update":
            old = (e.target, self._state.mapping()[e.target].version)
            found = set(self._origins[old]) | {old}
            for parent in e.parents:
                parent_key = (parent, self._state.mapping()[parent].version)
                found.add(parent_key)
                found.update(self._origins[parent_key])
            refs = frozenset(found)
        else:
            refs = self._origins[key]
        all_origins = dict(self._origins)
        all_origins[key] = refs
        self._check_origins(candidate, all_origins)
        return refs

    def _candidate(self, e):
        current = self._state
        cs, inactive, withdrawn = current.mapping(), set(current.inactive), set(current.withdrawn)
        c = cs[e.target]
        if e.expected != c.version:
            raise Rejected("stale expected version")
        if e.precondition != "any" and (e.target not in inactive) != (e.precondition == "active"):
            raise Rejected("precondition failed")
        affected = closure(cs, {e.target}) - {e.target}
        if e.operation == "withdraw":
            if e.version != c.version:
                raise Rejected("withdraw must identify current version")
            withdrawn.add((c.name, c.version))
            inactive |= affected | {e.target}
        elif e.operation == "rollback":
            if (c.name, e.version) not in self._history:
                raise Rejected("unknown recovery version")
            if (c.name, e.version) in withdrawn:
                raise Rejected("rollback would restore withdrawn version")
            cs[c.name] = self._history[(c.name, e.version)]
            inactive.discard(c.name)
            inactive |= affected
        elif e.operation == "update":
            if not set(c.parents) <= set(e.parents):
                raise Rejected("provenance removal requires an independent release certificate; unsupported")
            if e.version <= c.version or (c.name, e.version) in self._history:
                raise Rejected("version reuse or non-increasing version")
            from dataclasses import replace

            cs[c.name] = replace(
                c, version=e.version, depends=e.depends, parents=e.parents, capabilities=e.capabilities
            )
            inactive.discard(c.name)
            inactive |= affected
        else:
            raise Rejected("unsupported operation")
        ceiling = dict(self._policy.ceilings).get(c.name, c.capabilities)
        if not set(cs[c.name].capabilities) <= set(ceiling):
            raise Rejected("recovery or update would expand capabilities beyond the current ceiling")
        if any(not cs[n].mutable or cs[n].kind in PROTECTED_KINDS for n in inactive - current.inactive):
            raise Rejected("operation would invalidate protected dependent")
        candidate = State(tuple(cs.values()), frozenset(inactive), frozenset(withdrawn), current.revision + 1)
        if (e.target not in inactive) != (e.postcondition == "active"):
            raise Rejected("postcondition failed")
        errors = structural_errors(candidate)
        if errors:
            raise Rejected("; ".join(errors))
        self._lineage_for(candidate, e)
        return candidate

    def approve(self, source, principal):
        with self._lock:
            context = self._context_hash()
            base_hash = self._state.fingerprint()
            policy_hash = self._policy.fingerprint()
            registry_hash = self._registry_hash()
            try:
                spec = compile_source(source, self._policy, principal)
                if State(spec.components).mapping() != self._state.mapping():
                    raise Rejected("declared snapshot differs from trusted state")
                e = spec.evolution
                candidate = self._candidate(e)
                refs = self._lineage_for(candidate, e)
                evidence = []
                for name in sorted(set(self._policy.validators + e.requires)):
                    if name not in self._validators:
                        raise Rejected(f"missing independent validator: {name}")
                    try:
                        ok = self._validators[name](candidate, e) is True
                    except Exception as exc:
                        raise Rejected(f"validator failed: {name}") from exc
                    if self._context_hash() != context:
                        raise Rejected("REVALIDATION_REQUIRED: validation changed the trusted context")
                    if not ok:
                        raise Rejected(f"negative independent evidence: {name}")
                    evidence.append((name, ok))
                from .verification import verify_instance

                origin_map = dict(self._origins)
                origin_map[(e.target, candidate.mapping()[e.target].version)] = refs
                formal = verify_instance(candidate, self._policy, principal, e, self._state, origin_map)
                if not formal["safe"]:
                    raise Rejected(f"verification failed: {formal['counterexample']}")
                if self._context_hash() != context:
                    raise Rejected("REVALIDATION_REQUIRED: approval context changed")
                approval = Approval(
                    secrets.token_hex(32),
                    digest(spec.ir()),
                    base_hash,
                    tuple(evidence),
                    ("PROPOSED", "ANALYSED", "VERIFIED", "APPROVED"),
                    principal,
                    policy_hash,
                    registry_hash,
                    candidate.fingerprint(),
                    digest(sorted(refs)),
                    context,
                )
                self._approvals[approval.token] = (approval, candidate, e, policy_hash)
                self._approved_origins[approval.token] = refs
                self._sources[approval.token] = source
                self._record_decision("APPROVED", principal, approval.proposal_hash, "")
                return approval
            except ValueError as exc:
                self._record_decision("REJECTED", principal, digest(source), str(exc))
                raise

    def _discard(self, token):
        self._approvals.pop(token, None)
        self._approved_origins.pop(token, None)
        self._sources.pop(token, None)

    def deploy(self, approval, *, fail_before_commit=False):
        with self._lock:
            try:
                if not isinstance(approval, Approval):
                    raise Rejected("invalid approval type")
                stored = self._approvals.get(approval.token)
                if stored is None or stored[0] != approval:
                    raise Rejected("unknown, forged, or consumed approval")
                _, candidate, e, policy_hash = stored
                if (
                    approval.base_hash != self._state.fingerprint()
                    or policy_hash != self._policy.fingerprint()
                    or approval.context_hash != self._context_hash()
                ):
                    self._discard(approval.token)
                    raise Rejected("REVALIDATION_REQUIRED: approval is stale")
                refs = self._approved_origins[approval.token]
                if approval.candidate_hash != candidate.fingerprint() or approval.origins_hash != digest(
                    sorted(refs)
                ):
                    raise Rejected("approval candidate/provenance binding failed")
                if structural_errors(candidate):
                    raise Rejected("commit invariant failed")
                origins = dict(self._origins)
                origins[(e.target, candidate.mapping()[e.target].version)] = refs
                self._check_origins(candidate, origins)
                if fail_before_commit:
                    raise Rejected("injected adapter failure; trusted state unchanged")
                event = {
                    "index": len(self._journal),
                    "previous": self._journal[-1]["hash"] if self._journal else "0" * 64,
                    "schema": "ssevoh-journal-v2",
                    "principal": approval.principal,
                    "policy": policy_hash,
                    "registry": approval.registry_hash,
                    "source": self._sources[approval.token],
                    "proposal": approval.proposal_hash,
                    "before": approval.base_hash,
                    "after": candidate.fingerprint(),
                    "operation": e.operation,
                    "target": e.target,
                    "origins": sorted(refs),
                    "evidence": list(approval.evidence),
                    "lifecycle": "DEPLOYED",
                }
                event["hash"] = digest(event)
                history = dict(self._history)
                history.update({(c.name, c.version): c for c in candidate.components})
                journal = self._journal + [event]
                self._history, self._origins, self._journal, self._state = (
                    history,
                    origins,
                    journal,
                    candidate,
                )
                self._discard(approval.token)
                self._record_decision("DEPLOYED", approval.principal, approval.proposal_hash, "")
                return self._state
            except ValueError as exc:
                self._record_decision(
                    "DEPLOYMENT_REJECTED",
                    getattr(approval, "principal", ""),
                    getattr(approval, "proposal_hash", ""),
                    str(exc),
                )
                raise


def validate_journal(journal, expected_head=None, initial_state_hash=None, final_state_hash=None):
    previous = "0" * 64
    prior_state = initial_state_hash
    try:
        for i, event in enumerate(journal):
            body = {k: v for k, v in event.items() if k != "hash"}
            if (
                event.get("index") != i
                or event.get("previous") != previous
                or digest(body) != event.get("hash")
            ):
                return False
            if (
                event.get("schema") != "ssevoh-journal-v2"
                or not event.get("principal")
                or event.get("lifecycle") != "DEPLOYED"
            ):
                return False
            if prior_state is not None and event.get("before") != prior_state:
                return False
            if not all(
                isinstance(item, (list, tuple)) and len(item) == 2 and item[1] is True
                for item in event["evidence"]
            ):
                return False
            prior_state = event["after"]
            previous = event["hash"]
    except (KeyError, TypeError, ValueError):
        return False
    return (expected_head is None or previous == expected_head) and (
        final_state_hash is None or prior_state == final_state_hash
    )


def replay_journal(initial_state, journal, policy, validators=None, expected_head=None):
    if not validate_journal(journal, expected_head, initial_state.fingerprint()):
        raise Rejected("invalid or unanchored-inconsistent journal")
    engine = SandboxEngine(initial_state, policy, validators)
    for event in journal:
        spec = compile_source(event["source"])
        if digest(spec.ir()) != event["proposal"] or event["policy"] != policy.fingerprint():
            raise Rejected("journal source/policy binding failed")
        if spec.evolution.operation != event["operation"] or spec.evolution.target != event["target"]:
            raise Rejected("journal effect binding failed")
        approval = engine.approve(event["source"], event["principal"])
        if tuple(tuple(x) for x in event["evidence"]) != approval.evidence:
            raise Rejected("journal evidence does not reproduce")
        engine.deploy(approval)
        if engine.state.fingerprint() != event["after"] or engine.journal[-1]["origins"] != event["origins"]:
            raise Rejected("journal post-state/provenance does not reproduce")
    return engine.state

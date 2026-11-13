"""Operator-owned policy, never accepted from proposal text."""

from dataclasses import dataclass

from .model import canonical_names, digest


@dataclass(frozen=True)
class Policy:
    # (principal, target, operation), exact names; no implicit wildcard.
    grants: frozenset[tuple[str, str, str]]
    ceilings: tuple[tuple[str, tuple[str, ...]], ...] = ()
    validators: tuple[str, ...] = ("structure",)

    def __post_init__(self):
        grants = frozenset(tuple(g) for g in self.grants)
        if any(
            len(g) != 3
            or not all(isinstance(x, str) and x for x in g)
            or g[2] not in {"update", "withdraw", "rollback"}
            for g in grants
        ):
            raise ValueError("invalid policy grant")
        ceilings = tuple((name, canonical_names(values)) for name, values in self.ceilings)
        if len({name for name, _ in ceilings}) != len(ceilings):
            raise ValueError("duplicate capability ceiling")
        object.__setattr__(self, "grants", grants)
        object.__setattr__(self, "ceilings", tuple(sorted(ceilings)))
        object.__setattr__(self, "validators", canonical_names(self.validators))

    def fingerprint(self):
        return digest([sorted(self.grants), self.ceilings, self.validators])

    def authorize(self, principal, component, evolution):
        if not component.mutable or component.kind in {"policy", "verifier"}:
            raise ValueError("protected component")
        if (principal, component.name, evolution.operation) not in self.grants:
            raise ValueError("principal lacks operation permission")
        ceiling = dict(self.ceilings).get(component.name, component.capabilities)
        if not set(evolution.capabilities) <= set(ceiling):
            raise ValueError("capability expansion exceeds operator ceiling")

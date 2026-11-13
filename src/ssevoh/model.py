"""Immutable intermediate representation; no executable proposal values."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


KINDS = frozenset({"skill", "memory", "tool", "workflow", "configuration", "policy", "verifier"})
PROTECTED_KINDS = frozenset({"policy", "verifier"})
NAME = re.compile(r"[A-Za-z_][A-Za-z_0-9.-]*\Z")


def canonical_names(values):
    result = tuple(values)
    if any(not isinstance(v, str) or not NAME.fullmatch(v) for v in result):
        raise ValueError("invalid identifier in component relation/capability list")
    if len(set(result)) != len(result):
        raise ValueError("duplicate relation/capability")
    return tuple(sorted(result))


@dataclass(frozen=True)
class Component:
    name: str
    kind: str
    version: int
    mutable: bool = True
    depends: tuple[str, ...] = ()
    parents: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.name, str) or not NAME.fullmatch(self.name) or self.kind not in KINDS:
            raise ValueError("invalid component identity/type")
        if type(self.version) is not int or self.version < 1 or type(self.mutable) is not bool:
            raise ValueError("component requires a positive integer version and boolean mutability")
        for key in ("depends", "parents", "capabilities"):
            object.__setattr__(self, key, canonical_names(getattr(self, key)))


@dataclass(frozen=True)
class Evolution:
    name: str
    operation: str
    target: str
    expected: int
    version: int
    depends: tuple[str, ...] = ()
    parents: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    precondition: str = "active"
    postcondition: str = "active"

    def __post_init__(self):
        for key in ("depends", "parents", "capabilities", "requires"):
            object.__setattr__(self, key, canonical_names(getattr(self, key)))


@dataclass(frozen=True)
class Specification:
    name: str
    components: tuple[Component, ...]
    evolution: Evolution

    def __post_init__(self):
        object.__setattr__(self, "components", tuple(sorted(self.components, key=lambda c: c.name)))

    def ir(self):
        return asdict(self)


@dataclass(frozen=True)
class State:
    components: tuple[Component, ...]
    inactive: frozenset[str] = frozenset()
    withdrawn: frozenset[tuple[str, int]] = frozenset()
    revision: int = 0

    def __post_init__(self):
        components = tuple(self.components)
        if any(not isinstance(c, Component) for c in components):
            raise ValueError("state components must be typed Component records")
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("state revision must be a nonnegative integer")
        withdrawn = frozenset(tuple(pair) for pair in self.withdrawn)
        if any(
            len(pair) != 2 or not isinstance(pair[0], str) or type(pair[1]) is not int or pair[1] < 1
            for pair in withdrawn
        ):
            raise ValueError("invalid withdrawn version identity")
        object.__setattr__(self, "components", tuple(sorted(components, key=lambda c: c.name)))
        object.__setattr__(self, "inactive", frozenset(self.inactive))
        object.__setattr__(self, "withdrawn", withdrawn)

    def mapping(self):
        return {c.name: c for c in self.components}

    def fingerprint(self):
        return digest(
            {
                "components": [asdict(c) for c in self.components],
                "inactive": sorted(self.inactive),
                "withdrawn": sorted(self.withdrawn),
                "revision": self.revision,
            }
        )


def closure(components, roots):
    """Reverse reachability over dependencies AND derivations, including roots."""
    reached = set(roots)
    reverse = {name: set() for name in components}
    for c in components.values():
        for dep in c.depends + c.parents:
            reverse.setdefault(dep, set()).add(c.name)
    todo = list(roots)
    while todo:
        for name in reverse.get(todo.pop(), ()):
            if name not in reached:
                reached.add(name)
                todo.append(name)
    return reached


def structural_errors(state):
    cs = state.mapping()
    errors = []
    if len(cs) != len(state.components):
        errors.append("duplicate component")
    if state.inactive - cs.keys():
        errors.append("unknown quarantined component")
    visiting, visited = set(), set()

    def visit(name):
        if name in visiting:
            errors.append(f"dependency/provenance cycle at {name}")
            return
        if name in visited:
            return
        visiting.add(name)
        c = cs[name]
        if c.version < 1:
            errors.append(f"invalid version: {name}")
        for dep in c.depends + c.parents:
            if dep not in cs:
                errors.append(f"unknown dependency/provenance: {dep}")
            else:
                visit(dep)
                if name not in state.inactive and dep in state.inactive:
                    errors.append(f"inactive dependency/provenance: {name}->{dep}")
        if name not in state.inactive and (name, c.version) in state.withdrawn:
            errors.append(f"withdrawn version active: {name}@{c.version}")
        visiting.remove(name)
        visited.add(name)

    for name in cs:
        visit(name)
    return tuple(errors)

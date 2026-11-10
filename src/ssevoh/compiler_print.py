"""Canonical text serializer for typed IR; no policy or execution logic."""

from .model import Specification


def print_specification(spec: Specification):
    def names(values):
        return "[" + ",".join(values) + "]"

    lines = [f"harness {spec.name} {{"]
    for c in spec.components:
        lines.append(
            f"component {c.name} {c.kind} {{ version {c.version}; mutable {str(c.mutable).lower()}; depends {names(c.depends)}; parents {names(c.parents)}; capabilities {names(c.capabilities)}; }}"
        )
    e = spec.evolution
    lines.append(
        f"evolution {e.name} {{ operation {e.operation}; target {e.target}; from {e.expected}; to {e.version}; depends {names(e.depends)}; parents {names(e.parents)}; capabilities {names(e.capabilities)}; requires {names(e.requires)}; expect {e.precondition}; ensure {e.postcondition}; }} }}"
    )
    return "\n".join(lines)

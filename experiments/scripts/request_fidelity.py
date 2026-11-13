"""Post hoc request fidelity; independent of whether the requested change is permitted."""

from functools import lru_cache

from ssevoh.benchmark import load_cases, make_engine, proposal
from ssevoh.compiler import Parser


@lru_cache(maxsize=1)
def contexts():
    result = {}
    for case in load_cases():
        engine = make_engine(case)
        for index, step in enumerate(case["steps"]):
            if step.get("mode", "normal") != "normal":
                continue
            source = proposal(engine.state, step)
            result[(case["id"], index)] = (engine.state, Parser(source).parse().evolution, source)
            if step["expect"] == "accept":
                engine.deploy(engine.approve(source, step.get("principal", "alice")))
    return result


def matches(row):
    context = contexts().get((row.get("scenario"), row.get("step")))
    if context is None:
        return None
    state, expected, _ = context
    try:
        spec = Parser(row.get("raw", {}).get("response", "")).parse()
    except ValueError:
        return False
    fields = ("operation", "target", "expected", "version", "depends", "parents", "capabilities", "requires", "postcondition")
    evolution = spec.evolution
    return (
        spec.components == state.components
        and all(getattr(evolution, name) == getattr(expected, name) for name in fields)
        and evolution.precondition in {"any", "inactive" if expected.target in state.inactive else "active"}
    )

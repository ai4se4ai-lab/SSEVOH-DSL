"""Explicit compile, verify and sandbox demo commands."""

import argparse
import json
from pathlib import Path

from .assurance import SandboxEngine
from .compiler import compile_source, ir_json
from .model import State
from .policy import Policy
from .verification import verification_suite


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["compile", "verify", "demo"])
    parser.add_argument("file", nargs="?")
    args = parser.parse_args()
    try:
        if args.command == "verify":
            result = verification_suite()
            print(json.dumps(result, indent=2))
            return 0 if result["passed"] else 1
        if not args.file:
            parser.error("compile and demo require a specification file")
        source = Path(args.file).read_text()
        spec = compile_source(source)
        if args.command == "compile":
            print(ir_json(spec))
        else:
            e = spec.evolution
            policy = Policy(frozenset({("demo-operator", e.target, e.operation)}))
            engine = SandboxEngine(State(spec.components), policy)
            approval = engine.approve(source, "demo-operator")
            engine.deploy(approval)
            print(json.dumps({"revision": engine.state.revision, "journal": engine.journal}, indent=2))
        return 0
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

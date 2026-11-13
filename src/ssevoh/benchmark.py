"""Hand-labeled HeartBench, explicit sandbox baselines, resumable JSONL output."""

import argparse
import json
import os
import time
from dataclasses import asdict
from pathlib import Path

from .assurance import Rejected, SandboxEngine
from .compiler import Parser, compile_source
from .model import Component, State, digest, structural_errors
from .policy import Policy

ROOT = Path(__file__).resolve().parents[2]


def load_cases():
    return json.loads((ROOT / "benchmark/scenarios/heartbench-v1.json").read_text())["scenarios"]


def make_engine(case):
    components = tuple(
        Component(**{k: tuple(v) if isinstance(v, list) else v for k, v in c.items()})
        for c in case["initial"]
    )
    grants = frozenset(("alice", c.name, op) for c in components for op in ("update", "withdraw", "rollback"))
    return SandboxEngine(State(components), Policy(grants), {"rejecting": lambda s, e: False})


def proposal(state, step):
    target = step.get("target", "a")
    c = state.mapping()[target]

    def names(xs):
        return "[" + ",".join(xs) + "]"

    lines = ["harness heartbench {"]
    for x in state.components:
        lines.append(
            f"component {x.name} {x.kind} {{ version {x.version}; mutable {str(x.mutable).lower()}; "
            f"depends {names(x.depends)}; parents {names(x.parents)}; "
            f"capabilities {names(x.capabilities)}; }}"
        )
    op = step.get("operation", "update")
    version = step.get("version", c.version if op == "withdraw" else c.version + 1)
    lines.append(
        f"evolution request {{ operation {op}; target {target}; from {c.version}; to {version}; "
        f"depends {names(step.get('depends', c.depends))}; parents {names(step.get('parents', c.parents))}; "
        f"capabilities {names(step.get('capabilities', c.capabilities))}; "
        f"requires {names(step.get('requires', []))}; expect any; "
        f"ensure {'inactive' if op == 'withdraw' else 'active'}; }} }}"
    )
    return "\n".join(lines)


def evaluate_case(case, baseline="B3", engine_factory=make_engine):
    engine = engine_factory(case)
    rows, held, held_source = [], None, None
    for index, step in enumerate(case["steps"]):
        before, error = engine.state, ""
        source = (
            held_source
            if step.get("mode") == "commit-held" and held_source is not None
            else proposal(before, step)
        )
        if step.get("mode") == "hold":
            held_source = source
        start = time.perf_counter()
        try:
            principal = step.get("principal", "alice")
            mode = step.get("mode", "normal")
            if baseline == "B0":
                # Admission-only unrestricted sandbox baseline: no trusted deployment claim.
                Parser(source).parse()
            elif baseline == "B1":
                spec = Parser(source).parse()
                if structural_errors(State(spec.components)):
                    raise Rejected("structural schema failure")
            elif baseline == "B2":
                spec = compile_source(source, engine._policy, principal)
                engine._candidate(spec.evolution)
                # Static baseline has neither validator execution nor deployment capability.
            elif mode == "commit-held":
                engine.deploy(held)
            else:
                approval = engine.approve(source, principal)
                if mode == "hold":
                    held = approval
                elif mode == "race":
                    second = engine.approve(source, principal)
                    engine.deploy(approval)
                    try:
                        engine.deploy(second)
                    except Rejected:
                        pass
                    else:
                        raise AssertionError("both conflicting approvals committed")
                elif mode in {"fault", "fault-retry"}:
                    try:
                        engine.deploy(approval, fail_before_commit=True)
                    except Rejected:
                        if engine.state != before:
                            raise AssertionError("partial state leaked")
                        if mode == "fault":
                            raise
                    engine.deploy(approval)
                else:
                    engine.deploy(approval)
            accepted = True
        except AssertionError as exc:
            if engine_factory is make_engine:
                raise
            accepted, error = True, "ablation safety assertion: " + str(exc)
        except ValueError as exc:
            accepted, error = False, str(exc)
        expected = step["expect"] == "accept"
        rows.append(
            {
                "scenario": case["id"],
                "step": index,
                "baseline": baseline,
                "accepted": accepted,
                "expected_accept": expected,
                "correct": accepted == expected,
                "false_accept": accepted and not expected,
                "false_reject": not accepted and expected,
                "expected_reason": step.get("reason"),
                "error": error,
                "reason_matches": accepted or step.get("reason", "") in error,
                "seconds": time.perf_counter() - start,
                "journal": engine.journal,
                "actual_state": {
                    "components": [asdict(c) for c in engine.state.components],
                    "inactive": sorted(engine.state.inactive),
                    "withdrawn": sorted(engine.state.withdrawn),
                    "revision": engine.state.revision,
                },
                "state_hash": engine.state.fingerprint(),
                "revision": engine.state.revision,
                "state_matches": (
                    {
                        "revision": engine.state.revision,
                        "inactive": sorted(engine.state.inactive),
                        "versions": {n: c.version for n, c in engine.state.mapping().items()},
                        "withdrawn": [list(x) for x in sorted(engine.state.withdrawn)],
                        "provenance_events": len(engine.journal),
                    }
                    == step.get("expected_state")
                ),
                "proposal_hash": digest(source),
                "events": len(engine.journal),
                "scope": "deployment" if baseline == "B3" else "admission-only baseline",
                "source": source,
            }
        )
        if baseline != "B3" and accepted and expected and step.get("mode", "normal") == "normal":
            # Advance context using the reference safe setup, never a baseline's unsafe change.
            try:
                engine.deploy(engine.approve(source, step.get("principal", "alice")))
            except ValueError:
                pass
    return rows


def append_record(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def read_records(path):
    path = Path(path)
    if not path.exists():
        return []
    raw = path.read_text()
    lines = raw.splitlines()
    records = []
    for i, line in enumerate(lines):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            if i != len(lines) - 1:
                raise
            # Interrupted final write: truncate to the last complete record before append.
            path.write_text("\n".join(lines[:i]) + ("\n" if i else ""))
    if records and raw and not raw.endswith("\n") and len(records) == len(lines):
        with path.open("a") as stream:
            stream.write("\n")
    return records


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--baseline", choices=["B0", "B1", "B2", "B3", "all"], default="B3")
    p.add_argument("--limit", type=int, default=0)
    a = p.parse_args()
    done = {(r["scenario"], r["step"], r["baseline"], r["repeat"]) for r in read_records(a.output)}
    cases = load_cases()[: a.limit or None]
    for baseline in ["B0", "B1", "B2", "B3"] if a.baseline == "all" else [a.baseline]:
        for repeat in range(a.repeats):
            for case in cases:
                for row in evaluate_case(case, baseline):
                    key = (row["scenario"], row["step"], baseline, repeat)
                    if key in done:
                        continue
                    row.update(
                        repeat=repeat,
                        benchmark="heartbench-v1",
                        cluster=os.environ.get("CLUSTER", "local"),
                        job_id=os.environ.get("SLURM_JOB_ID", "local-validation"),
                    )
                    append_record(a.output, row)
                    done.add(key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

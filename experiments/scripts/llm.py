"""Independent per-task Ollama generation with raw responses, model pins and GPU residency checks."""

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runtime import api, load_on_gpu, require_allocation

from ssevoh.benchmark import append_record, load_cases, make_engine, proposal, read_records
from ssevoh.compiler import Diagnostic, Parser, compile_source
from ssevoh.model import digest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))  # independent formal reference shipped in each frozen job source


def task_instances(limit=0):
    count = 0
    for case in load_cases():
        engine = make_engine(case)
        for index, step in enumerate(case["steps"]):
            if step.get("mode", "normal") != "normal":
                continue
            yield case, index, step, engine
            count += 1
            if limit and count >= limit:
                return
            if step["expect"] == "accept":
                text = proposal(engine.state, step)
                engine.deploy(engine.approve(text, step.get("principal", "alice")))


def independent_oracle(spec, engine, principal):
    """Operational reference oracle, independent of compiler/engine decision code.

    Benchmark evidence is fixed: structure is available; rejecting and unknown
    validators fail. Never invoke production validators to label their result.
    Include actual trusted history and version origins, including withdrawn ones.
    """
    from formal.assurance.reference import RefReject, transition

    cs = engine.state.mapping()
    if len(spec.components) != len(cs) or {c.name: c for c in spec.components} != cs:
        return False
    try:
        transition(
            engine.state, engine._policy, spec.evolution, principal,
            dict(engine._history), dict(engine._origins), {"structure": True},
        )
    except (RefReject, ValueError):
        return False
    return True


def run(model, output, lock, repeats, limit=0, qualification=False):
    require_allocation()
    pinned = json.loads(Path(lock).read_text())
    expected_digest = pinned["models"][model]["digest"]
    current = {x["name"]: x["digest"] for x in api("tags")["models"]}
    if current.get(model) != expected_digest:
        raise SystemExit("model digest changed since setup")
    load_on_gpu(model, expected_digest)
    decoding = json.loads((ROOT / "hpc/config/models.json").read_text())["decoding"]
    done = {(r["scenario"], r["step"], r["repeat"]) for r in read_records(output) if r.get("status") == "ok"}
    for case, index, step, engine in task_instances(limit):
        context_engine = engine
        for repeat in range(repeats):
            from ssevoh.assurance import SandboxEngine

            engine = SandboxEngine(context_engine.state, context_engine._policy, context_engine._validators)
            engine._history = dict(context_engine._history)
            engine._origins = dict(context_engine._origins)
            key = (case["id"], index, repeat)
            if key in done:
                continue
            # Context contains no expected labels, counterexamples, or golden proposal.
            request = {k: v for k, v in step.items() if k not in {"expect", "reason", "expected_state"}}
            prompt = (
                "Produce only an SSEVOH specification for this change request. Follow the grammar. "
                "Do not invent evidence or change unrelated components.\nGRAMMAR:\n"
                + (ROOT / "docs/language/grammar.ebnf").read_text()
                + "\nTrust rules: immutable components and policy/verifier kinds are protected; "
                "only alice may update, withdraw or rollback. Capabilities cannot expand. "
                "The structure validator is available. Other evidence is unavailable. "
                "Updates increase versions; withdraw uses the current version and ensure inactive. "
                "A component referring to an inactive ancestor cannot be reactivated.\n"
                + json.dumps(
                    {
                        "harness": [asdict(c) for c in engine.state.components],
                        "inactive": sorted(engine.state.inactive),
                        "withdrawn": sorted(engine.state.withdrawn),
                        "historical_versions": sorted(engine._history),
                        "request": request,
                        "principal": step.get("principal", "alice"),
                    },
                    sort_keys=True,
                )
            )
            start, started = time.perf_counter(), datetime.now(UTC).isoformat()
            payload = {
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": "5m",
                    "options": {
                        **decoding,
                        "seed": 1701 + repeat,
                        "num_thread": int(os.environ.get("SLURM_CPUS_PER_TASK", "4")),
                    },
                }
            attempts = Path(output).parent / "requests" / digest([model, case["id"], index, repeat])
            attempts.mkdir(parents=True, exist_ok=True)
            attempt = attempts / str(time.time_ns())
            attempt.with_suffix(".request.json").write_text(json.dumps(payload, indent=2))
            print(f"GENERATE_START model={model} scenario={case['id']} step={index} repeat={repeat}", flush=True)
            try:
                response = api("generate", payload)
            except Exception as exc:
                attempt.with_suffix(".failure.json").write_text(json.dumps({"error": str(exc), "utc": datetime.now(UTC).isoformat()}))
                raise
            attempt.with_suffix(".response.json").write_text(json.dumps(response, indent=2))
            raw = response.get("response", "")
            residency = api("ps")["models"]
            loaded = next((m for m in residency if m.get("digest") == expected_digest), None)
            fully_gpu = bool(loaded and loaded.get("size_vram", 0) >= loaded.get("size", 1))
            if not fully_gpu:
                raise SystemExit("model not fully resident on GPU; qualification failed")
            syntax, semantic, oracle, accepted, error, completion = False, False, None, False, "", False
            try:
                parsed = Parser(raw).parse()
                syntax = True
                oracle = independent_oracle(parsed, engine, step.get("principal", "alice"))
                golden = Parser(proposal(engine.state, step)).parse().evolution
                completion = all(
                    getattr(parsed.evolution, field) == getattr(golden, field)
                    for field in (
                        "operation",
                        "target",
                        "expected",
                        "version",
                        "depends",
                        "parents",
                        "capabilities",
                    )
                )
                compile_source(raw)
                semantic = True
                approval = engine.approve(raw, step.get("principal", "alice"))
                # Use a separate engine for each repeat to avoid contamination.
                engine.deploy(approval)
                accepted = True
            except (ValueError, Diagnostic) as exc:
                if isinstance(exc, Diagnostic) and exc.category != "syntax":
                    syntax = True
                error = str(exc)
            elapsed = time.perf_counter() - start
            record = {
                "status": "ok",
                "model": model,
                "model_digest": expected_digest,
                "scenario": case["id"],
                "step": index,
                "repeat": repeat,
                "seed": 1701 + repeat,
                "syntax_valid": syntax,
                "semantic_valid": semantic,
                "oracle_safe": oracle,
                "accepted": accepted,
                "false_accept": accepted and oracle is False,
                "false_reject": not accepted and oracle is True,
                "task_completion": completion,
                "error": error,
                "seconds": elapsed,
                "started_utc": started,
                "ended_utc": datetime.now(UTC).isoformat(),
                "raw": response,
                "prompt": prompt,
                "prompt_hash": digest(prompt),
                "prompt_version": "heartbench-prompt-v1",
                "options": {
                    **decoding,
                    "seed": 1701 + repeat,
                    "num_thread": int(os.environ.get("SLURM_CPUS_PER_TASK", "4")),
                },
                "benchmark": "heartbench-v1",
                "fully_gpu": fully_gpu,
                "tokens": response.get("eval_count", 0),
                "tokens_per_second": response.get("eval_count", 0)
                / max(response.get("eval_duration", 1) / 1e9, 1e-9),
                "load_seconds": response.get("load_duration", 0) / 1e9,
                "cluster": os.environ["CLUSTER"],
                "job_id": os.environ["SLURM_JOB_ID"],
                "array_job_id": os.environ.get("SLURM_ARRAY_JOB_ID"),
                "array_task_id": os.environ.get("SLURM_ARRAY_TASK_ID"),
                "run_id": os.environ["RUN_ID"],
                "qualification": qualification,
                "ollama": pinned["version"],
                "gpu": pinned["gpu"],
                "principal": step.get("principal", "alice"),
                "journal": engine.journal,
                "state_after": {
                    "components": [asdict(c) for c in engine.state.components],
                    "inactive": sorted(engine.state.inactive),
                    "withdrawn": sorted(engine.state.withdrawn),
                    "revision": engine.state.revision,
                },
                "output_hash": digest(response),
            }
            append_record(output, record)
            done.add(key)
            print(f"GENERATE_END model={model} scenario={case['id']} step={index} repeat={repeat} accepted={accepted} unsafe_deployed={record['false_accept']}", flush=True)
            if record["false_accept"]:
                raise SystemExit("Critical independent-oracle unsafe deployment; raw evidence retained")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--lock", required=True)
    p.add_argument("--repeats", type=int, default=5)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--qualification", action="store_true")
    a = p.parse_args()
    run(a.model, a.output, a.lock, a.repeats, a.limit, a.qualification)

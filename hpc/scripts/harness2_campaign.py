"""Harness² study coordinator using the existing fleet, Slurm graph, audit and collectors.

No alternate scheduler or inference runner. Qualification and full cells are owned once,
I/O is bounded, unqualified/auth-failed sites remain explicit, and only jobs compute.
"""

import fcntl
import hashlib
import json
import shlex
import shutil
import signal
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from campaign import complete, terminal_failure
from fleet import (
    ROOT,
    SITES,
    STATE,
    atomic_json,
    config,
    deploy,
    event,
    fetch,
    qualify_score,
    remote,
    ssh_args,
    status,
    submit,
)
from measure import collect_accounting, measure, records
from verify_transfer import verify

PROFILE = "harness2-controlled-v1"
PREFIX = "ssevoh-h2-"
LABEL = "harness2"
GRAPH = "hpc/config/profiles/harness2.json"
PATH = ROOT / "hpc/fetched/harness2-campaign.json"
STOP = False


def stop(signum, frame):
    global STOP
    STOP = True


def _rows_except(audit, item):
    """Audit with explicitly superseded cells removed (their raw evidence stays on disk)."""
    if not audit or not item.get("replaced_cells"):
        return audit
    return {**audit, "rows": [r for r in audit["rows"] if r.get("cell") not in set(item["replaced_cells"])]}


def submit_supplement(state, cfg, site, models, replaced_run, replaced_cells, reason):
    """Re-run explicitly listed cells on a site; the replaced run and its logs are retained."""
    source_current()
    original = next(i for i in state["full_runs"] if i["run_id"] == replaced_run)
    original["replaced_cells"] = sorted(replaced_cells)
    original["replacement_reason"] = reason
    deploy_profile(site, cfg)
    graph = json.loads((ROOT / GRAPH).read_text())
    graph["vars"]["MODELS"] = " ".join(models)
    for stage in graph["stages"]:
        if stage["name"] == "llm":
            stage["matrix"]["model"] = models
        if not stage.get("cpu_only"):
            stage["resources"]["gpus"] = cfg["clusters"][site]["gpus"]
    code = 'import pathlib,json,sys; p=pathlib.Path(sys.argv[1]); (p/"hpc/config/experiments.json").write_text(json.dumps(json.load(sys.stdin),indent=2))'
    subprocess.run(ssh_args(site, cfg) + [shlex.join(["python3", "-c", code, cfg["clusters"][site]["remote_dir"]])],
                   input=json.dumps(graph), text=True, check=True, timeout=90)
    run = PREFIX + "full-supplement-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + site
    state["full_runs"].append({"cluster": site, "run_id": run, "models": models, "state": "requested",
                               "supplements": replaced_run, "reason": reason})
    state["phase"] = "full_submitting"
    save(state)
    submit(site, cfg, False, run)
    state["full_runs"][-1]["state"] = "submitted"
    state["phase"] = "full_running"
    state.pop("error", None)
    save(state)
    event("supplement-submitted", site, {"run": run, "replaces": replaced_run, "cells": replaced_cells, "reason": reason})
    return run


def save(state):
    state["updated_utc"] = datetime.now(UTC).isoformat()
    atomic_json(PATH, state)


def data(site, run):
    path = ROOT / "hpc/fetched" / site / run / "audit.json"
    return json.loads(path.read_text()) if path.exists() else None


def source_current():
    for path in [
        ROOT / "formal/assurance/results/readiness.json",
        ROOT / "integrations/harness2/evidence/readiness.json",
    ]:
        r = json.loads(path.read_text())
        if not r["passed"] or any(
            not (ROOT / p).is_file() or hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h
            for p, h in r["source_sha256"].items()
        ):
            raise RuntimeError("Verification absent or stale: " + str(path))
    if PROFILE == "ssevoh-core-v2":
        path = ROOT / "experiments/evidence/core-study-readiness.json"
        report = json.loads(path.read_text())
        if not report.get("passed") or any(
            hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h
            for p, h in report["source_sha256"].items()
        ):
            raise RuntimeError("Core experiment worker verification is stale")


def deploy_profile(site, cfg):
    deploy(site, cfg)
    graph = json.loads((ROOT / GRAPH).read_text())
    for stage in graph["stages"]:
        if not stage.get("cpu_only"):
            stage["resources"]["gpus"] = cfg["clusters"][site]["gpus"]
    code = "import json,pathlib,sys; (pathlib.Path(sys.argv[1])/'hpc/config/experiments.json').write_text(json.dumps(json.load(sys.stdin),indent=2))"
    subprocess.run(
        ssh_args(site, cfg) + [shlex.join(["python3", "-c", code, cfg["clusters"][site]["remote_dir"]])],
        input=json.dumps(graph), text=True, check=True, timeout=90,
    )


def available_models(site, cfg):
    c = cfg["clusters"][site]
    code = """import hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]); result=[]
for path in (root/'manifests/registry.ollama.ai/library').glob('*/*'):
 value=json.loads(path.read_text()); layers=[value['config'],*value['layers']]
 valid=True; warnings=[]
 for r in layers:
  blob=root/'blobs'/r['digest'].replace(':','-')
  if not blob.is_file():valid=False;break
  actual=blob.stat().st_size
  if actual<=1048576:
   if hashlib.sha256(blob.read_bytes()).hexdigest()!=r['digest'].split(':')[1]:valid=False;break
   if actual!=r['size']:warnings.append({'layer':r['digest'],'declared_bytes':r['size'],'actual_bytes':actual,'sha256_verified':True})
  elif actual!=r['size']:valid=False;break
 if valid:result.append({'model':path.parent.name+':'+path.name,'digest':hashlib.sha256(path.read_bytes()).hexdigest(),'metadata_warnings':warnings})
print(json.dumps(result))
"""
    response = remote(site, shlex.join(["python3", "-c", code, c["work"] + "/models"]), cfg)
    expected = json.loads((ROOT / "hpc/config/models.frozen.json").read_text())["models"]
    found = json.loads(response.stdout)
    for record in found:
        if record.get("metadata_warnings"):
            event("cache-metadata-size-discrepancy", site, record)
    return [
        r["model"] for r in found if r["model"] in expected and r["digest"] == expected[r["model"]]["digest"]
    ]


def refresh(state, cfg):
    def one(site):
        ok = True
        try:
            prefixes = [PREFIX, "ssevoh-h2-"] if PROFILE == "ssevoh-core-v2" else [PREFIX]
            print(status(site, cfg, prefix=prefixes, strict=True), flush=True)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            event("audit-refresh-failed", site, str(exc))
            ok = False
        try:
            fetch(site, cfg)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            event("harness2-monitor-failed", site, str(exc))
            ok = False
        return site, ok

    with ThreadPoolExecutor(3) as pool:
        state["latest_reachable"] = dict(pool.map(one, SITES))


def refresh_report(build=False):
    """Local artifact publication only; all pooled analysis remains a Slurm job."""
    import sys

    subprocess.run(
        [sys.executable, str(ROOT / "experiments/scripts/update_report.py")],
        cwd=ROOT, check=True, timeout=60, stdout=subprocess.DEVNULL,
    )
    if build:
        subprocess.run(["bash", str(ROOT / "paper/build.sh")], cwd=ROOT, check=True, timeout=180)
        event("harness2-papers-refreshed", "local", {"source": "completed scheduled pooled analysis"})


def observations(state, cfg):
    for site, runs in state["qualification_runs"].items():
        for run in runs:
            audit = data(site, run)
            folder = ROOT / "hpc/fetched" / site / run
            if not complete(audit):
                continue
            if not (folder / "transfer.json").exists():
                verify(site, run, cfg)
            if not (folder / "accounting.tsv").exists():
                collect_accounting(site, folder, cfg)
    allowed = {(site, run) for site, runs in state["qualification_runs"].items() for run in runs}
    result = [r for r in measure(ROOT / "hpc/fetched") if (r["cluster"], r["run_id"]) in allowed]
    seen = {(r["cluster"], r["run_id"], r["model"]) for r in result}
    smoke = json.loads((ROOT / "hpc/config/models.json").read_text())["smoke_models"]
    for site, run in allowed:
        if terminal_failure(data(site, run)):
            for model in smoke:
                if (site, run, model) not in seen:
                    result.append({"cluster": site, "run_id": run, "model": model, "success": False})
    for model in smoke:
        if len({r["model_digest"] for r in result if r.get("success") and r["model"] == model}) > 1:
            raise RuntimeError("Smoke model identity mismatch")
    atomic_json(ROOT / f"hpc/fetched/{LABEL}-qualification.json", result)
    return result


def plan_from(observed, caches):
    scores = qualify_score(observed)
    if len(scores) < 2:
        raise ValueError(
            "At least two independently qualified clusters required for distributed full evaluation"
        )
    models = json.loads((ROOT / "hpc/config/models.json").read_text())["models"]
    load = {s: 0.0 for s in scores}
    assignment = {s: [] for s in scores}
    for model in reversed(models):
        eligible = [s for s in scores if model in caches.get(s, [])]
        if not eligible:
            raise ValueError("No qualified cluster has the pinned cached model: " + model)
        site = min(eligible, key=lambda s: load[s] + 1 / scores[s]["score"])
        assignment[site].append(model)
        load[site] += 1 / scores[site]["score"]
    return {
        "primary": max(scores, key=lambda s: scores[s]["score"]),
        "scores": scores,
        "assignment": assignment,
        "cache_constraints": caches,
        "unique_cells": len(models),
        "rule": "measured reliability/completion gates; weighted earliest finish subject to verified cached model identities; no hardware-only ranking",
        "limitations": "speed is measured on two smoke models; transfer-free cached ownership avoids large unnecessary model transfers",
    }


def submit_full(state, cfg):
    source_current()
    state["phase"] = "full_submitting"
    save(state)
    plan = state["plan"]
    for site, models in plan["assignment"].items():
        if not models:
            continue
        deploy_profile(site, cfg)  # qualification snapshots remain frozen
        graph = json.loads((ROOT / GRAPH).read_text())
        graph["vars"]["MODELS"] = " ".join(models)
        for stage in graph["stages"]:
            if stage["name"] == "llm":
                stage["matrix"]["model"] = models
                stage["array_throttle"] = 8 if PROFILE == "toolrepair-v1" else min(3, len(models))
            if not stage.get("cpu_only"):
                stage["resources"]["gpus"] = cfg["clusters"][site]["gpus"]
        code = 'import pathlib,json,sys; p=pathlib.Path(sys.argv[1]); d=json.load(sys.stdin); (p/"hpc/config/experiments.json").write_text(json.dumps(d["graph"],indent=2)); (p/"hpc/config/qualification-plan.json").write_text(json.dumps(d["plan"],indent=2))'
        subprocess.run(
            ssh_args(site, cfg) + [shlex.join(["python3", "-c", code, cfg["clusters"][site]["remote_dir"]])],
            input=json.dumps({"graph": graph, "plan": plan}),
            text=True,
            check=True,
            timeout=90,
        )
        run = PREFIX + "full-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + site
        state["full_runs"].append({"cluster": site, "run_id": run, "models": models, "state": "requested"})
        save(state)
        submit(site, cfg, False, run)
        state["full_runs"][-1]["state"] = "submitted"
        save(state)
    state["phase"] = "full_running"
    save(state)


def aggregate(state, cfg):
    if PROFILE == "ssevoh-core-v2":
        import campaign as original

        source_current()
        original.PATH = PATH
        if not original.full_summary(state):
            raise RuntimeError("Core five-model matrix is incomplete")
        deploy_profile(state["plan"]["primary"], cfg)
        original.submit_aggregate(state, cfg)
        return
    if PROFILE == "harness2-pilot-v2":
        return aggregate_pilot(state, cfg)
    if PROFILE == "toolrepair-v1":
        return aggregate_toolrepair(state, cfg)
    dest = ROOT / "artifacts/benchmark-results/harness2-full"
    dest.mkdir(parents=True, exist_ok=True)
    model_rows = []
    aux = []
    primary = state["plan"]["primary"]
    for item in state["full_runs"]:
        folder = ROOT / "hpc/fetched" / item["cluster"] / item["run_id"]
        model_rows.extend(r for r in records(folder) if r.get("schema") == "harness2-model-stream-v1")
        if item["cluster"] == primary:
            import tarfile

            with tarfile.open(folder / "results/deterministic.tar.gz") as archive:
                for member in archive:
                    if member.isfile() and member.name.endswith(".jsonl"):
                        aux.extend(
                            json.loads(line)
                            for line in archive.extractfile(member).read().decode().splitlines()
                        )
    keys = [(r["model"], r["repeat"]) for r in model_rows]
    if len(set(keys)) != len(keys):
        raise RuntimeError("Duplicate full model stream ownership")
    models = json.loads((ROOT / "hpc/config/models.json").read_text())["models"]
    expected = {(model, repeat) for model in models for repeat in range(5)}
    task_outcomes = sum(len(r["tasks"]) for r in model_rows)
    locks = json.loads((ROOT / "hpc/config/models.frozen.json").read_text())["models"]
    identities_match = all(r["model_digest"] == locks[r["model"]]["digest"] for r in model_rows)
    finished = (
        set(keys) == expected and len(model_rows) == 25 and task_outcomes == 50
        and len(aux) == 900 and identities_match
        and all(r.get("status") == "ok" and r.get("fully_gpu") is True for r in model_rows)
        and all(len(r["tasks"]) == 2 and {t["task"] for t in r["tasks"]} == {"ledger-1", "ledger-2"} for r in model_rows)
    )
    atomic_json(
        dest / "completeness.json",
        {
            "complete": finished,
            "records": len(model_rows),
            "expected": 25,
            "task_outcomes": task_outcomes,
            "deterministic_records": len(aux),
            "model_identities_match": identities_match,
            "runs": state["full_runs"],
        },
    )
    if not finished:
        raise RuntimeError("Full model stream matrix is incomplete")
    source_current()
    deploy_profile(primary, cfg)
    for name, rows in [("model-streams.jsonl", model_rows), ("controlled.jsonl", aux)]:
        (dest / name).write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    c = cfg["clusters"][primary]
    remote(primary, "mkdir -p " + shlex.quote(c["remote_dir"] + "/experiments/harness2-aggregate-input"), cfg)
    for name in ["model-streams.jsonl", "controlled.jsonl"]:
        subprocess.run(
            [
                "rsync",
                "-az",
                "--timeout=45",
                "-e",
                shlex.join(ssh_args(primary, cfg)[:-1]),
                str(dest / name),
                f"{cfg['username']}@{c['host']}:{c['remote_dir']}/experiments/harness2-aggregate-input/{name}",
            ],
            check=True,
            timeout=120,
        )
    graph = {
        "project": "ssevoh-h2-aggregate",
        "study": "harness2-controlled-v1",
        "require_gpu": True,
        "stages": [
            {
                "name": "analysis",
                "depends": [],
                "cpu_only": True,
                "resources": {"cpus": 2, "mem": "4G", "time": "00:20:00"},
                "sbatch_extra": ["--account=def-mbabaei_cpu"],
                "steps": [
                    {
                        "name": "pooled",
                        "cmd": 'python experiments/scripts/harness2_analyze.py --root experiments/harness2-aggregate-input --output "{RESULTS}/analysis"',
                        "produces": [
                            "analysis/summary.json",
                            "analysis/summary.csv",
                            "analysis/summary.md",
                            "analysis/summary.tex",
                        ],
                        "critical": True,
                    }
                ],
            },
            {
                "name": "collect",
                "depends": [{"stage": "analysis", "type": "afterany"}],
                "cpu_only": True,
                "resources": {"cpus": 1, "mem": "2G", "time": "00:10:00"},
                "sbatch_extra": ["--account=def-mbabaei_cpu"],
                "steps": [
                    {
                        "name": "persist",
                        "builtin": "collect",
                        "needs": ["analysis/summary.json"],
                        "critical": True,
                    }
                ],
            },
        ],
        "results": {"tables": [], "summaries": [], "copy": ["analysis/**"], "archive": []},
    }
    run = "ssevoh-h2-aggregate-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + primary
    code = """import json,pathlib,shutil,sys
root=pathlib.Path(sys.argv[1]); run=sys.argv[2]; sys.path.insert(0,str(root/'hpc/scripts')); import hpclib
p=root/'hpc/logs'/run/'config';p.mkdir(parents=True)
value=json.load(sys.stdin);(p/'experiments.resolved.json').write_text(json.dumps(hpclib.resolve(value,False),indent=2))
for name in ['cluster.env','requirements.txt','source-provenance.json']:
 if (root/'hpc/config'/name).exists():shutil.copy2(root/'hpc/config'/name,p/name)
"""
    subprocess.run(
        ssh_args(primary, cfg) + [shlex.join(["python3", "-c", code, c["remote_dir"], run])],
        input=json.dumps(graph),
        text=True,
        check=True,
        timeout=90,
    )
    state["aggregate_run"] = {"cluster": primary, "run_id": run}
    state["phase"] = "aggregate_requested"
    save(state)
    submit(primary, cfg, False, run)
    state["phase"] = "aggregate_running"
    save(state)


def aggregate_pilot(state, cfg):
    """v2 pooling: 5 models x 2 executable policies x 5 seeds, no deterministic records."""
    dest = ROOT / "artifacts/benchmark-results/harness2-pilot-v2"
    dest.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in state["full_runs"]:
        folder = ROOT / "hpc/fetched" / item["cluster"] / item["run_id"]
        replaced = {c.split(",")[0].removeprefix("model=") + "|" + c.split("policy=")[-1]
                    for c in item.get("replaced_cells", [])}
        rows.extend(r for r in records(folder) if r.get("schema") == "harness2-model-stream-v2"
                    and f"{r['model']}|{r['executable_policy']}" not in replaced)
    keys = [(r["model"], r["executable_policy"], r["repeat"]) for r in rows]
    if len(set(keys)) != len(keys):
        raise RuntimeError("Duplicate v2 model stream ownership")
    models = json.loads((ROOT / "hpc/config/models.json").read_text())["models"]
    expected = {(m, p, k) for m in models for p in ("catalog", "sandboxed_evidence") for k in range(5)}
    locks = json.loads((ROOT / "hpc/config/models.frozen.json").read_text())["models"]
    identities = all(r["model_digest"] == locks[r["model"]]["digest"] for r in rows)
    finished = (
        set(keys) == expected and identities
        and all(r.get("status") == "ok" and r.get("fully_gpu") is True and r.get("cohort") == "hpc" for r in rows)
        and all({t["task"] for t in r["tasks"]} == {"ledger-1", "ledger-2"} for r in rows)
    )
    atomic_json(dest / "completeness.json", {
        "complete": finished, "records": len(rows), "expected": len(expected),
        "model_identities_match": identities, "runs": state["full_runs"],
    })
    if not finished:
        raise RuntimeError("v2 model stream matrix is incomplete")
    (dest / "model-streams.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    # Pooled tables are descriptive counts over immutable collected rows; computed locally.
    import sys

    subprocess.run(
        [sys.executable, str(ROOT / "experiments/scripts/harness2_pilot_analyze.py"),
         "--root", str(dest), "--output", str(dest / "analysis")],
        check=True, timeout=120, cwd=ROOT,
    )
    state["phase"] = "complete"
    save(state)


def aggregate_toolrepair(state, cfg):
    """Pool ToolRepair-12: 5 models x 3 arms x 12 families x 3 seeds = 540 streams."""
    import sys

    dest = ROOT / "artifacts/benchmark-results/toolrepair-v1"
    dest.mkdir(parents=True, exist_ok=True)
    protocol = json.loads((ROOT / "experiments/toolrepair/protocol.json").read_text())
    rows = []
    for item in state["full_runs"]:
        folder = ROOT / "hpc/fetched" / item["cluster"] / item["run_id"]
        replaced = set(item.get("replaced_cells", []))
        rows.extend(r for r in records(folder) if r.get("schema") == "toolrepair-stream-v1"
                    and f"model={r['model']},arm={r['arm']},family={r['family']}" not in replaced)
    keys = [(r["model"], r["arm"], r["family"], r["repeat"]) for r in rows]
    if len(set(keys)) != len(keys):
        raise RuntimeError("Duplicate ToolRepair stream ownership")
    expected = {(m, a, f, k) for m in protocol["models"] for a in ("original", "catalog", "sandboxed_evidence")
                for f in protocol["families"] for k in range(len(protocol["seeds"]))}
    locks = json.loads((ROOT / "hpc/config/models.frozen.json").read_text())["models"]
    identities = all(r["model_digest"] == locks[r["model"]]["digest"] for r in rows)
    finished = (set(keys) == expected and identities
                and all(r.get("status") == "ok" and r.get("fully_gpu") is not False for r in rows)
                and all(len(r["tasks"]) == 3 for r in rows))
    atomic_json(dest / "completeness.json", {"complete": finished, "records": len(rows), "expected": len(expected),
                                             "model_identities_match": identities, "runs": state["full_runs"]})
    if not finished:
        raise RuntimeError("ToolRepair stream matrix is incomplete")
    (dest / "streams.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    subprocess.run([sys.executable, str(ROOT / "experiments/scripts/toolrepair_analyze.py"),
                    "--root", str(dest), "--output", str(dest / "analysis")], check=True, timeout=600, cwd=ROOT)
    state["phase"] = "complete"
    save(state)


def validate_resume(state, ledger):
    """Lost submission acknowledgements require ledger inspection, never blind retry."""
    if state["phase"] not in {"qualification", "full_running", "aggregate_running"}:
        raise RuntimeError("Interrupted submission phase; inspect remote job ledger before repair")
    if state["phase"] == "qualification" and state.get("full_runs"):
        raise RuntimeError("Full submission intent exists; automatic resubmission is forbidden")
    if state["phase"] == "full_running" and not state.get("full_runs"):
        raise RuntimeError("Full-running state has no recorded owners")
    acknowledged = {
        (r["cluster"], r["run_id"]) for r in ledger["runs"] if r.get("submission_state") == "submitted"
    }
    expected = {(site, run) for site, runs in state["qualification_runs"].items() for run in runs}
    expected |= {(r["cluster"], r["run_id"]) for r in state.get("full_runs", [])}
    if state.get("aggregate_run"):
        r = state["aggregate_run"]
        expected.add((r["cluster"], r["run_id"]))
    if not expected <= acknowledged:
        raise RuntimeError("Submission outcome is uncertain; inspect remote ledger before retry")


def run(args):
    global STOP, PROFILE, PREFIX, LABEL, GRAPH, PATH
    if args.profile == "toolrepair":
        PROFILE, PREFIX, LABEL = "toolrepair-v1", "ssevoh-tr-", "toolrepair-v1"
        GRAPH = "hpc/config/profiles/toolrepair-v1.json"
        PATH = ROOT / "hpc/fetched/toolrepair-v1-campaign.json"
    if args.profile == "pilot-v2":
        # Corrected-adapter ledger pilot; its own prefix, state and outputs (v1 is never touched).
        PROFILE, PREFIX, LABEL = "harness2-pilot-v2", "ssevoh-h2v2-", "harness2-pilot-v2"
        GRAPH = "hpc/config/profiles/harness2-pilot-v2.json"
        PATH = ROOT / "hpc/fetched/harness2-pilot-v2-campaign.json"
    if args.profile == "core":
        PROFILE, PREFIX, LABEL = "ssevoh-core-v2", "ssevoh-core-", "core"
        GRAPH = "hpc/config/profiles/ssevoh-original.json"
        PATH = ROOT / "hpc/fetched/core-campaign.json"
        previous = json.loads((ROOT / "hpc/fetched/harness2-campaign.json").read_text())
        if previous["phase"] != "complete":
            raise SystemExit("Core empirical continuation waits for completed Harness2 campaign")
    source_current()
    cfg = config()
    gate = json.loads((ROOT / "hpc/config/research-readiness.json").read_text())
    if not gate.get("empirical_allowed") or PROFILE not in gate.get("allowed_studies", []):
        raise SystemExit("Controlled study readiness gate is closed")
    PATH.parent.mkdir(parents=True, exist_ok=True)
    with (PATH.parent / f"{LABEL}-campaign.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        state = (
            json.loads(PATH.read_text())
            if PATH.exists()
            else {
                "phase": "qualification",
                "started_utc": datetime.now(UTC).isoformat(),
                "qualification_runs": {s: [] for s in SITES},
                "deployed": {},
                "caches": {},
                "full_runs": [],
                "profile": PROFILE,
                "models": json.loads((ROOT / "hpc/config/models.json").read_text())["models"],
            }
        )
        if state["phase"] == "qualification":
            for site in SITES:
                if state["deployed"].get(site):
                    try:
                        state["caches"][site] = available_models(site, cfg)
                    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                        state.setdefault("site_errors", {})[site] = str(exc)
                        event("cache-refresh-failed", site, str(exc))
                        # A metadata/auth outage cannot qualify an unverified current cache.
                        state["caches"][site] = []
        if state["phase"] in {"complete", "needs_attention"}:
            raise SystemExit("Inspect terminal campaign state before restart")
        try:
            validate_resume(state, json.loads(STATE.read_text()) if STATE.exists() else {"runs": []})
        except RuntimeError as exc:
            state["phase_at_error"] = state["phase"]
            state["phase"], state["error"] = "needs_attention", str(exc)
            save(state)
            raise
        save(state)

        for cycle in range(args.cycles):
            if STOP:
                break
            try:
                if state["phase"] == "qualification":
                    for site in SITES:
                        if state["deployed"].get(site):
                            continue
                        try:
                            deploy_profile(site, cfg)
                            state["caches"][site] = available_models(site, cfg)
                            state["deployed"][site] = True
                            save(state)
                        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                            state.setdefault("site_errors", {})[site] = str(exc)
                            save(state)
                            continue
                    for site in SITES:
                        if not state["deployed"].get(site):
                            continue
                        while len(state["qualification_runs"][site]) < 3:
                            run_id = (
                                PREFIX + "smoke-"
                                + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
                                + "-"
                                + site
                                + "-r"
                                + str(len(state["qualification_runs"][site]) + 1)
                            )
                            state["qualification_runs"][site].append(run_id)
                            save(state)
                            submit(site, cfg, True, run_id)
                refresh(state, cfg)
                if state["phase"] == "qualification":
                    measured = observations(state, cfg)
                    scores = qualify_score(measured)
                    elapsed = (
                        datetime.now(UTC) - datetime.fromisoformat(state["started_utc"])
                    ).total_seconds()
                    if (
                        args.auto_full
                        and len(scores) >= 2
                        and (len(scores) == 3 or elapsed >= args.qualification_minutes * 60)
                    ):
                        state["plan"] = plan_from(measured, state["caches"])
                        state["plan"]["unqualified_sites"] = [s for s in SITES if s not in scores]
                        atomic_json(ROOT / f"hpc/fetched/{LABEL}-plan.json", state["plan"])
                        save(state)
                        submit_full(state, cfg)
                elif state["phase"] == "full_running":
                    if any(terminal_failure(_rows_except(data(i["cluster"], i["run_id"]), i)) for i in state["full_runs"]):
                        raise RuntimeError("A full-run cell failed; inspect raw evidence before repair")
                    if all(complete(_rows_except(data(i["cluster"], i["run_id"]), i)) for i in state["full_runs"]):
                        for item in state["full_runs"]:
                            folder = ROOT / "hpc/fetched" / item["cluster"] / item["run_id"]
                            if not verify(item["cluster"], item["run_id"], cfg)["verified"]:
                                raise RuntimeError("Full result transfer failed content verification")
                            collect_accounting(item["cluster"], folder, cfg)
                        aggregate(state, cfg)
                        if state["phase"] == "complete":  # pilot-v2 pools locally; no aggregate job
                            break
                elif state["phase"] == "aggregate_running":
                    item = state["aggregate_run"]
                    audit = data(item["cluster"], item["run_id"])
                    if terminal_failure(audit):
                        raise RuntimeError("Pooled analysis failed; raw evidence retained")
                    if complete(audit):
                        if not verify(item["cluster"], item["run_id"], cfg)["verified"]:
                            raise RuntimeError("Pooled analysis transfer failed content verification")
                        run_root = (
                            ROOT / "hpc/fetched" / item["cluster"] / item["run_id"] / "results/raw/analysis"
                        )
                        dest = ROOT / ("artifacts/benchmark-results/full-campaign/analysis" if PROFILE == "ssevoh-core-v2" else "artifacts/benchmark-results/harness2-full/analysis")
                        shutil.copytree(run_root, dest, dirs_exist_ok=True)
                        state["phase"] = "complete"
                        save(state)
                        refresh_report(build=True)
                        if PROFILE == "harness2-controlled-v1" and "ssevoh-core-v2" in gate.get("allowed_studies", []):
                            import sys
                            subprocess.run([sys.executable, str(ROOT / "hpc/scripts/campaignctl.py"), "--profile", "core", "start", "--auto-full", "--cycles", str(args.cycles), "--interval", str(args.interval), "--qualification-minutes", str(args.qualification_minutes)], check=True, cwd=ROOT, timeout=30)
                        break
                save(state)
                refresh_report()
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                state["phase"] = "needs_attention"
                state["error"] = str(exc)
                save(state)
                raise
            if cycle + 1 < args.cycles and not STOP:
                for _ in range(args.interval):
                    if STOP:
                        break
                    time.sleep(1)
        state["controller_finished_utc"] = datetime.now(UTC).isoformat()
        save(state)

#!/usr/bin/env python3
"""Finite, restartable campaign controller: qualification → measured plan → staged models → full evaluation.

Only Slurm jobs compute. The controller invokes the upstream graph, audits/fetches files, verifies hashes,
and refreshes factual reports. It never changes a failed safety decision or substitutes a model.
"""

import argparse
import fcntl
import hashlib
import json
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from fleet import ROOT, SITES, STATE, atomic_json, config, event, fetch, make_plan, remote, status, submit
from measure import collect_accounting, measure, records
from transfer_models import transfer
from verify_transfer import verify

PATH = ROOT / "hpc/fetched/campaign.json"
STOP = False


def stopped(signum, frame):
    global STOP
    STOP = True


def audit_data(site, run_id):
    path = ROOT / "hpc/fetched" / site / run_id / "audit.json"
    return json.loads(path.read_text()) if path.exists() else None


def complete(data):
    return bool(data and data["rows"]) and all(
        r["state"] == "OK"
        and r.get("steps_ok", 0) == r.get("steps_total", -1)
        and r.get("slurm_state") == "COMPLETED"
        for r in data["rows"]
    )


def terminal_failure(data):
    return bool(data) and any(
        r.get("slurm_state", "").split(" ")[0]
        in {"FAILED", "CANCELLED", "OUT_OF_MEMORY", "NODE_FAIL", "TIMEOUT"}
        or r.get("state") in {"FAILED", "CANCELLED", "OUT_OF_MEMORY", "NODE_FAIL", "TIMEOUT"}
        for r in data["rows"]
    )


def worker_identity(run):
    path = run / "config/source-provenance.json"
    if not path.exists():
        return None
    files = json.loads(path.read_text())["files"]
    names = [
        "src/ssevoh/assurance.py",
        "src/ssevoh/compiler.py",
        "src/ssevoh/verification.py",
        "experiments/scripts/llm.py",
        "experiments/scripts/runtime.py",
        "benchmark/scenarios/heartbench-v1.json",
    ]
    return hashlib.sha256(json.dumps({n: files.get(n) for n in names}, sort_keys=True).encode()).hexdigest()


def refresh(cfg):
    def one(site):
        try:
            text = status(site, cfg)
            print(text, flush=True)
            fetch(site, cfg)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            event("monitor-failed", site, str(exc))
            print(f"{site}: {exc}", flush=True)

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(one, SITES))
    subprocess.run(
        [sys.executable, str(ROOT / "experiments/scripts/update_report.py")],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )


def save(state):
    state["updated_utc"] = datetime.now(UTC).isoformat()
    atomic_json(PATH, state)


def measurements(state, cfg):
    for site, runs in state["qualification_runs"].items():
        for run_id in runs:
            run = ROOT / "hpc/fetched" / site / run_id
            data = audit_data(site, run_id)
            if not complete(data):
                continue
            if not (run / "transfer.json").exists():
                verify(site, run_id, cfg)
            if not (run / "accounting.tsv").exists():
                collect_accounting(site, run, cfg)
    observed = measure(ROOT / "hpc/fetched")
    allowed = {(site, run) for site, rs in state["qualification_runs"].items() for run in rs}
    observed = [r for r in observed if (r["cluster"], r["run_id"]) in allowed]
    # Cross-site model identity must agree before any ranking.
    for model in ["qwen2.5-coder:7b", "phi4:14b"]:
        if len({r["model_digest"] for r in observed if r["model"] == model}) > 1:
            raise RuntimeError("Cross-site smoke model digest mismatch: " + model)
    # Failed/partial trials without raw rows must remain in reliability accounting.
    present = {(r["cluster"], r["run_id"], r["model"]) for r in observed}
    for site, runs in state["qualification_runs"].items():
        for run_id in runs:
            data = audit_data(site, run_id)
            if not data:
                continue
            terminal = any(
                r["state"] in {"FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL"}
                for r in data["rows"]
            )
            if terminal:
                for model in ["qwen2.5-coder:7b", "phi4:14b"]:
                    if (site, run_id, model) not in present:
                        observed.append(
                            {
                                "cluster": site,
                                "run_id": run_id,
                                "model": model,
                                "success": False,
                                "fully_gpu": False,
                                "recovery_ok": False,
                                "transfer_ok": False,
                            }
                        )
    atomic_json(ROOT / "hpc/fetched/qualification.json", observed)
    return observed


def model_lock(state, cfg):
    run = state.get("modelstage_run")
    if not run:
        return None
    path = cfg["clusters"]["fir"]["work"] + "/runs/" + run + "/results/setup/models.lock.json"
    result = remote("fir", shlex.join(["cat", path]), cfg, check=False)
    if result.returncode:
        return None
    value = json.loads(result.stdout)
    required = json.loads((ROOT / "hpc/config/models.json").read_text())["models"]
    if set(value["models"]) != set(required):
        raise RuntimeError("Model staging lock is incomplete")
    if not all(v.get("preflight", {}).get("fully_gpu") for v in value["models"].values()):
        raise RuntimeError("Model staging GPU preflight is incomplete")
    for model in required:
        for site, runs in state["qualification_runs"].items():
            for run_id in runs:
                other = ROOT / "hpc/fetched" / site / run_id / "results/raw/setup/models.lock.json"
                if other.exists():
                    models = json.loads(other.read_text())["models"]
                    if model in models and models[model]["digest"] != value["models"][model]["digest"]:
                        raise RuntimeError("Downloaded model differs from qualification identity")
    atomic_json(ROOT / "hpc/config/models.frozen.json", value)
    return value


def full_summary(state):
    target = ROOT / "artifacts/benchmark-results/full-campaign"
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in state["full_runs"]:
        run = ROOT / "hpc/fetched" / item["cluster"] / item["run_id"]
        rows.extend(r for r in records(run) if not r.get("qualification"))
    keys = [(r["model"], r["scenario"], r["step"], r["repeat"]) for r in rows]
    if len(set(keys)) != len(keys):
        raise RuntimeError("Duplicate full experiment cells")
    cases = json.loads((ROOT / "benchmark/scenarios/heartbench-v1.json").read_text())["scenarios"]
    expected = {
        (model, case["id"], index, repeat)
        for model in state["models"] for case in cases
        for index, step in enumerate(case["steps"]) if step.get("mode", "normal") == "normal"
        for repeat in range(5)
    }
    locks = json.loads((ROOT / "hpc/config/models.frozen.json").read_text())["models"]
    finished = set(keys) == expected and all(
        r["status"] == "ok" and r["fully_gpu"] is True and r["model_digest"] == locks[r["model"]]["digest"]
        for r in rows
    )
    with (target / "records.jsonl").open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    # Joining records is controller I/O; statistical computation is submitted as a Slurm job below.
    extra_rows = []
    auxiliary_counts = {}
    for item in state["full_runs"]:
        if item["cluster"] != state["plan"]["primary"]:
            continue  # side-study conditions have one owner; avoid duplicated per-site fixture samples
        run = ROOT / "hpc/fetched" / item["cluster"] / item["run_id"]
        for name in ["deterministic", "ablations", "scaling"]:
            before = len(extra_rows)
            archive = run / "results" / (name + ".tar.gz")
            if archive.exists():
                with tarfile.open(archive) as tar:
                    for member in tar:
                        if member.isfile() and member.name.endswith(".jsonl"):
                            extra_rows.extend(
                                json.loads(line)
                                for line in tar.extractfile(member).read().decode().splitlines()
                            )
            auxiliary_counts[name] = len(extra_rows) - before
    if state.get("profile") == "ssevoh-core-v2":
        finished = finished and auxiliary_counts == {"deterministic": 500, "ablations": 750, "scaling": 180}
    with (target / "auxiliary.jsonl").open("w") as f:
        for row in extra_rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    atomic_json(
        target / "completeness.json",
        {
            "records": len(rows),
            "expected": 500,
            "complete": finished,
            "per_model": {m: sum(r["model"] == m for r in rows) for m in state["models"]},
            "runs": state["full_runs"],
            "auxiliary_records": auxiliary_counts,
        },
    )
    return finished


def submit_aggregate(state, cfg):
    site = state["plan"]["primary"]
    c = cfg["clusters"][site]
    source = ROOT / "artifacts/benchmark-results/full-campaign"
    remote(site, "mkdir -p " + shlex.quote(c["remote_dir"] + "/experiments/aggregate-input"), cfg)
    from fleet import ssh_args

    for name in ["records.jsonl", "auxiliary.jsonl"]:
        subprocess.run(
            [
                "rsync",
                "-az",
                "--timeout=45",
                "-e",
                shlex.join(ssh_args(site, cfg)[:-1]),
                str(source / name),
                f"{cfg['username']}@{c['host']}:{c['remote_dir']}/experiments/aggregate-input/{name}",
            ],
            check=True,
            timeout=120,
        )
    graph = json.loads((ROOT / "hpc/config/aggregate.json").read_text())
    prefix = "ssevoh-aggregate-"
    if state.get("profile") == "ssevoh-core-v2":
        graph["study"] = "ssevoh-core-v2"
        prefix = "ssevoh-core-aggregate-"
    run_id = prefix + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + site
    code = """import json,pathlib,shutil,sys
root=pathlib.Path(sys.argv[1]); run=sys.argv[2]
sys.path.insert(0,str(root/'hpc/scripts'))
import hpclib
value=json.load(sys.stdin); folder=root/'hpc/logs'/run/'config'; folder.mkdir(parents=True)
(folder/'experiments.json').write_text(json.dumps(value,indent=2))
(folder/'experiments.resolved.json').write_text(json.dumps(hpclib.resolve(value,False),indent=2))
for name in ['cluster.env','requirements.txt','source-provenance.json']:
 if (root/'hpc/config'/name).exists():shutil.copy2(root/'hpc/config'/name,folder/name)
"""
    subprocess.run(
        ssh_args(site, cfg) + [shlex.join(["python3", "-c", code, c["remote_dir"], run_id])],
        input=json.dumps(graph),
        text=True,
        check=True,
        timeout=90,
    )
    state["aggregate_run"] = {"cluster": site, "run_id": run_id}
    state["phase"] = "aggregate_submitting"
    save(state)
    submit(site, cfg, False, run_id)
    state["phase"] = "aggregate_running"
    save(state)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile", choices=["ssevoh", "harness2", "core", "pilot-v2", "toolrepair"], default="ssevoh")
    p.add_argument("--cycles", type=int, default=180)
    p.add_argument("--interval", type=int, default=120)
    p.add_argument("--qualification-minutes", type=int, default=90)
    p.add_argument(
        "--auto-full",
        action="store_true",
        help="explicitly run the already-authorized full study after all gates pass",
    )
    a = p.parse_args()
    if a.interval < 60:
        raise SystemExit("interval must be >=60 seconds")
    if a.profile in {"harness2", "core", "pilot-v2", "toolrepair"}:
        from harness2_campaign import run

        return run(a)
    cfg = config()
    PATH.parent.mkdir(parents=True, exist_ok=True)
    with (PATH.parent / "campaign.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        signal.signal(signal.SIGTERM, stopped)
        signal.signal(signal.SIGINT, stopped)
        if PATH.exists():
            state = json.loads(PATH.read_text())
        else:
            existing = json.loads(STATE.read_text())["runs"]
            state = {
                "phase": "qualification",
                "runtime_protocol": "node-local-v2-preload-gpu",
                "started_utc": datetime.now(UTC).isoformat(),
                "qualification_runs": {
                    s: [next(r["run_id"] for r in reversed(existing) if r["cluster"] == s and r["smoke"])]
                    for s in SITES
                },
                "modelstage_run": next(
                    (r["run_id"] for r in reversed(existing) if "modelstage" in r["run_id"]), None
                ),
                "models": json.loads((ROOT / "hpc/config/models.json").read_text())["models"],
                "full_runs": [],
            }
            save(state)
        # Existing latest runs were submitted using the same staged worker source; schedule two disjoint trials/site.
        if state["phase"] == "qualification":
            for site in SITES:
                while len(state["qualification_runs"][site]) < 3:
                    run_id = (
                        "ssevoh-smoke-q2-"
                        + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
                        + "-"
                        + site
                        + "-r"
                        + str(len(state["qualification_runs"][site]) + 1)
                    )
                    state["qualification_runs"][site].append(run_id)
                    save(state)  # persist intent before remote mutation; never silently duplicate on restart
                    try:
                        submit(site, cfg, True, run_id)
                    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                        state["last_error"] = "Submission outcome must be inspected before retry: " + str(exc)
                        state["phase"] = "needs_attention"
                        save(state)
                        raise
        for cycle in range(a.cycles):
            if STOP:
                break
            refresh(cfg)
            try:
                if state["phase"] == "qualification":
                    observed = measurements(state, cfg)
                    identities = {
                        worker_identity(ROOT / "hpc/fetched" / site / run)
                        for site, rs in state["qualification_runs"].items()
                        for run in rs
                    }
                    identities.discard(None)
                    if len(identities) > 1:
                        raise RuntimeError(
                            "Qualification worker source differs between trials; do not mix these trials"
                        )
                    from fleet import qualify_score

                    scores = qualify_score(observed)
                    elapsed = (
                        datetime.now(UTC) - datetime.fromisoformat(state["started_utc"])
                    ).total_seconds()
                    if scores and (len(scores) == 3 or elapsed >= a.qualification_minutes * 60):
                        plan = make_plan(observed)
                        plan["unqualified_sites"] = [s for s in SITES if s not in scores]
                        plan["qualification_deadline_minutes"] = a.qualification_minutes
                        atomic_json(ROOT / "hpc/fetched/plan.json", plan)
                        state["plan"] = plan
                        state["phase"] = "model_staging"
                        save(state)
                        print(json.dumps(plan, indent=2), flush=True)
                if state["phase"] == "model_staging" and a.auto_full:
                    pins = model_lock(state, cfg)
                    if pins:
                        plan = json.loads((ROOT / "hpc/fetched/plan.json").read_text())
                        for site, models in plan["assignment"].items():
                            if models and site != "fir":
                                transfer("fir", site, models, cfg)
                        # Ship canonical pins as data; worker source remains the qualified release.
                        for site, models in plan["assignment"].items():
                            if not models:
                                continue
                            path = cfg["clusters"][site]["remote_dir"] + "/hpc/config/models.frozen.json"
                            code = (
                                "import pathlib,sys; pathlib.Path("
                                + repr(path)
                                + ").write_text(sys.stdin.read())"
                            )
                            from fleet import ssh_args

                            subprocess.run(
                                ssh_args(site, cfg) + [shlex.join(["python3", "-c", code])],
                                input=json.dumps(pins),
                                text=True,
                                check=True,
                            )
                        before = {r["run_id"] for r in json.loads(STATE.read_text())["runs"]}
                        subprocess.run(
                            [
                                sys.executable,
                                str(ROOT / "hpc/scripts/fleet.py"),
                                "full",
                                "--plan",
                                str(ROOT / "hpc/fetched/plan.json"),
                                "--measurements",
                                str(ROOT / "hpc/fetched/qualification.json"),
                            ],
                            check=True,
                            cwd=ROOT,
                        )
                        state["full_runs"] = [
                            r
                            for r in json.loads(STATE.read_text())["runs"]
                            if r["run_id"] not in before and r["run_id"].startswith("ssevoh-full-")
                        ]
                        state["phase"] = "full_running"
                        save(state)
                if state["phase"] == "full_running":
                    for r in state["full_runs"]:
                        data = audit_data(r["cluster"], r["run_id"])
                        if terminal_failure(data):
                            raise RuntimeError(
                                "Full job failed; inspect the recorded audit before explicit repair: "
                                + r["run_id"]
                            )
                    if all(complete(audit_data(r["cluster"], r["run_id"])) for r in state["full_runs"]):
                        for r in state["full_runs"]:
                            verify(r["cluster"], r["run_id"], cfg)
                        if full_summary(state):
                            submit_aggregate(state, cfg)
                if state["phase"] == "aggregate_running":
                    item = state["aggregate_run"]
                    data = audit_data(item["cluster"], item["run_id"])
                    if terminal_failure(data):
                        raise RuntimeError(
                            "Scheduled pooled analysis failed; inspect its audit: " + item["run_id"]
                        )
                    if complete(data):
                        verify(item["cluster"], item["run_id"], cfg)
                        run = ROOT / "hpc/fetched" / item["cluster"] / item["run_id"]
                        destination = ROOT / "artifacts/benchmark-results/full-campaign/analysis"
                        shutil.copytree(run / "results/raw/analysis", destination, dirs_exist_ok=True)
                        state["phase"] = "complete"
                        save(state)
                        subprocess.run(
                            [sys.executable, str(ROOT / "experiments/scripts/update_report.py")],
                            check=True,
                            cwd=ROOT,
                        )
                        subprocess.run(
                            ["bash", str(ROOT / "paper/build.sh")],
                            check=True,
                            cwd=ROOT,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        print(
                            "CAMPAIGN COMPLETE: 500 distinct model generations, scheduled aggregate analysis, and reports collected.",
                            flush=True,
                        )
                        return 0
                save(state)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                state["last_error"] = str(exc)
                state["phase_at_error"] = state["phase"]
                state["phase"] = "needs_attention"
                save(state)
                event("campaign-needs-attention", "all", str(exc))
                print(str(exc), flush=True)
                return 2
            if cycle + 1 < a.cycles:
                # Controller-side wait only. No sleep occurs in Slurm jobs.
                for _ in range(a.interval):
                    if STOP:
                        break
                    time.sleep(1)
        state["monitor_state"] = "stopped" if STOP else "finite_watch_finished"
        save(state)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

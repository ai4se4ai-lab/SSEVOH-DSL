#!/usr/bin/env python3
"""Thin multi-site extension around upstream use-hpc. Never duplicates its Slurm runner."""

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "hpc/config/fleet.local.json"
STATE = ROOT / "hpc/fetched/fleet-state.json"
SITES = ("fir", "narval", "rorqual")


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False
    ) as stream:
        temporary = Path(stream.name)
        json.dump(data, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def record_submission(site, run_id, smoke, **updates):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with STATE.with_suffix(".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(STATE.read_text()) if STATE.exists() else {"runs": []}
        item = next((r for r in state["runs"] if r["run_id"] == run_id and r["cluster"] == site), None)
        if item is None:
            item = {
                "cluster": site,
                "run_id": run_id,
                "smoke": smoke,
                "requested_utc": datetime.now(UTC).isoformat(),
            }
            state["runs"].append(item)
        item.update(updates)
        atomic_json(STATE, state)


def config():
    if not CONFIG.exists():
        raise SystemExit(
            "Create hpc/config/fleet.local.json from fleet.example.json and fill discovered paths/resources"
        )
    return json.loads(CONFIG.read_text())


def ssh_args(site, cfg):
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "ConnectTimeout=15",
        "-o",
        "ServerAliveInterval=60",
        "-o",
        "ServerAliveCountMax=3",
        "-o",
        f"ControlPath={ROOT}/hpc/.ssh/{site}",
        f"{cfg['username']}@{cfg['clusters'][site]['host']}",
    ]


def remote(site, command, cfg, check=True, timeout=90):
    result = subprocess.run(ssh_args(site, cfg) + [command], text=True, capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f"{site}: {result.stderr.strip() or result.stdout.strip()}")
    return result


def event(action, site, result):
    path = ROOT / "hpc/fetched/operations.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(
            json.dumps(
                {"utc": datetime.now(UTC).isoformat(), "action": action, "cluster": site, "result": result}
            )
            + "\n"
        )


def deploy(site, cfg):
    c = cfg["clusters"][site]
    for key in ["account", "remote_dir", "work", "gpus"]:
        if not c.get(key):
            raise ValueError(f"{site}: missing {key}")
    path = c["remote_dir"]
    if not path.startswith("/") or any(x.isspace() for x in path):
        raise ValueError("remote_dir must be an absolute path without spaces")
    remote(site, "mkdir -p " + shlex.quote(path), cfg)
    transport = shlex.join(ssh_args(site, cfg)[:-1])
    subprocess.run(
        [
            "rsync",
            "-az",
            "--exclude=.git",
            "--exclude=.venv",
            "--exclude=.cache",
            "--exclude=integrations/*/original/upstream",
            "--exclude=__pycache__",
            "--exclude=hpc/logs",
            "--exclude=hpc/fetched",
            "--exclude=hpc/.ssh",
            "--exclude=fleet.local.json",
            "-e",
            transport,
            str(ROOT) + "/",
            f"{cfg['username']}@{c['host']}:{path}/",
        ],
        check=True,
    )
    graph = json.loads((ROOT / "hpc/config/experiments.json").read_text())
    for stage in graph["stages"]:
        if not stage.get("cpu_only"):
            stage["resources"]["gpus"] = c["gpus"]
    # Site config is shipped as data through stdin; no untrusted shell interpolation.
    env = (ROOT / "hpc/config/cluster.env").read_text()
    for k, v in {
        "ACCOUNT": c["account"],
        "WORK": c["work"],
        "CLUSTER": site,
        "MODULES": c["modules"],
        "ALLOW_MODEL_DOWNLOAD": "1" if site == "fir" else "0",
    }.items():
        env += "\n" + k + "=" + shlex.quote(v) + "\n"
    data = json.dumps({"graph": graph, "env": env})
    script = (
        "import json,sys,pathlib; d=json.load(sys.stdin); p=pathlib.Path("
        + repr(path)
        + '); (p/"hpc/config/experiments.json").write_text(json.dumps(d["graph"],indent=2)); (p/"hpc/config/cluster.env").write_text(d["env"])'
    )
    subprocess.run(
        ssh_args(site, cfg) + [shlex.join(["python3", "-c", script])], input=data, text=True, check=True
    )
    provenance = {
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "git_status": subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True
        ),
        "deployed_utc": datetime.now(UTC).isoformat(),
        "files": {},
    }
    for folder in ["src", "tests", "benchmark", "formal", "experiments", "integrations", "hpc"]:
        for f in (ROOT / folder).rglob("*"):
            if (
                f.is_file()
                and not any(
                    x in f.parts
                    for x in ["__pycache__", ".ssh", "logs", "fetched", "original", ".git", ".cache"]
                )
                and f.name != "fleet.local.json"
            ):
                provenance["files"][str(f.relative_to(ROOT))] = hashlib.sha256(f.read_bytes()).hexdigest()
    script = (
        "import pathlib,sys; pathlib.Path("
        + repr(path + "/hpc/config/source-provenance.json")
        + ").write_text(sys.stdin.read())"
    )
    subprocess.run(
        ssh_args(site, cfg) + [shlex.join(["python3", "-c", script])],
        input=json.dumps(provenance, indent=2),
        text=True,
        check=True,
    )
    event(
        "deploy",
        site,
        {
            "remote_dir": path,
            "graph_sha256": hashlib.sha256(json.dumps(graph, sort_keys=True).encode()).hexdigest(),
        },
    )


def submit(site, cfg, smoke, run_id=None, only=None):
    gate_path = ROOT / "hpc/config/research-readiness.json"
    gate = json.loads(gate_path.read_text()) if gate_path.exists() else {}
    if gate.get("empirical_allowed") is not True:
        raise RuntimeError("Empirical work is locked until the core DSL readiness evidence passes")
    c = cfg["clusters"][site]
    run_id = (
        run_id
        or ("ssevoh-smoke-" if smoke else "ssevoh-full-")
        + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + site
    )
    args = ["env", "TZ=UTC", "python3", "hpc/slurm/submit.py", "--run-id", run_id]
    if smoke:
        args.append("--smoke")
    if only:
        args += ["--only", only]
    record_submission(site, run_id, smoke, submission_state="requested")
    try:
        # Source freezing can take minutes on a busy parallel filesystem.
        result = remote(site, "cd " + shlex.quote(c["remote_dir"]) + " && " + shlex.join(args), cfg, timeout=300)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        record_submission(site, run_id, smoke, submission_state="inspect_remote_ledger", error=str(exc))
        event("submit-outcome-uncertain", site, {"run_id": run_id, "error": str(exc)})
        raise
    print(result.stdout, flush=True)
    record_submission(
        site, run_id, smoke, submission_state="submitted", submitted_utc=datetime.now(UTC).isoformat()
    )
    event("submit", site, {"run_id": run_id, "smoke": smoke, "output": result.stdout})


def status(site, cfg, run_id=None, prefix=None, strict=False):
    c = cfg["clusters"][site]
    command = "cd " + shlex.quote(c["remote_dir"]) + " && TZ=UTC python3 hpc/scripts/audit_fleet.py "
    command += "--run-id " + shlex.quote(run_id) if run_id else ""
    if prefix:
        for item in ([prefix] if isinstance(prefix, str) else prefix):
            command += " --prefix " + shlex.quote(item)
    try:
        result = remote(site, command, cfg, check=False)
    except subprocess.TimeoutExpired:
        event("audit-timeout", site, {"run_id": run_id})
        if strict:
            raise RuntimeError(site + ": audit timed out; previous snapshot retained")
        return f"\n=== {site} ===\nAudit timed out; last fetched snapshot retained.\n"
    if strict and result.returncode:
        raise RuntimeError(site + ": audit failed: " + result.stderr[-1000:])
    return f"\n=== {site} ===\n{result.stdout}{result.stderr}"


def fetch(site, cfg, run_id=None, *, include_source=True):
    c = cfg["clusters"][site]
    if run_id is not None and not re.fullmatch(r"[A-Za-z0-9_.-]+", run_id):
        raise ValueError("Noncanonical run identifier")
    destination = ROOT / "hpc/fetched" / site
    if run_id:
        destination /= run_id
    destination.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    status_path = destination / "fetch-status.json"
    previous = json.loads(status_path.read_text()) if status_path.exists() else {}
    refresh = {
        "cluster": site,
        "started_utc": datetime.now(UTC).isoformat(),
        "last_success_utc": previous.get("last_success_utc"),
        "state": "fetching",
        "total_timeout_seconds": 120,
        "inactivity_timeout_seconds": 45,
    }
    atomic_json(status_path, refresh)
    try:
        subprocess.run(
            [
                "rsync",
                "-az",
                "--timeout=45",
                *(["--exclude=/source/"] if run_id and not include_source else []),
                "-e",
                shlex.join(ssh_args(site, cfg)[:-1]),
                f"{cfg['username']}@{c['host']}:{c['remote_dir']}/hpc/logs/" + ((run_id + "/") if run_id else ""),
                str(destination) + "/",
            ],
            check=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        refresh.update(
            state="failed", finished_utc=datetime.now(UTC).isoformat(), error=str(exc), partial_refresh=True
        )
        atomic_json(status_path, refresh)
        event("fetch-failed", site, refresh)
        raise
    refresh.update(state="complete", finished_utc=datetime.now(UTC).isoformat(), partial_refresh=False)
    refresh["last_success_utc"] = refresh["finished_utc"]
    atomic_json(status_path, refresh)
    seconds = time.perf_counter() - started
    for run in ([destination] if run_id else destination.iterdir()):
        if run.is_dir():
            atomic_json(
                run / "fetch-metric.json",
                {
                    "seconds": seconds,
                    "scope": ("single-run incremental fetch; source snapshot available separately" if run_id else "whole-site incremental fetch; conservative shared transfer cost"),
                },
            )
    event("fetch", site, {"local": str(destination), "seconds": seconds})


def fetch_sites(sites, cfg):
    """A failed site must not prevent collection from the other sites."""

    def one(site):
        try:
            fetch(site, cfg)
            return site, True, "logs refreshed"
        except (OSError, subprocess.SubprocessError) as exc:
            return site, False, str(exc)

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(one, sites))
    for site, ok, detail in results:
        print(f"{site}: {'OK' if ok else 'UNAVAILABLE; previous snapshot retained'}: {detail}", flush=True)
    return all(ok for _, ok, _ in results)


def qualify_score(records):
    """No hardware-only rankings: gate on ≥3 successful small AND large-model repetitions."""
    grouped = {}
    for r in records:
        grouped.setdefault(r["cluster"], []).append(r)
    scores = {}
    required = json.loads((ROOT / "hpc/config/models.json").read_text())["smoke_models"]
    for site, rows in grouped.items():
        good = [
            r
            for r in rows
            if r.get("success") is True
            and r.get("fully_gpu") is True
            and r.get("recovery_ok") is True
            and r.get("transfer_ok") is True
        ]
        counts = {m: len([r for r in good if r["model"] == m]) for m in required}
        runs = {m: {r["run_id"] for r in good if r["model"] == m} for m in required}
        if any(len(ids) < 3 for ids in runs.values()):
            continue
        trials = {}
        for row in rows:
            trials.setdefault((row["run_id"], row["model"]), []).append(row)
        successful = {key: values for key, values in trials.items() if all(v in good for v in values)}
        reliability = len(successful) / len(trials)
        reliability_adjusted = (len(successful) + 1) / (len(trials) + 2)
        costs = []
        for values in successful.values():
            r = values[0]
            elapsed = r.get(
                "job_elapsed_seconds", sum(v["generation_seconds"] for v in values) + r["startup_seconds"]
            )
            costs.append(r["queue_seconds"] + elapsed + r["transfer_seconds"])
        if not costs or any(not math.isfinite(c) or c <= 0 for c in costs):
            continue
        scores[site] = {
            "score": reliability_adjusted / (sum(costs) / len(costs)),
            "reliability": reliability,
            "successes": len(successful),
            "trials": len(trials),
            "mean_completion_seconds": sum(costs) / len(costs),
            "model_counts": counts,
            "independent_runs": {m: len(v) for m, v in runs.items()},
        }
    return scores


def make_plan(measurements):
    scores = qualify_score(measurements)
    if not scores:
        raise ValueError(
            "No cluster qualified; three measured end-to-end repetitions per smoke model are required"
        )
    models = json.loads((ROOT / "hpc/config/models.json").read_text())["models"]
    loads = {site: 0.0 for site in scores}
    assignment = {site: [] for site in scores}
    # Largest model first, weighted earliest-finish scheduling. Model name defines unique ownership.
    for model in reversed(models):
        site = min(scores, key=lambda c: loads[c] + 1 / scores[c]["score"])
        assignment[site].append(model)
        loads[site] += 1 / scores[site]["score"]
    return {
        "primary": max(scores, key=lambda c: scores[c]["score"]),
        "scores": scores,
        "assignment": assignment,
        "unique_cells": len(models),
        "rule": "qualified gates; reliability-adjusted end-to-end completion time; weighted earliest finish",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "command", choices=["probe", "deploy", "smoke", "status", "fetch", "watch", "plan", "full", "repair"]
    )
    p.add_argument("--cluster", choices=[*SITES, "all"], default="all")
    p.add_argument("--measurements")
    p.add_argument("--plan")
    p.add_argument("--run-id")
    p.add_argument("--only")
    p.add_argument("--prefix", action="append", default=[], help="limit audits to these run prefixes")
    p.add_argument("--interval", type=int, default=120)
    p.add_argument(
        "--cycles",
        type=int,
        default=1,
        help="finite watch cycles; explicit maintenance, never a hidden daemon",
    )
    a = p.parse_args()
    cfg = config()
    sites = SITES if a.cluster == "all" else [a.cluster]
    if a.command == "plan":
        plan = make_plan(json.loads(Path(a.measurements).read_text()))
        atomic_json(ROOT / "hpc/fetched/plan.json", plan)
        print(json.dumps(plan, indent=2))
        return
    if a.command == "full":
        if not a.plan:
            raise SystemExit("--plan required; full runs require an evidence-based assignment")
        plan = json.loads(Path(a.plan).read_text())
        prior = json.loads(STATE.read_text())["runs"] if STATE.exists() else []
        if any(r["run_id"].startswith("ssevoh-full-") for r in prior):
            raise SystemExit(
                "Full study already has run identities; use explicit per-run repair instead of duplicating model cells"
            )
        if not plan.get("assignment") or not plan.get("scores"):
            raise SystemExit("Unqualified plan")
        if not a.measurements:
            raise SystemExit("--measurements required to validate the plan against observed data")
        observed = json.loads(Path(a.measurements).read_text())
        recomputed = make_plan(observed)
        if plan["assignment"] != recomputed["assignment"] or plan["scores"] != recomputed["scores"]:
            raise SystemExit("Plan differs from actual qualification measurements")
        assigned = [m for models in plan["assignment"].values() for m in models]
        expected = json.loads((ROOT / "hpc/config/models.json").read_text())["models"]
        if sorted(assigned) != sorted(expected) or len(set(assigned)) != len(assigned):
            raise SystemExit("Every model must have exactly one owning cluster")
        for site, models in plan["assignment"].items():
            if not models:
                continue
            c = cfg["clusters"][site]
            graph = json.loads((ROOT / "hpc/config/experiments.json").read_text())
            graph["vars"]["MODELS"] = " ".join(models)
            for stage in graph["stages"]:
                if stage["name"] == "llm":
                    stage["matrix"]["model"] = models
                if not stage.get("cpu_only"):
                    stage["resources"]["gpus"] = c["gpus"]
            payload = {"graph": graph, "plan": plan}
            script = (
                "import json,sys,pathlib; d=json.load(sys.stdin); p=pathlib.Path("
                + repr(c["remote_dir"])
                + '); (p/"hpc/config/experiments.json").write_text(json.dumps(d["graph"],indent=2)); (p/"hpc/config/qualification-plan.json").write_text(json.dumps(d["plan"],indent=2))'
            )
            subprocess.run(
                ssh_args(site, cfg) + [shlex.join(["python3", "-c", script])],
                input=json.dumps(payload),
                text=True,
                check=True,
            )
            submit(site, cfg, False)
        return
    if a.command == "watch":
        import fcntl

        (ROOT / "hpc/fetched").mkdir(parents=True, exist_ok=True)
        campaign_guards = []
        for name in ["campaign.lock", "harness2-campaign.lock", "core-campaign.lock"]:
            campaign_guard = (ROOT / "hpc/fetched" / name).open("a")
            try:
                fcntl.flock(campaign_guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise SystemExit("A campaign already polls the fleet; use live.py for local snapshots or campaignctl.py status")
            campaign_guards.append(campaign_guard)
        if a.interval < 60:
            raise SystemExit("poll interval must be >=60 seconds")
        # One finite monitor owns a local advisory lock; auth failures surface for manual MFA.
        import fcntl

        lock_path = ROOT / "hpc/fetched/watch.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for cycle in range(a.cycles):
                with ThreadPoolExecutor(max_workers=3) as pool:
                    for text in pool.map(lambda site: status(site, cfg, prefix=a.prefix or None), sites):
                        print(text)
                fetch_sites(sites, cfg)
                subprocess.run([sys.executable, str(ROOT / "hpc/scripts/live.py"), "--output", str(ROOT / "hpc/fetched/fleet-live.md")], check=True, timeout=30)
                if cycle + 1 < a.cycles:
                    time.sleep(a.interval)
        return
    if a.command == "fetch":
        raise SystemExit(0 if fetch_sites(sites, cfg) else 1)
    if a.command == "status":
        with ThreadPoolExecutor(max_workers=3) as pool:
            for text in pool.map(lambda site: status(site, cfg, a.run_id, prefix=a.prefix or None), sites):
                print(text, flush=True)
        return
    for site in sites:
        if a.command == "probe":
            result = remote(
                site,
                'hostname; sshare -U -u "$USER" -n -P; sinfo -h -o "%P|%G|%l"; diskusage_report',
                cfg,
                check=False,
            )
            event("probe", site, {"rc": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
            print(site, result.stdout, result.stderr)
        elif a.command == "deploy":
            deploy(site, cfg)
        elif a.command == "smoke":
            submit(site, cfg, True)
        elif a.command == "repair":
            if not a.run_id or not a.only:
                raise SystemExit("repair requires --run-id and --only")
            submit(site, cfg, False, a.run_id, a.only)


if __name__ == "__main__":
    main()

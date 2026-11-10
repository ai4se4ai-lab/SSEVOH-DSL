#!/usr/bin/env python3
"""Collect closed qualification graphs and use the native Slurm runner for descriptive analysis."""

import hashlib
import json
import shlex
import subprocess
from datetime import UTC, datetime

from campaign import complete
from fleet import ROOT, atomic_json, config, deploy, remote, ssh_args, submit
from harness2_campaign import source_current
from measure import measure, records
from verify_transfer import verify


def main():
    state_path = ROOT / "hpc/fetched/qualification-report-campaign.json"
    if state_path.exists():
        raise SystemExit("Inspect the existing report ledger before retrying")
    source_current()
    cfg = config()
    states = {name: json.loads((ROOT / f"hpc/fetched/{name}-campaign.json").read_text()) for name in ["harness2", "core"]}
    trials, folders, samples = [], {}, []
    for study, state in states.items():
        for site, runs in state["qualification_runs"].items():
            for trial, run in enumerate(runs, 1):
                folder = ROOT / "hpc/fetched" / site / run
                audit = json.loads((folder / "audit.json").read_text())
                if any(r["slurm_state"].split()[0] not in {"COMPLETED", "CANCELLED", "FAILED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL"} for r in audit["rows"]):
                    raise SystemExit("A qualification graph is still active: " + run)
                if any(r["state"] != "OK" for r in audit["rows"] if r["stage"] in {"analysis", "collect"}):
                    raise SystemExit("Analysis and collection must finish before report: " + run)
                folders[(site, run)] = folder
                trials.append({"study": study, "cluster": site, "run_id": run, "trial": trial,
                               "full_graph_complete": complete(audit),
                               "censored_gpu_cells": sum(r["stage"] == "llm" and r["slurm_state"].startswith("CANCELLED") for r in audit["rows"])})
    # One accounting query per site for any newly closed trials, not repeated scheduler polling.
    for site in ["fir", "narval", "rorqual"]:
        missing = [f for (s, _), f in folders.items() if s == site and not (f / "accounting.tsv").exists()]
        if missing:
            jobs = sorted({line.split("\t")[0] for f in missing for line in (f / "jobs.tsv").read_text().splitlines()})
            result = remote(site, "TZ=UTC sacct -n -P -X -j " + ",".join(jobs) + " --format=JobID,State,Submit,Start,End,ElapsedRaw,AllocTRES%200", cfg)
            for folder in missing:
                (folder / "accounting.tsv").write_text(result.stdout)
    for item in trials:
        folder = folders[(item["cluster"], item["run_id"])]
        transfer = json.loads((folder / "transfer.json").read_text()) if (folder / "transfer.json").exists() else {}
        if not transfer.get("verified") and not verify(item["cluster"], item["run_id"], cfg)["verified"]:
            raise RuntimeError("Result transfer verification failed")
        if item["study"] != "core":
            continue
        manifest = json.loads((folder / "config/source-snapshot.json").read_text())["files"]
        names = ["src/ssevoh/assurance.py", "src/ssevoh/compiler.py", "src/ssevoh/model.py", "src/ssevoh/policy.py", "src/ssevoh/verification.py", "experiments/scripts/llm.py", "experiments/scripts/runtime.py", "formal/assurance/reference.py", "benchmark/scenarios/heartbench-v1.json", "docs/language/grammar.ebnf"]
        worker = hashlib.sha256(json.dumps({n: manifest[n] for n in names}, sort_keys=True).encode()).hexdigest()
        for row in records(folder):
            if row.get("status") != "ok" or row.get("fully_gpu") is not True:
                continue
            samples.append({"cluster": item["cluster"], "trial": item["trial"], "full_graph_complete": item["full_graph_complete"],
                            **{k: row[k] for k in ["model", "model_digest", "scenario", "step", "repeat", "options", "prompt_hash", "accepted", "syntax_valid"]},
                            "runtime": row["ollama"], "worker_source": worker,
                            "response_sha256": hashlib.sha256(row["raw"]["response"].encode()).hexdigest()})
    lookup = {(t["cluster"], t["run_id"]): t for t in trials}
    measurements = [dict(r, study=lookup[(r["cluster"], r["run_id"])]["study"]) for r in measure(ROOT / "hpc/fetched") if (r["cluster"], r["run_id"]) in lookup and r["success"]]
    value = {"measurements": measurements, "core_samples": samples, "trials": trials,
             "selection_frozen": {n: s["plan"] for n, s in states.items()}, "created_utc": datetime.now(UTC).isoformat()}
    dest = ROOT / "artifacts/benchmark-results/qualification"
    dest.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2) + "\n"
    (dest / "input.json").write_text(text)
    site = states["core"]["plan"]["primary"]
    run = "ssevoh-results-audit-qualification-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + site
    state = {"phase": "requested", "cluster": site, "run_id": run, "input_sha256": hashlib.sha256(text.encode()).hexdigest(), "created_utc": datetime.now(UTC).isoformat()}
    atomic_json(state_path, state)
    deploy(site, cfg)
    graph = {"project": "ssevoh-qualification-report", "study": "results-audit-v1", "require_gpu": True, "stages": [{
        "name": "report", "depends": [], "cpu_only": True, "resources": {"cpus": 2, "mem": "4G", "time": "00:15:00"},
        "sbatch_extra": ["--account=def-mbabaei_cpu"], "steps": [
            {"name": "matched", "cmd": 'python experiments/scripts/qualification_analyze.py --input "{REPO}/experiments/qualification-input.json" --output "{RESULTS}/analysis"', "needs": ["{REPO}/experiments/qualification-input.json"], "produces": ["analysis/summary.json", "analysis/summary.md", "analysis/infrastructure.csv", "analysis/matched-outputs.csv", "analysis/summary.tex"], "critical": True},
            {"name": "persist", "builtin": "collect", "needs": ["analysis/summary.json"], "critical": True}]}],
        "results": {"tables": [], "copy": ["analysis/**"], "archive": []}}
    code = """import json,pathlib,shutil,sys
root=pathlib.Path(sys.argv[1]);run=sys.argv[2];value=json.load(sys.stdin)
(root/'experiments/qualification-input.json').write_text(value['text'])
sys.path.insert(0,str(root/'hpc/scripts'));import hpclib
folder=root/'hpc/logs'/run/'config';folder.mkdir(parents=True)
(folder/'experiments.resolved.json').write_text(json.dumps(hpclib.resolve(value['graph'],False),indent=2))
for name in ['cluster.env','requirements.txt','source-provenance.json']:
 if (root/'hpc/config'/name).exists():shutil.copy2(root/'hpc/config'/name,folder/name)
"""
    subprocess.run(ssh_args(site, cfg) + [shlex.join(["python3", "-c", code, cfg["clusters"][site]["remote_dir"], run])], input=json.dumps({"graph": graph, "text": text}), text=True, check=True, timeout=90)
    submit(site, cfg, False, run)
    state["phase"] = "submitted"
    atomic_json(state_path, state)
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()

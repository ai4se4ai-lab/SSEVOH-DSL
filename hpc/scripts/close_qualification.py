#!/usr/bin/env python3
"""Close unused, wholly pending qualification graphs after both full studies complete."""

import argparse
import hashlib
import json
import shlex
import subprocess
from datetime import UTC, datetime

from fleet import ROOT, STATE, atomic_json, config, event, ssh_args


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", choices=["fir", "narval", "rorqual"], default="narval")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    owned = {(r["cluster"], r["run_id"]) for r in json.loads(STATE.read_text())["runs"]}
    trials = []
    for profile in ["harness2", "core"]:
        state = json.loads((ROOT / f"hpc/fetched/{profile}-campaign.json").read_text())
        if state["phase"] != "complete":
            raise SystemExit("Both completed campaigns are required before closeout")
        if args.site in state["plan"]["scores"]:
            continue
        for run in state["qualification_runs"][args.site]:
            folder = ROOT / "hpc/fetched" / args.site / run
            audit_path = folder / "audit.json"
            audit = json.loads(audit_path.read_text())
            jobs = [line.split("\t")[0] for line in (folder / "jobs.tsv").read_text().splitlines()]
            if (args.site, run) not in owned or not jobs or not all(j.isdigit() for j in jobs):
                raise SystemExit("Owned numeric job ledger required")
            if not audit["rows"] or any(r["state"] != "PENDING" or r["slurm_state"] != "PENDING" for r in audit["rows"]):
                raise SystemExit("A graph is not wholly pending; preserve it for inspection: " + run)
            if {r["job"].split("_")[0] for r in audit["rows"]} != set(jobs):
                raise SystemExit("Audit and submission job IDs disagree")
            trials.append({"profile": profile, "run_id": run, "jobs": jobs, "audit_utc": audit["time"],
                           "audit_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
                           "qualification_started_utc": state["started_utc"], "selection_deadline_minutes": 45})
    record = {"schema": "ssevoh-qualification-closeout-v1", "utc": datetime.now(UTC).isoformat(),
              "cluster": args.site, "trials": trials, "state": "planned",
              "reason": "right-censored at the predefined selection deadline; unused pending trials closed after both full studies completed",
              "gpu_performance": "unmeasured; cancellation is not a GPU failure",
              "reference": "https://slurm.schedmd.com/scancel.html"}
    if not args.apply or not trials:
        print(json.dumps(record, indent=2))
        return
    path = ROOT / f"artifacts/manifests/{args.site}-qualification-closeout.json"
    atomic_json(path, record)
    cfg = config()
    code = """import json,pathlib,subprocess,sys
value=json.load(sys.stdin); ids=[j for t in value['trials'] for j in t['jobs']]
query=subprocess.run(['squeue','--noheader','--jobs',','.join(ids),'--format=%i|%T'],text=True,capture_output=True)
rows=[line.strip().split('|') for line in query.stdout.splitlines() if line.strip()]
if query.returncode or {r[0].split('_')[0] for r in rows}!=set(ids) or any(r[1]!='PENDING' for r in rows):
 print(json.dumps({'state':'refused','queue_before':query.stdout,'error':query.stderr}));sys.exit(2)
result=subprocess.run(['scancel','--state=PENDING','--user='+sys.argv[2],*ids],text=True,capture_output=True)
value.update(state='cancel_requested' if result.returncode==0 else 'cancel_failed',queue_before=query.stdout,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
for trial in value['trials']:
 path=pathlib.Path(sys.argv[1])/'hpc/logs'/trial['run_id']/'qualification-closeout.json'
 path.write_text(json.dumps(value,indent=2)+'\\n')
print(json.dumps(value))
sys.exit(result.returncode)
"""
    result = subprocess.run(
        ssh_args(args.site, cfg) + [shlex.join(["python3", "-c", code, cfg["clusters"][args.site]["remote_dir"], cfg["username"]])],
        input=json.dumps(record), text=True, capture_output=True, timeout=90,
    )
    response = json.loads(result.stdout) if result.stdout.strip() else {"state": "unknown", "stderr": result.stderr}
    record.update(response)
    atomic_json(path, record)
    event("qualification-closeout", args.site, record)
    print(json.dumps({"state": record["state"], "graphs": len(trials), "job_ids": sum(len(t["jobs"]) for t in trials)}))
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()

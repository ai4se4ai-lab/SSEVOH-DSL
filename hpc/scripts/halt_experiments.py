#!/usr/bin/env python3
"""Enforce the user's formal-first order. Cancel only this repository's recorded jobs; preserve artifacts."""

import json
import shlex
import subprocess

from fleet import ROOT, SITES, atomic_json, config, event, ssh_args

cfg = config()
gate = (ROOT / "hpc/config/research-readiness.json").read_text()
for site in SITES:
    c = cfg["clusters"][site]
    script = (
        "import pathlib,sys; pathlib.Path("
        + repr(c["remote_dir"] + "/hpc/config/research-readiness.json")
        + ").write_text(sys.stdin.read())"
    )
    subprocess.run(
        ssh_args(site, cfg) + [shlex.join(["python3", "-c", script])], input=gate, text=True, check=True
    )
    subprocess.run(
        [
            "rsync",
            "-az",
            "-e",
            shlex.join(ssh_args(site, cfg)[:-1]),
            str(ROOT / "hpc/slurm/submit.py"),
            f"{cfg['username']}@{c['host']}:{c['remote_dir']}/hpc/slurm/submit.py",
        ],
        check=True,
    )
    script = """import pathlib,subprocess,json,sys
root=pathlib.Path(sys.argv[1]); user=sys.argv[2]
ids=sorted({line.split('\\t')[0] for path in (root/'hpc/logs').glob('*/jobs.tsv') for line in path.read_text().splitlines()})
if not all(i.isdigit() for i in ids):raise SystemExit('Unexpected ledger job identifier; cancellation refused')
result=subprocess.run(['scancel','--user',user,*ids],capture_output=True,text=True,check=False) if ids else None
print(json.dumps({'recorded_job_ids':ids,'returncode':result.returncode if result else 0,'stderr':result.stderr if result else ''}))
"""
    result = subprocess.run(
        ssh_args(site, cfg) + [shlex.join(["python3", "-c", script, c["remote_dir"], cfg["username"]])],
        capture_output=True,
        text=True,
        check=True,
    )
    record = json.loads(result.stdout)
    event("formal-first-halt", site, record)
    print(site, record, flush=True)
path = ROOT / "hpc/fetched/campaign.json"
if path.exists():
    state = json.loads(path.read_text())
    state["phase_before_formal_hold"] = state["phase"]
    state["phase"] = "paused_for_formal_readiness"
    state["empirical_allowed"] = False
    atomic_json(path, state)

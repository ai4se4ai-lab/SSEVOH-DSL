#!/usr/bin/env python3
"""Submit the existing CPU-only graph for diagnostics of unchanged collected samples."""

import argparse
import hashlib
import json
import re
import shlex
import subprocess
from datetime import UTC, datetime

from fleet import ROOT, atomic_json, config, deploy, ssh_args, submit
from harness2_campaign import source_current


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision")
    parser.add_argument("--core-only", action="store_true")
    args = parser.parse_args()
    if args.revision and not re.fullmatch(r"[a-z0-9-]+", args.revision):
        parser.error("revision must use lowercase letters, numbers and hyphens")
    suffix = "-" + args.revision if args.revision else ""
    state_path = ROOT / f"hpc/fetched/results-audit{suffix}-campaign.json"
    if state_path.exists():
        raise SystemExit("An analysis revision is already recorded; inspect its ledger before any retry")
    source_current()
    states = [json.loads((ROOT / f"hpc/fetched/{name}-campaign.json").read_text()) for name in ["core", "harness2"]]
    if any(s["phase"] != "complete" for s in states) or len({s["plan"]["primary"] for s in states}) != 1:
        raise SystemExit("Completed campaigns with a common pooled-data owner are required")
    site = states[0]["plan"]["primary"]
    cfg = config()
    pairs = {
        "experiments/aggregate-input/records.jsonl": "artifacts/benchmark-results/full-campaign/records.jsonl",
        "experiments/aggregate-input/auxiliary.jsonl": "artifacts/benchmark-results/full-campaign/auxiliary.jsonl",
        "experiments/harness2-aggregate-input/model-streams.jsonl": "artifacts/benchmark-results/harness2-full/model-streams.jsonl",
        "experiments/harness2-aggregate-input/controlled.jsonl": "artifacts/benchmark-results/harness2-full/controlled.jsonl",
    }
    hashes = {remote: hashlib.sha256((ROOT / local).read_bytes()).hexdigest() for remote, local in pairs.items()}
    graph = json.loads((ROOT / "hpc/config/profiles/results-audit.json").read_text())
    if args.core_only:
        graph["stages"] = [s for s in graph["stages"] if s["name"] != "harness2_analysis"]
        for stage in graph["stages"]:
            if stage["name"] == "collect":
                stage["depends"] = [d for d in stage["depends"] if d["stage"] != "harness2_analysis"]
                stage["steps"][0]["needs"] = [n for n in stage["steps"][0]["needs"] if not n.startswith("harness2-analysis/")]
        graph["results"]["copy"] = ["core-analysis/**"]
    run = "ssevoh-results-audit" + suffix + "-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + site
    state = {"phase": "requested", "run_id": run, "cluster": site, "input_sha256": hashes,
             "revision": args.revision, "core_only": args.core_only,
             "created_utc": datetime.now(UTC).isoformat(), "reason": "add protocol diagnostics and legitimate-action timing; preserve all original samples"}
    atomic_json(state_path, state)
    try:
        deploy(site, cfg)
        code = """import hashlib,json,pathlib,shutil,sys
root=pathlib.Path(sys.argv[1]);run=sys.argv[2];value=json.load(sys.stdin)
for name,expected in value['hashes'].items():
 if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:raise RuntimeError('Input identity mismatch: '+name)
sys.path.insert(0,str(root/'hpc/scripts'));import hpclib
folder=root/'hpc/logs'/run/'config';folder.mkdir(parents=True)
(folder/'experiments.resolved.json').write_text(json.dumps(hpclib.resolve(value['graph'],False),indent=2))
(folder/'input-sha256.json').write_text(json.dumps(value['hashes'],indent=2))
for name in ['cluster.env','requirements.txt','source-provenance.json']:
 if (root/'hpc/config'/name).exists():shutil.copy2(root/'hpc/config'/name,folder/name)
"""
        subprocess.run(
            ssh_args(site, cfg) + [shlex.join(["python3", "-c", code, cfg["clusters"][site]["remote_dir"], run])],
            input=json.dumps({"graph": graph, "hashes": hashes}), text=True, check=True, timeout=90,
        )
        submit(site, cfg, False, run)
        state["phase"] = "submitted"
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        state["phase"], state["error"] = "needs_attention", str(exc)
        raise
    finally:
        atomic_json(state_path, state)
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()

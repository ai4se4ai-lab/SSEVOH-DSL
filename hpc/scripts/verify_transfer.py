#!/usr/bin/env python3
"""Verify fetched collected results against remote content hashes; source hashing is light result I/O only."""

import argparse
import hashlib
import json
import shlex
import time

from fleet import ROOT, atomic_json, config, remote


def verify(site, run_id, cfg):
    start = time.perf_counter()
    root = ROOT / "hpc/fetched" / site / run_id
    remote_root = cfg["clusters"][site]["remote_dir"] + "/hpc/logs/" + run_id + "/results"
    code = """import pathlib,hashlib,json
p=pathlib.Path(__import__('sys').argv[1])
print(json.dumps({str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in p.rglob('*') if f.is_file()}))
"""
    result = remote(site, shlex.join(["python3", "-c", code, remote_root]), cfg)
    hashes = json.loads(result.stdout)
    valid = bool(hashes) and all(
        (root / "results" / name).exists()
        and hashlib.sha256((root / "results" / name).read_bytes()).hexdigest() == value
        for name, value in hashes.items()
    )
    fetch = (
        json.loads((root / "fetch-metric.json").read_text()) if (root / "fetch-metric.json").exists() else {}
    )
    record = {
        "verified": valid,
        "files": hashes,
        "seconds": time.perf_counter() - start + fetch.get("seconds", 0),
        "scope": "verification RPC and local hashing; fetch duration recorded separately by fleet operations",
    }
    atomic_json(root / "transfer.json", record)
    return record


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--cluster", required=True)
    p.add_argument("--run-id", required=True)
    a = p.parse_args()
    result = verify(a.cluster, a.run_id, config())
    print(json.dumps({"verified": result["verified"], "files": len(result["files"])}))
    if not result["verified"]:
        raise SystemExit(1)

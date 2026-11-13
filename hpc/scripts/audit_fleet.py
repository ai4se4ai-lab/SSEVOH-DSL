#!/usr/bin/env python3
"""Audit every run at one site with one shared squeue/sacct snapshot."""

import argparse
import json
import re

import audit


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-id")
    p.add_argument("--prefix", action="append", default=[])
    p.add_argument("--summary", action="store_true")
    a = p.parse_args()
    runs = sorted((audit.H.HPC / "logs").glob("*"))
    runs = [
        r
        for r in runs
        if (r / "config/experiments.resolved.json").exists()
        and (not a.run_id or r.name == a.run_id)
        and (not a.prefix or any(r.name.startswith(prefix) for prefix in a.prefix))
    ]
    ids = set()
    for run in runs:
        if (run / "jobs.tsv").exists():
            ids.update(line.split("\t")[0] for line in (run / "jobs.tsv").read_text().splitlines())
    cached = audit.slurm(sorted(ids))
    audit.slurm = lambda ids: cached
    for run in runs:
        try:
            data = audit.assemble(run.name)
            text = audit.render(data, "", not a.summary)
            (run / "audit.json").write_text(json.dumps(data, indent=2, default=str))
            (run / "audit.txt").write_text(re.sub(r"\033\[[0-9;]*m", "", text))
            print(text, flush=True)
        except (OSError, ValueError, KeyError) as exc:
            print(f"{run.name}: AUDIT ERROR {exc}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

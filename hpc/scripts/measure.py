#!/usr/bin/env python3
"""Derive qualification measurements from fetched manifests, raw records, Slurm accounting and transfer hashes."""

import argparse
import json
import tarfile
from datetime import datetime

from fleet import ROOT, atomic_json, config, remote


def records(run):
    rows = []
    for archive in (run / "results").rglob("*.tar.gz"):
        if archive.name != "llm.tar.gz":
            continue
        with tarfile.open(archive) as tar:
            for member in tar:
                if member.isfile() and member.name.endswith(".jsonl"):
                    parsed = [
                        json.loads(line) for line in tar.extractfile(member).read().decode().splitlines()
                    ]
                    rows.extend(row for row in parsed if row.get("model") and row.get("model_digest"))
    return rows


def seconds_between(start, end):
    return max(0, (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())


def collect_accounting(site, run, cfg):
    jobs = [line.split("\t")[0] for line in (run / "jobs.tsv").read_text().splitlines()]
    result = remote(
        site,
        "TZ=UTC sacct -n -P -X -j "
        + ",".join(jobs)
        + " --format=JobID,State,Submit,Start,End,ElapsedRaw,AllocTRES%200",
        cfg,
    )
    (run / "accounting.tsv").write_text(result.stdout)


_CELL_FIELDS = {"model": "model", "policy": "executable_policy", "arm": "arm", "family": "family"}


def _cell_matches(label, record):
    """A matrix cell label "k=v,k=v" matches a record when every known key agrees."""
    pairs = dict(part.split("=", 1) for part in label.split(",") if "=" in part)
    return bool(pairs) and all(
        str(record.get(_CELL_FIELDS.get(k, k))) == v for k, v in pairs.items()
    )


def measure(root):
    rows = []
    for site in ("fir", "narval", "rorqual"):
        for run in sorted((root / site).glob("*smoke*")):
            if not (run / "audit.json").exists() or not (run / "accounting.tsv").exists():
                continue
            audit = json.loads((run / "audit.json").read_text())
            # All cells, including collect, must succeed. Pending/failed runs remain visible but ineligible.
            cells = audit.get("rows", [])
            completed = bool(cells) and all(c.get("state") == "OK" for c in cells)
            accounting = {}
            for line in (run / "accounting.tsv").read_text().splitlines():
                parts = line.split("|")
                if len(parts) >= 6:
                    accounting[parts[0]] = parts
            raw = records(run)
            transfer = (
                json.loads((run / "transfer.json").read_text()) if (run / "transfer.json").exists() else {}
            )
            resume = run / "results" / "raw" / "analysis" / "resume-check.json"
            resume_data = json.loads(resume.read_text()) if resume.exists() else {}
            for record in raw:
                cell = next(
                    (
                        c for c in cells
                        if c["stage"] == "llm" and _cell_matches(c["cell"], record)
                    ),
                    None,
                )
                job = accounting.get(cell["job"]) if cell else accounting.get(record["job_id"])
                if not job or "Unknown" in job[2:5]:
                    continue
                rows.append(
                    {
                        "cluster": site,
                        "run_id": run.name,
                        "model": record["model"],
                        "model_digest": record["model_digest"],
                        "repeat": record["repeat"],
                        "success": completed and record.get("status") == "ok",
                        "fully_gpu": record.get("fully_gpu") is True,
                        "recovery_ok": resume_data.get("ok") is True,
                        "transfer_ok": transfer.get("verified") is True,
                        "queue_seconds": seconds_between(job[2], job[3]),
                        "startup_seconds": max(0, float(job[5]) - record["seconds"]),
                        "job_elapsed_seconds": float(job[5]),
                        "generation_seconds": record["seconds"],
                        # ToolRepair stream records carry total tokens and seconds instead of a rate.
                        "tokens_per_second": record["tokens_per_second"]
                        if "tokens_per_second" in record
                        else record.get("tokens", 0) / max(record["seconds"], 1e-9),
                        "transfer_seconds": transfer.get("seconds", 0),
                        "source": "fetched Slurm accounting + raw generation + completed audit + resume check + transfer hashes",
                    }
                )
    return rows


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "--accounting", action="store_true", help="one scheduler query/site/run, completed runs only"
    )
    a = p.parse_args()
    cfg = config()
    root = ROOT / "hpc/fetched"
    if a.accounting:
        for site in ("fir", "narval", "rorqual"):
            for run in (root / site).glob("*smoke*"):
                if (run / "jobs.tsv").exists() and not (run / "accounting.tsv").exists():
                    collect_accounting(site, run, cfg)
    result = measure(root)
    atomic_json(root / "qualification.json", result)
    print(json.dumps({"measurements": len(result), "output": str(root / "qualification.json")}))

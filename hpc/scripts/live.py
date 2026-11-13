#!/usr/bin/env python3
"""Read the fetched fleet audit as often as desired; never query Slurm or SSH."""

import argparse
import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def age_seconds(value, now):
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(value)
        return max(0, int((now - stamp.replace(tzinfo=stamp.tzinfo or UTC)).total_seconds()))
    except ValueError:
        return None


def render(root=ROOT, now=None):
    now = now or datetime.now(UTC)
    fetched = root / "hpc/fetched"
    lines = ["# Alliance experiment monitor", "", "Local snapshot at " + now.isoformat() + ". No SSH/Slurm query is made.", ""]
    for profile in ["harness2", "core"]:
        state = read(fetched / f"{profile}-campaign.json")
        try:
            pid = int((fetched / f"{profile}-campaign.pid").read_text())
            running = b"hpc/scripts/campaign.py" in Path(f"/proc/{pid}/cmdline").read_bytes()
        except (OSError, ValueError):
            running = False
        monitor = "running" if running else "finished" if state.get("phase") == "complete" else "STOPPED/not started"
        lines.append(f"- {profile}: {state.get('phase', 'not started')}; monitor {monitor}; controller update {state.get('updated_utc', 'absent')}; error: {state.get('error', 'none recorded')}")
        for item in state.get("full_runs", []):
            lines.append(f"  - Full owner {item['cluster']}: `{item['run_id']}`; submission {item.get('state', 'unknown')}; models {', '.join(item.get('models', []))}")
    lines += ["", "| Site | Fetch state | Last successful fetch age | Run / audit | Audit age | Cells | Model records |", "|---|---|---|---|---|---|---|"]
    for site in ["fir", "narval", "rorqual"]:
        folder = fetched / site
        fetch = read(folder / "fetch-status.json")
        seconds = age_seconds(fetch.get("last_success_utc"), now)
        fresh = str(seconds) + "s" if seconds is not None else "unknown"
        if seconds is None or seconds > 300:
            fresh += " **STALE/UNKNOWN**"
        paths = sorted(p for p in folder.glob("*/audit.json") if p.parent.name.startswith(("ssevoh-h2-", "ssevoh-core-", "ssevoh-results-audit-", "ssevoh-humaneval-")))
        if not paths:
            lines.append(f"| {site} | {fetch.get('state', 'unavailable')} | {fresh} | no fetched audit | unknown | unknown | unknown |")
        for path in paths:
            audit = read(path)
            counts = dict(Counter(row.get("state", "UNKNOWN") for row in audit.get("rows", [])))
            audit_age = age_seconds(audit.get("time"), now)
            audit_label = str(audit_age) + "s" if audit_age is not None else "unknown"
            if audit_age is None or audit_age > 300:
                audit_label += " **STALE/UNKNOWN**"
            progress = [r["progress"] for r in audit.get("rows", []) if r.get("stage") == "llm" and r.get("progress")]
            record_count = f"{sum(p[0] for p in progress)}/{sum(p[1] for p in progress):g}" if progress else "unavailable"
            link = path.parent / "audit.txt"
            lines.append(f"| {site} | {fetch.get('state', 'unavailable')} | {fresh} | [{path.parent.name}]({link}) | {audit_label} | {counts} | {record_count} |")
        if fetch.get("error"):
            lines += ["", f"{site} fetch error (previous files retained): `{fetch['error']}`", ""]
    lines += ["", "Open each audit for stage/cell job IDs, nodes, queue reasons, current/failed steps and raw log paths. Snapshots and fetch timestamps are separate: a successful file transfer does not by itself prove a fresh scheduler audit. No task-result inference is made from progress counts."]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", type=int, default=0, metavar="SECONDS")
    parser.add_argument("--cycles", type=int, default=360)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.watch < 0 or args.cycles < 1:
        parser.error("watch must be nonnegative and cycles positive")
    for index in range(args.cycles if args.watch else 1):
        report = render()
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            temporary = args.output.with_suffix(".tmp")
            temporary.write_text(report)
            temporary.replace(args.output)
        else:
            print(("\033[2J\033[H" if args.watch else "") + report, end="", flush=True)
        if args.watch and index + 1 < args.cycles:
            time.sleep(args.watch)


if __name__ == "__main__":
    main()

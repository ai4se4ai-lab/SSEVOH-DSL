#!/usr/bin/env python3
"""Start, inspect, or stop the local finite monitor. Stop never cancels Slurm jobs."""

import argparse
import json
import signal
import subprocess
import sys
from pathlib import Path

from fleet import ROOT


def running(pid):
    try:
        command = Path(f"/proc/{pid}/cmdline").read_bytes()
        return b"hpc/scripts/campaign.py" in command
    except OSError:
        return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["start", "status", "stop"], default="status", nargs="?")
    p.add_argument("--profile", choices=["ssevoh", "harness2", "core", "pilot-v2", "toolrepair"], default="ssevoh")
    p.add_argument("--auto-full", action="store_true")
    p.add_argument("--cycles", type=int, default=180)
    p.add_argument("--interval", type=int, default=120)
    p.add_argument("--qualification-minutes", type=int, default=45)
    a = p.parse_args()
    directory = ROOT / "hpc/fetched"
    directory.mkdir(parents=True, exist_ok=True)
    prefix = {"harness2": "harness2-", "core": "core-", "pilot-v2": "harness2-pilot-v2-", "toolrepair": "toolrepair-v1-"}.get(a.profile, "")
    pidfile = directory / (prefix + "campaign.pid")
    pid = int(pidfile.read_text()) if pidfile.exists() else None
    alive = pid is not None and running(pid)
    if a.command == "start":
        gate_path = ROOT / "hpc/config/research-readiness.json"
        gate = json.loads(gate_path.read_text()) if gate_path.exists() else {}
        if gate.get("empirical_allowed") is not True or (
            a.profile == "ssevoh" and gate.get("legacy_controller_allowed", False) is not True
        ):
            raise SystemExit("Campaign restart is locked until the core DSL formal-readiness gate passes")
        if alive:
            print(f"Already running: {pid}")
            return
        state = directory / (prefix + "campaign.json")
        if state.exists() and json.loads(state.read_text())["phase"] in {"needs_attention", "complete"}:
            raise SystemExit("Inspect campaign.json and its log before restarting a terminal campaign state")
        command = [
            sys.executable,
            "-u",
            str(ROOT / "hpc/scripts/campaign.py"),
            "--profile",
            a.profile,
            "--qualification-minutes",
            str(a.qualification_minutes),
            "--cycles",
            str(a.cycles),
            "--interval",
            str(a.interval),
        ]
        if a.auto_full:
            command.append("--auto-full")
        with (directory / (prefix + "campaign-driver.log")).open("a") as log:
            child = subprocess.Popen(
                command,
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        pidfile.write_text(str(child.pid) + "\n")
        print(f"Started finite controller: {child.pid}")
    elif a.command == "stop":
        if alive:
            import os

            os.kill(pid, signal.SIGTERM)
            print("Monitor stopping; submitted Slurm jobs continue.")
        else:
            print("No active monitor.")
    else:
        print(
            json.dumps(
                {"pid": pid, "running": alive, "log": str(directory / (prefix + "campaign-driver.log"))},
                indent=2,
            )
        )
        state = directory / (prefix + "campaign.json")
        if state.exists():
            print(state.read_text())


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Reproduce the unchanged, pinned executable upstream; refuse dirty/unrelated checkouts."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    pin = json.loads((ROOT / "upstream-pin.json").read_text())
    dest = ROOT / "original/upstream"

    def git(*args):
        return subprocess.check_output(["git", "-C", str(dest), *args], text=True).strip()

    if not dest.exists():
        subprocess.run(["git", "clone", "--filter=blob:none", pin["repository"], str(dest)], check=True)
    if git("remote", "get-url", "origin") != pin["repository"] or git("status", "--porcelain"):
        raise SystemExit("Refusing to change a dirty or unrelated upstream checkout")
    subprocess.run(["git", "-C", str(dest), "checkout", "--detach", pin["commit"]], check=True)
    if git("rev-parse", "HEAD") != pin["commit"]:
        raise SystemExit("Upstream pin mismatch")
    print(pin["commit"])


if __name__ == "__main__":
    main()

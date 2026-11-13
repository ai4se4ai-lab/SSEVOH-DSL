#!/usr/bin/env python3
"""Reproduce the reviewed checkout without changing a dirty or unrelated directory."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args], text=True).strip()


def main():
    pin = json.loads((ROOT / "upstream-pin.json").read_text())
    dest = ROOT / "original/upstream"
    if not dest.exists():
        subprocess.run(["git", "clone", "--filter=blob:none", pin["repository"], str(dest)], check=True)
    if git(dest, "remote", "get-url", "origin") != pin["repository"]:
        raise SystemExit("Existing checkout has an unexpected origin; refusing to change it")
    if git(dest, "status", "--porcelain"):
        raise SystemExit("Existing checkout is dirty; refusing to change it")
    subprocess.run(["git", "-C", str(dest), "cat-file", "-e", pin["commit"] + "^{commit}"], check=True)
    subprocess.run(["git", "-C", str(dest), "checkout", "--detach", pin["commit"]], check=True)
    if git(dest, "rev-parse", "HEAD") != pin["commit"]:
        raise SystemExit("Pinned revision mismatch")
    print(json.dumps({"checkout": str(dest), "commit": pin["commit"], "status": "pinned"}))


if __name__ == "__main__":
    main()

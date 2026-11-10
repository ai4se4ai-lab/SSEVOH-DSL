#!/usr/bin/env python3
"""Build a deterministic pinned runtime archive for offline Alliance compute nodes."""

import gzip
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    up = ROOT / "original/upstream"
    pin = json.loads((ROOT / "upstream-pin.json").read_text())

    def git(*args):
        return subprocess.check_output(["git", "-C", str(up), *args], text=True).strip()

    if git("rev-parse", "HEAD") != pin["commit"] or git("status", "--porcelain"):
        raise SystemExit("Clean pinned upstream required")
    paths = [p for p in git("ls-files").splitlines() if not p.startswith("assets/")]
    manifest = {
        "repository": pin["repository"],
        "commit": pin["commit"],
        "files": {p: hashlib.sha256((up / p).read_bytes()).hexdigest() for p in paths},
    }
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as archive:
        for path in paths:
            body = (up / path).read_bytes()
            info = tarfile.TarInfo(path)
            info.size = len(body)
            info.mode = 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(body))
    target = ROOT / "upstream-runtime.tar.gz"
    with target.open("wb") as file:
        with gzip.GzipFile(fileobj=file, mode="wb", filename="", mtime=0) as gz:
            gz.write(raw.getvalue())
    manifest["archive_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    (ROOT / "upstream-runtime.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                "archive": str(target),
                "bytes": target.stat().st_size,
                "files": len(paths),
                "sha256": manifest["archive_sha256"],
            }
        )
    )


if __name__ == "__main__":
    main()

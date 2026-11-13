#!/usr/bin/env python3
"""Fetch an official, checksum-pinned TLC checker; never execute an unverified download."""

import hashlib
from pathlib import Path
from urllib.request import urlopen

URL = "https://github.com/tlaplus/tlaplus/releases/download/v1.7.4/tla2tools.jar"
SHA256 = "936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88"


def ensure_tlc(path):
    path = Path(path)
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != SHA256:
            raise ValueError("TLC checker checksum mismatch: " + str(path))
        return path.resolve()
    with urlopen(URL, timeout=90) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("Downloaded TLC checker checksum mismatch")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".download")
    temporary.write_bytes(data)
    temporary.replace(path)
    return path.resolve()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=".cache/tla2tools.jar")
    args = parser.parse_args()
    print(ensure_tlc(args.output))

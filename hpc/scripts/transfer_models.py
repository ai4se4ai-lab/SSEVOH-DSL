#!/usr/bin/env python3
"""Stream selected pinned Ollama blobs between sites through the controller; no inference on login nodes."""

import argparse
import json
import re
import shlex
import subprocess

from fleet import config, event, remote, ssh_args


def transfer(source, target, models, cfg):
    src = cfg["clusters"][source]["work"] + "/models"
    dst = cfg["clusters"][target]["work"] + "/models"
    files = []
    for model in models:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+", model):
            raise ValueError("invalid model identifier")
        name, tag = model.split(":")
        manifest = f"manifests/registry.ollama.ai/library/{name}/{tag}"
        result = remote(source, "cat " + shlex.quote(src + "/" + manifest), cfg)
        data = json.loads(result.stdout)
        files.append(manifest)
        for layer in [data["config"], *data["layers"]]:
            value = layer["digest"]
            if not re.fullmatch("sha256:[0-9a-f]{64}", value):
                raise ValueError("invalid blob digest")
            files.append("blobs/" + value.replace(":", "-"))
    files = sorted(set(files))
    # Uncompressed tar is a data transfer only. Both endpoints retain normal SSH host-key checks.
    command = shlex.join(["tar", "-C", src, "-cf", "-", *files])
    remote(target, "mkdir -p " + shlex.quote(dst), cfg)
    producer = subprocess.Popen(ssh_args(source, cfg) + [command], stdout=subprocess.PIPE)
    consumer = subprocess.Popen(
        ssh_args(target, cfg) + [shlex.join(["tar", "-C", dst, "--skip-old-files", "-xf", "-"])],
        stdin=producer.stdout,
        stderr=subprocess.PIPE,
    )
    producer.stdout.close()
    _, err = consumer.communicate()
    first = producer.wait()
    # --keep-old-files may return 2 for existing shared layers. Verify all files, never suppress other errors.
    check = remote(target, shlex.join(["test", "-f", dst + "/" + files[0]]), cfg, check=False)
    if first or check.returncode or consumer.returncode:
        raise RuntimeError(
            f"model transfer failed: source={first}, destination={consumer.returncode}: {err.decode()}"
        )
    event(
        "transfer-models",
        target,
        {"source": source, "models": models, "files": len(files), "stderr": err.decode()},
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", default="fir")
    p.add_argument("--target", required=True)
    p.add_argument("--models", nargs="+", required=True)
    a = p.parse_args()
    transfer(a.source, a.target, a.models, config())

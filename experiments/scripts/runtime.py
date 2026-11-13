"""Slurm-only Ollama cache preparation and frozen manifests; no installation on login nodes."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path


def api(endpoint, body=None, timeout=900):
    host = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        "http://" + host + "/api/" + endpoint, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def require_allocation():
    if not os.environ.get("SLURM_JOB_ID") or not os.environ.get("CUDA_VISIBLE_DEVICES"):
        raise SystemExit("This command requires a Slurm GPU allocation")


def load_on_gpu(model, expected_digest, num_ctx=4096):
    # Empty-prompt generate loads the model without evaluating a task prompt.
    api(
        "generate",
        {
            "model": model,
            "stream": False,
            "keep_alive": "5m",
            "options": {"num_ctx": num_ctx, "num_thread": int(os.environ.get("SLURM_CPUS_PER_TASK", "4"))},
        },
    )
    loaded = next((m for m in api("ps")["models"] if m.get("digest") == expected_digest), None)
    if not loaded or loaded.get("size_vram", 0) < loaded.get("size", 1):
        raise SystemExit(f"{model} did not load fully on GPU; no task prompt was evaluated")
    return loaded


def seed_cache():
    require_allocation()
    seed = Path(os.environ["SEED_MODEL_CACHE"])
    dest = Path(os.environ["OLLAMA_MODELS"])
    (dest / "blobs").mkdir(parents=True, exist_ok=True)
    # Metadata copies are independent; existing weight files are hard-linked, never overwritten.
    for manifest in seed.glob("manifests/registry.ollama.ai/library/*/*"):
        target = dest / manifest.relative_to(seed)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(manifest, target)
        meta = json.loads(manifest.read_text())
        for layer in [meta["config"], *meta["layers"]]:
            blob = layer["digest"].replace(":", "-")
            src, dst = seed / "blobs" / blob, dest / "blobs" / blob
            if not dst.exists():
                try:
                    os.link(src, dst)
                except OSError:
                    # Avoid silently copying many GB; use an explicit transfer operation instead.
                    raise SystemExit(
                        f"Cannot hard-link cached blob {src}; stage cache on the same filesystem"
                    )


def freeze(models, output):
    require_allocation()
    tags = {x["name"]: x for x in api("tags")["models"]}
    records = {}
    for model in models:
        if model not in tags:
            if os.environ.get("ALLOW_MODEL_DOWNLOAD") != "1":
                raise SystemExit(f"Missing {model}; stage it from Fir's download job before offline setup")
            api("pull", {"model": model, "stream": False}, timeout=2400)
            tags = {x["name"]: x for x in api("tags")["models"]}
        info = api("show", {"model": model})
        if not info.get("license"):
            raise SystemExit(f"No license metadata for {model}")
        load_on_gpu(model, tags[model]["digest"])
        warmup = api(
            "generate",
            {
                "model": model,
                "prompt": "Return the single word READY.",
                "stream": False,
                "keep_alive": "5m",
                "options": {
                    "num_predict": 32,
                    "num_ctx": 4096,
                    "temperature": 0,
                    "seed": 481,
                    "num_thread": int(os.environ.get("SLURM_CPUS_PER_TASK", "4")),
                },
            },
        )
        loaded = next((m for m in api("ps")["models"] if m.get("digest") == tags[model]["digest"]), None)
        if not loaded or loaded.get("size_vram", 0) < loaded.get("size", 1):
            raise SystemExit(f"{model} is not fully resident on the allocated GPU")
        model_name, model_tag = model.split(":", 1)
        manifest = (
            Path(os.environ["OLLAMA_MODELS"])
            / "manifests/registry.ollama.ai/library"
            / model_name
            / model_tag
        )
        manifest_data = json.loads(manifest.read_text())
        verified_blobs = []
        for layer in [manifest_data["config"], *manifest_data["layers"]]:
            blob = Path(os.environ["OLLAMA_MODELS"]) / "blobs" / layer["digest"].replace(":", "-")
            with blob.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if "sha256:" + actual != layer["digest"]:
                raise SystemExit(f"Corrupted model blob: {blob}")
            verified_blobs.append(layer["digest"])
        canonical_path = Path(__file__).resolve().parents[2] / "hpc/config/models.frozen.json"
        if canonical_path.exists():
            canonical = json.loads(canonical_path.read_text())
            if canonical["models"][model]["digest"] != tags[model]["digest"]:
                raise SystemExit(f"{model} differs from the frozen cross-site model identity")
        records[model] = {
            "preflight": {"fully_gpu": True, "response": warmup, "residency": loaded},
            "verified_blobs": verified_blobs,
            "digest": tags[model]["digest"],
            "details": info.get("details"),
            "license": info["license"],
            "parameters": info.get("parameters"),
            "model_info": info.get("model_info"),
            "template": info.get("template"),
        }
    binary = Path(os.environ["OLLAMA_BIN"])
    result = {
        "models": records,
        "version": api("version"),
        "binary_sha256": hashlib.file_digest(binary.open("rb"), "sha256").hexdigest(),
        "runtime_protocol": "node-local-v2-preload-gpu",
        "gpu": subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], text=True
        ),
        "cluster": os.environ["CLUSTER"],
        "job": os.environ["SLURM_JOB_ID"],
    }
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["seed", "freeze"])
    p.add_argument("--models", nargs="+")
    p.add_argument("--output")
    a = p.parse_args()
    if a.command == "seed":
        seed_cache()
    else:
        freeze(a.models, a.output)

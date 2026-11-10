#!/usr/bin/env python3
"""Warm pinned node-local CUDA backends before Ollama's short discovery watchdog.

Runs trusted llama-server device enumeration only, inside a Slurm GPU allocation.
It never loads model weights, evaluates prompts, downloads files, or substitutes
CPU inference. The subsequent model-residency guards remain mandatory.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path


def enumerate_backends(runtime, runner=subprocess.run):
    if not os.environ.get('SLURM_JOB_ID') or not os.environ.get('CUDA_VISIBLE_DEVICES'):
        raise RuntimeError('CUDA startup preparation requires a Slurm GPU allocation')
    base = runtime / 'lib/ollama'
    binary = base / 'llama-server'
    if not binary.is_file():
        raise ValueError('Pinned node-local llama-server is missing')
    reports = []
    for directory in sorted(base.glob('cuda_v*')):
        backends = sorted(directory.glob('libggml-cuda.so*'))
        if not backends:
            continue
        backend = backends[0]
        env = dict(os.environ)
        env['GGML_BACKEND_PATH'] = str(backend)
        env['LD_LIBRARY_PATH'] = os.pathsep.join([str(base), str(directory), env.get('LD_LIBRARY_PATH', '')])
        command = [str(binary), '--list-devices', '--offline', '--verbose']
        started = time.perf_counter()
        try:
            result = runner(command, env=env, text=True, capture_output=True, timeout=180)
            text = result.stdout + '\n' + result.stderr
            reports.append({'backend': str(backend), 'returncode': result.returncode,
                            'cuda_visible': result.returncode == 0 and bool(re.search(r'\bCUDA\d+\b', text)),
                            'stdout': result.stdout[-20000:], 'stderr': result.stderr[-20000:],
                            'seconds': time.perf_counter() - started,
                            'backend_sha256': hashlib.sha256(backend.read_bytes()).hexdigest()})
        except subprocess.TimeoutExpired as exc:
            reports.append({'backend': str(backend), 'cuda_visible': False, 'timed_out': True,
                            'seconds': time.perf_counter() - started, 'error': str(exc)})
    return {'schema': 'ssevoh-cuda-startup-v1', 'job_id': os.environ['SLURM_JOB_ID'],
            'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
            'backends': reports, 'passed': any(r['cuda_visible'] for r in reports),
            'model_loaded': False, 'task_prompt_evaluated': False,
            'reference': 'https://github.com/ollama/ollama/blob/v0.32.14/discover/llama_server.go'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = enumerate_backends(args.runtime_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    if not report['passed']:
        raise SystemExit('No CUDA backend enumerated successfully; CPU fallback is prohibited')


if __name__ == '__main__':
    main()

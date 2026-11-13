#!/usr/bin/env python3
"""External, fail-closed per-task EvalPlus supervisor for frozen coding outputs.

Does not contact models. Requires Slurm, pinned inputs, all-stream freeze receipt,
and a successful feasibility report from the current site. Never grades inline
inside an online Harness² method. Each task receives a new PID/network/mount
namespace and writable scratch; host project/home/credentials remain unmounted.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import platform
import resource
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASET_SHA = '272720b90ac375502c8ed23cd791c2a93dfb22a911641a494da74a426c09f101'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage_vendor(destination):
    vendor = ROOT / 'experiments/humaneval/vendor'
    manifest = json.loads((vendor / 'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        if sha(vendor / name) != expected:
            raise ValueError('Evaluator dependency identity mismatch: ' + name)
    with tarfile.open(vendor / 'evalplus-26d6d00.tar.gz') as source:
        source.extractall(destination, filter='data')
    deps = destination / 'deps'
    deps.mkdir()
    for name in manifest['files']:
        if name.endswith('.whl'):
            if 'x86_64' not in name:
                raise ValueError('This cluster release requires pinned x86_64 wheels')
            with zipfile.ZipFile(vendor / name) as source:
                for item in source.infolist():
                    parts = Path(item.filename).parts
                    if item.filename.startswith('/') or '..' in parts:
                        raise ValueError('Unsafe wheel member')
                source.extractall(deps)
    return manifest


def limits():
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    resource.setrlimit(resource.RLIMIT_FSIZE, (4 * 1024**2, 4 * 1024**2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def grade_one(problem, solution, vendor, directory):
    binary = shutil.which('bwrap')
    if not binary:
        raise RuntimeError('Qualified Bubblewrap executable is unavailable')
    inputs = directory / 'input'
    work = directory / 'work'
    inputs.mkdir()
    work.mkdir()
    (inputs / 'task.json').write_text(json.dumps({'problem': problem, 'solution': solution}))
    expected_input = sha(inputs / 'task.json')
    evaluator = ROOT / 'experiments/scripts/humaneval_eval_inside.py'
    args = [binary, '--unshare-all', '--die-with-parent', '--new-session', '--cap-drop', 'ALL', '--clearenv']
    for name in ('/usr', '/lib', '/lib64', '/bin', '/sbin', '/cvmfs'):
        if Path(name).exists():
            args += ['--ro-bind', name, name]
    args += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/dev/shm', '--tmpfs', '/tmp', '--dir', '/etc', '--dir', '/opt']
    for name in ('/etc/ld.so.cache', '/etc/localtime'):
        if Path(name).is_file():
            args += ['--ro-bind', name, name]
    args += ['--ro-bind', str(inputs), '/input', '--ro-bind', str(vendor), '/opt/vendor',
             '--ro-bind', str(evaluator), '/opt/evaluate.py', '--bind', str(work), '/work', '--chdir', '/work']
    for key, value in {'HOME': '/tmp', 'PATH': '/usr/bin:/bin', 'OPENBLAS_NUM_THREADS': '1',
                       'OMP_NUM_THREADS': '1', 'PYTHONDONTWRITEBYTECODE': '1'}.items():
        args += ['--setenv', key, value]
    args += [str(Path(sys.executable).resolve()), '-I', '/opt/evaluate.py', '--input', '/input/task.json',
             '--output', '/work/verdict.json', '--vendor-root', '/opt/vendor']
    started = time.perf_counter()
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True, preexec_fn=limits)
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=150)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(proc.pid, signal.SIGKILL)
        stdout, stderr = proc.communicate()
    verdict_path = work / 'verdict.json'
    result = {'task_id': problem['task_id'], 'seconds': time.perf_counter() - started,
              'returncode': proc.returncode, 'timed_out': timed_out,
              'stdout': stdout[-10000:], 'stderr': stderr[-10000:],
              'status': 'evaluator_error', 'passed': False}
    if proc.returncode == 0 and verdict_path.is_file() and sha(inputs / 'task.json') == expected_input:
        verdict = json.loads(verdict_path.read_text())
        if verdict.get('task_id') != problem['task_id'] or type(verdict.get('passed')) is not bool:
            raise ValueError('Malformed evaluator verdict')
        result.update(status='graded', **verdict)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--isolation-report', type=Path, required=True)
    parser.add_argument('--controls', action='store_true')
    parser.add_argument('--samples', type=Path)
    parser.add_argument('--freeze', type=Path)
    parser.add_argument('--controls-report', type=Path)
    parser.add_argument('--model')
    parser.add_argument('--seed', type=int)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise SystemExit('External evaluation requires a Slurm allocation')
    if platform.machine() != 'x86_64' or sys.version_info[:2] != (3, 12):
        raise SystemExit('Pinned evaluator wheels require x86_64 CPython 3.12')
    from humaneval_sandbox import probe
    fresh = probe()
    if fresh.get('feasible') is not True:
        raise SystemExit('Current evaluator allocation failed fresh isolation controls')
    isolation = json.loads(args.isolation_report.read_text())
    if isolation.get('feasible') is not True or isolation.get('generated_code_executed') is not False:
        raise SystemExit('Isolation feasibility gate did not pass')
    if sha(args.dataset) != DATASET_SHA:
        raise SystemExit('Full private dataset hash mismatch')
    raw = args.dataset.read_bytes()
    problems = {r['task_id']: r for r in (json.loads(line) for line in gzip.decompress(raw).decode().splitlines())}
    if len(problems) != 164:
        raise SystemExit('Full dataset completeness check failed')
    if args.controls:
        rows = []
        for task in ('HumanEval/0', 'HumanEval/1', 'HumanEval/2'):
            p = problems[task]
            rows.append({'task_id': task, 'solution': p['prompt'] + p['canonical_solution'], 'control': 'positive'})
            rows.append({'task_id': task, 'solution': p['prompt'] + '\n    raise RuntimeError("deliberately incorrect control")\n', 'control': 'negative'})
    else:
        if not args.samples or not args.freeze or not args.controls_report:
            parser.error('Samples, evaluator controls, and global freeze receipt are required for generated-code grading')
        controls = [json.loads(line) for line in args.controls_report.read_text().splitlines()]
        expected_controls = {(f'HumanEval/{i}', kind) for i in range(3) for kind in ('positive', 'negative')}
        context = {'evaluator_sha256': sha(ROOT / 'experiments/scripts/humaneval_eval_inside.py'),
                   'supervisor_sha256': sha(Path(__file__)),
                   'vendor_manifest_sha256': sha(ROOT / 'experiments/humaneval/vendor/manifest.json'),
                   'private_dataset_sha256': DATASET_SHA}
        if (len(controls) != 6 or {(r.get('task_id'), r.get('control')) for r in controls} != expected_controls
                or not all(r.get('control_ok') is True and all(r.get(k) == v for k, v in context.items()) for r in controls)):
            raise SystemExit('Complete successful positive/negative controls are required')
        freeze = json.loads(args.freeze.read_text())
        if freeze.get('all_streams_frozen') is not True or freeze.get('samples_sha256') != sha(args.samples):
            raise SystemExit('All-stream freeze identity mismatch')
        rows = [json.loads(line) for line in args.samples.read_text().splitlines() if line.strip()]
        if args.model is not None:
            rows = [r for r in rows if r.get('model') == args.model]
        if args.seed is not None:
            rows = [r for r in rows if r.get('seed') == args.seed]
        if not rows:
            raise SystemExit('Requested grading stream is absent from the global frozen population')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # A fresh output prevents ambiguous repeated control populations.
    with args.output.open('x') as output, tempfile.TemporaryDirectory(prefix='ssevoh-evalplus-', dir=os.environ.get('SLURM_TMPDIR')) as folder:
        root = Path(folder)
        vendor = root / 'vendor'
        vendor.mkdir()
        stage_vendor(vendor)
        for index, row in enumerate(rows):
            task = row['task_id']
            if task not in problems:
                raise ValueError('Unknown frozen task identifier')
            if row.get('solution') is None:
                result = {'task_id': task, 'status': 'missing_solution', 'passed': False}
            else:
                directory = root / f'task-{index}'
                directory.mkdir()
                result = grade_one(problems[task], row['solution'], vendor, directory)
            for field in ('condition', 'model', 'seed', 'control', 'selection_sha256'):
                if field in row:
                    result[field] = row[field]
            result.update(evaluator_sha256=sha(ROOT / 'experiments/scripts/humaneval_eval_inside.py'),
                          supervisor_sha256=sha(Path(__file__)),
                          vendor_manifest_sha256=sha(ROOT / 'experiments/humaneval/vendor/manifest.json'),
                          private_dataset_sha256=DATASET_SHA)
            if args.controls:
                result['control_ok'] = result['status'] == 'graded' and result['passed'] == (row['control'] == 'positive')
            output.write(json.dumps(result, sort_keys=True) + '\n')
            output.flush()
            print(json.dumps({'task_id': task, 'status': result['status'], 'passed': result['passed'], 'control': row.get('control')}), flush=True)
    if args.controls:
        reports = [json.loads(line) for line in args.output.read_text().splitlines()]
        if not all(r['control_ok'] for r in reports):
            raise SystemExit('Evaluator controls failed; generated-code grading stays blocked')


if __name__ == '__main__':
    main()

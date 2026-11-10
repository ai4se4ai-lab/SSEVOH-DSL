#!/usr/bin/env python3
"""Fail-closed Bubblewrap feasibility check. Runs trusted probes only, in Slurm.

This report is a prerequisite, not certification of arbitrary-code containment.
No model output or benchmark reference is executed by this program.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

PROBE = r'''
import json, os, pathlib, socket
sentinel = pathlib.Path(os.environ['HOST_SENTINEL'])
checks = {'host_file_hidden': not sentinel.exists(), 'pid_namespace': os.getpid() < 100}
try:
    pathlib.Path('/usr/ssevoh-write-probe').write_text('unexpected')
    checks['host_mount_readonly'] = False
except OSError:
    checks['host_mount_readonly'] = True
try:
    s = socket.create_connection(('1.1.1.1', 443), timeout=1)
    s.close()
    checks['network_blocked'] = False
except OSError:
    checks['network_blocked'] = True
checks['credentials_absent'] = not any(k in os.environ for k in ('SSH_AUTH_SOCK', 'AWS_SECRET_ACCESS_KEY', 'HF_TOKEN', 'OLLAMA_HOST'))
checks['private_work_writable'] = pathlib.Path('/work').is_dir()
pathlib.Path('/work/output.txt').write_text('trusted control')
print(json.dumps(checks, sort_keys=True))
'''


def limits():
    resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def command(work: Path, sentinel: Path):
    binary = shutil.which('bwrap')
    if not binary:
        raise RuntimeError('Bubblewrap is unavailable')
    args = [binary, '--unshare-all', '--die-with-parent', '--new-session', '--cap-drop', 'ALL', '--clearenv']
    for name in ('/usr', '/lib', '/lib64', '/bin', '/sbin', '/cvmfs'):
        if Path(name).exists():
            args += ['--ro-bind', name, name]
    args += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--dir', '/etc']
    for name in ('/etc/ld.so.cache', '/etc/localtime'):
        if Path(name).is_file():
            args += ['--ro-bind', name, name]
    args += ['--bind', str(work), '/work', '--chdir', '/work', '--setenv', 'HOST_SENTINEL', str(sentinel),
             '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'HOME', '/tmp',
             str(Path(sys.executable).resolve()), '-I', '-c', PROBE]
    return args


def probe():
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Run feasibility checks in a Slurm compute allocation, never on a login node')
    with tempfile.TemporaryDirectory(prefix='ssevoh-isolation-', dir=os.environ.get('SLURM_TMPDIR')) as folder:
        root = Path(folder)
        work = root / 'work'
        work.mkdir()
        sentinel = root / 'host-only.txt'
        sentinel.write_text('must not be visible inside sandbox')
        args = command(work, sentinel)
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True, preexec_fn=limits)
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
        checks = {}
        if process.returncode == 0:
            try:
                checks = json.loads(stdout)
            except ValueError:
                pass
        checks['output_collected'] = (work / 'output.txt').is_file()
        return {'schema': 'ssevoh-humaneval-isolation-preflight-v1',
                'utc': datetime.now(UTC).isoformat(), 'host': platform.node(),
                'job_id': os.environ['SLURM_JOB_ID'], 'python': sys.version,
                'bwrap': args[0], 'command': args, 'returncode': process.returncode,
                'timed_out': timed_out, 'stdout': stdout, 'stderr': stderr,
                'checks': checks,
                'feasible': process.returncode == 0 and len(checks) == 7 and all(checks.values()),
                'generated_code_executed': False,
                'probe_sha256': hashlib.sha256(PROBE.encode()).hexdigest(),
                'limitation': 'Trusted feasibility controls only; descendant/resource/escape controls and evaluator integration still required.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = probe()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'job_id': report['job_id'], 'feasible': report['feasible'], 'stderr': report['stderr']}))
    # A negative feasibility finding is a successful diagnostic, never an authorization.


if __name__ == '__main__':
    main()

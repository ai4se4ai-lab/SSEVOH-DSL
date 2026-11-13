#!/usr/bin/env python3
"""Submit trusted isolation diagnostics through the existing frozen Slurm graph.

This does not authorize generated-code execution or claim benchmark readiness.
Submission intent is persisted first; existing ledgers require inspection, never
blind resubmission. Run from the local workstation, not a compute allocation.
"""
import argparse
import hashlib
import json
import shlex
import subprocess
from datetime import UTC, datetime

from fleet import ROOT, SITES, atomic_json, config, deploy, ssh_args, submit
from harness2_campaign import source_current


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', choices=SITES, required=True)
    parser.add_argument('--trial', type=int, choices=(1, 2, 3), default=1)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--controls', action='store_true', help='Add isolated trusted evaluator controls')
    modes.add_argument('--coding-smoke', action='store_true', help='Complete pinned two-task/model coding graph')
    parser.add_argument('--private-dataset', type=__import__('pathlib').Path,
                        default=__import__('pathlib').Path('/tmp/ssevoh-HumanEvalPlus-v0.1.10.jsonl.gz'))
    parser.add_argument("--cohort", choices=("v1", "v2", "v3", "v4", "v5"), default="v5")
    args = parser.parse_args()
    kind = 'smoke' if args.coding_smoke else 'controls' if args.controls else 'preflight'
    state_path = ROOT / f'hpc/fetched/humaneval-{kind}-{args.cohort}-{args.site}-{args.trial}.json'
    if state_path.exists():
        raise SystemExit('Submission intent already exists; inspect remote jobs.tsv and state before retrying')
    source_current()
    graph_path = ROOT / f'hpc/config/profiles/humaneval-{kind}.json'
    graph = json.loads(graph_path.read_text())
    if not args.coding_smoke and any(not stage.get('cpu_only') for stage in graph['stages']):
        raise SystemExit('This release is for CPU-only trusted controls, not inference')
    state = {'schema': 'ssevoh-humaneval-preflight-submission-v1', 'site': args.site, 'trial': args.trial,
             'phase': 'requested', 'created_utc': datetime.now(UTC).isoformat(),
             'run_id': f'ssevoh-humaneval-{kind}-{args.cohort}-t{args.trial}-' + datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ') + '-' + args.site,
             'graph_sha256': hashlib.sha256(graph_path.read_bytes()).hexdigest(),
             'generated_code_authorized': False}
    atomic_json(state_path, state)
    cfg = config()
    for stage in graph['stages']:
        if not stage.get('cpu_only'):
            stage['resources']['gpus'] = cfg['clusters'][args.site]['gpus']
    try:
        deploy(args.site, cfg)
        if args.controls or args.coding_smoke:
            expected = '272720b90ac375502c8ed23cd791c2a93dfb22a911641a494da74a426c09f101'
            if hashlib.sha256(args.private_dataset.read_bytes()).hexdigest() != expected:
                raise ValueError('Private dataset identity mismatch')
            destination = cfg['clusters'][args.site]['work'] + '/benchmarks/private'
            from fleet import remote
            remote(args.site, shlex.join(['mkdir', '-p', '-m', '700', destination]), cfg)
            remote(args.site, shlex.join(['chmod', '700', destination]), cfg)
            subprocess.run(['rsync', '-az', '--chmod=F600', '-e', shlex.join(ssh_args(args.site, cfg)[:-1]),
                            str(args.private_dataset), f"{cfg['username']}@{cfg['clusters'][args.site]['host']}:{destination}/HumanEvalPlus-v0.1.10.jsonl.gz"],
                           check=True, timeout=120)
        code = """import json,pathlib,shutil,sys
root=pathlib.Path(sys.argv[1]);run=sys.argv[2];graph=json.load(sys.stdin)
sys.path.insert(0,str(root/'hpc/scripts'));import hpclib
folder=root/'hpc/logs'/run/'config';folder.mkdir(parents=True)
(folder/'experiments.resolved.json').write_text(json.dumps(hpclib.resolve(graph,False),indent=2))
for name in ['cluster.env','requirements.txt','source-provenance.json']:
 if (root/'hpc/config'/name).exists():shutil.copy2(root/'hpc/config'/name,folder/name)
"""
        subprocess.run(ssh_args(args.site, cfg) + [shlex.join(['python3', '-c', code, cfg['clusters'][args.site]['remote_dir'], state['run_id']])],
                       input=json.dumps(graph), text=True, check=True, timeout=90)
        submit(args.site, cfg, False, state['run_id'])
        state['phase'] = 'submitted'
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        state.update(phase='needs_attention', error=str(exc))
        raise
    finally:
        atomic_json(state_path, state)
    print(json.dumps(state, indent=2))


if __name__ == '__main__':
    main()

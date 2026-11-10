#!/usr/bin/env python3
"""Finite coding-study coordination using existing native Slurm/fleet machinery.

No alternative scheduler: this only qualifies completed native graphs, assigns
whole streams, submits existing profiles, and gates external grading on the
complete globally frozen generation population. Every intent is persisted before
submission; uncertain acknowledgments are never blindly retried.
"""
import argparse
import concurrent.futures
import fcntl
import hashlib
import json
import shlex
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from fleet import ROOT, SITES, atomic_json, config, deploy, fetch, remote, ssh_args, status, submit
from harness2_campaign import source_current
from measure import collect_accounting
from verify_transfer import verify

STATE = ROOT / 'hpc/fetched/humaneval-campaign.json'
PROTOCOL = ROOT / 'experiments/humaneval/protocol.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(value):
    value['updated_utc'] = datetime.now(UTC).isoformat()
    atomic_json(STATE, value)


def run_root(intent):
    return ROOT / 'hpc/fetched' / intent['site'] / intent['run_id']


def complete(intent):
    root = run_root(intent)
    path = root / 'audit.json'
    if not path.exists():
        return False
    rows = json.loads(path.read_text()).get('rows', [])
    return bool(rows) and all(r['state'] == 'OK' for r in rows)


def refresh_site(site, cfg, intents):
    status(site, cfg, prefix='ssevoh-humaneval', strict=True)
    for intent in intents:
        if intent['site'] != site:
            continue
        root = run_root(intent)
        transfer = root / 'transfer.json'
        if (root / 'diagnostic-collected.json').exists():
            continue
        if transfer.exists() and json.loads(transfer.read_text()).get('verified') is True and complete(intent):
            if not (root / 'accounting.tsv').exists():
                collect_accounting(site, root, cfg)
            continue
        fetch(site, cfg, intent['run_id'], include_source=False)
        audit_path = root / 'audit.json'
        if audit_path.exists() and intent.get('kind') not in ('full-generation', 'full-evaluation'):
            rows = json.loads(audit_path.read_text()).get('rows', [])
            final_states = ('COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL')
            if rows and all(r.get('slurm_state') in final_states for r in rows) and not all(r['state']=='OK' for r in rows):
                atomic_json(root / 'diagnostic-collected.json', {'states': rows, 'scope': 'Final failed diagnostic logs retained; not a valid benchmark result'})
        if complete(intent) and (root / 'results/run_manifest.json').exists():
            verify(site, intent['run_id'], cfg)
            if not (root / 'accounting.tsv').exists():
                collect_accounting(site, root, cfg)


def smoke_intents():
    cohort = json.loads(PROTOCOL.read_text())['qualification_cohort']
    return [json.loads(p.read_text()) for p in sorted((ROOT / 'hpc/fetched').glob(f'humaneval-smoke-{cohort}-*.json'))]


def qualify(intent, protocol):
    if not complete(intent):
        audit_path = run_root(intent) / 'audit.json'
        if audit_path.exists():
            rows = json.loads(audit_path.read_text()).get('rows', [])
            failed = [(r['stage'], r['state']) for r in rows if r['state'] in ('FAIL', 'FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY')]
            if failed:
                return {'site': intent['site'], 'trial': intent['trial'], 'run_id': intent['run_id'],
                        'eligible': False, 'reason': 'Native smoke failure', 'failed_stages': failed}
        return None
    root = run_root(intent)
    transfer = json.loads((root / 'transfer.json').read_text()) if (root / 'transfer.json').exists() else {}
    if transfer.get('verified') is not True:
        return None
    release = fingerprint()
    snapshot = json.loads((root / 'config/source-snapshot.json').read_text())['files']
    expected = {**release['verified_sources'], 'integrations/harness2/evidence/readiness.json': release['readiness_sha256'],
                'hpc/scripts/fleet.py': release['fleet_sha256'],
                'hpc/scripts/submit_humaneval_preflight.py': release['submitter_sha256']}
    if any(snapshot.get(name) != value for name, value in expected.items()):
        raise ValueError('Completed smoke did not test the current frozen release')
    summary = json.loads((root / 'results/raw/analysis/summary.json').read_text())
    if summary['sample_rows'] != 16 or summary['grade_rows'] != 16:
        raise ValueError('Smoke outcome population mismatch')
    freezes = list((root / 'results/raw/llm').glob('*.freeze.json'))
    if len(freezes) != 2:
        raise ValueError('Both model streams are required')
    for path in freezes:
        row = json.loads(path.read_text())
        expected_digest = json.loads((ROOT / 'hpc/config/models.frozen.json').read_text())['models'][row['model']]['digest']
        if row.get('model_digest') != expected_digest:
            raise ValueError('Smoke model differs from frozen study identity')
        if row['protocol_sha256'] != sha(PROTOCOL) or not row['fully_gpu'] or row['failed_calls']:
            raise ValueError('Smoke source/GPU/client qualification failed')
    calibration = list((root / 'results/raw/development').glob('*.json'))
    if len(calibration) != 2 or not all(json.loads(p.read_text()).get('passed') is True for p in calibration):
        raise ValueError('Disjoint edit calibration did not pass for both models')
    controls = [json.loads(line) for line in (root / 'results/raw/controls/records.jsonl').read_text().splitlines()]
    if len(controls) != 6 or not all(r['control_ok'] for r in controls):
        raise ValueError('Evaluator controls failed')
    for model in protocol['models']:
        reference = next(r for r in summary['summaries'] if r['model'] == model and r['condition'] == 'frozen-one-shot')
        if reference['passed'] == 0:
            raise ValueError('No useful smoke reference; do not scale this protocol')
    rows = [line.split('|') for line in (root / 'accounting.tsv').read_text().splitlines()]
    rows = [r for r in rows if len(r) >= 6 and r[2] not in ('Unknown', '') and r[4] not in ('Unknown', '')]
    ended = max(datetime.fromisoformat(r[4]).replace(tzinfo=UTC) for r in rows)
    created = datetime.fromisoformat(intent['created_utc'])
    completion = (ended - created).total_seconds()
    if completion > protocol['qualification']['deadline_minutes'] * 60:
        return {'site': intent['site'], 'trial': intent['trial'], 'eligible': False,
                'reason': 'completed after prespecified qualification deadline', 'completion_seconds': completion}
    audit = json.loads((root / 'audit.json').read_text())
    gpu_cost = {}
    for row in audit['rows']:
        if row['stage'] == 'llm':
            model = row['cell'].split('model=', 1)[1].split(',', 1)[0]
            gpu_cost[model] = row['elapsed']
    return {'site': intent['site'], 'trial': intent['trial'], 'run_id': intent['run_id'], 'eligible': True,
            'completion_seconds': completion, 'transfer_seconds': transfer.get('seconds', 0),
            'score_seconds': completion + transfer.get('seconds', 0), 'gpu_job_seconds': gpu_cost,
            'protocol_sha256': sha(PROTOCOL), 'readiness_sha256': release['readiness_sha256'],
            'source_snapshot_sha256': sha(root / 'config/source-snapshot.json'),
            'score_note': 'Native completion plus final verified fetch/RPC cost; prior failed fetches remain in operation logs and are not cumulative in this score.'}


def install_graph(site, cfg, run, graph, cells=None):
    code = """import json,pathlib,shutil,sys
root=pathlib.Path(sys.argv[1]);run=sys.argv[2];value=json.load(sys.stdin)
sys.path.insert(0,str(root/'hpc/scripts'));import hpclib
resolved=hpclib.resolve(value['graph'],False)
if value.get('cells') is not None:
 next(s for s in resolved['stages'] if s['name']=='llm')['cells']=value['cells']
errors=hpclib.validate(resolved)
if errors:raise ValueError(errors)
folder=root/'hpc/logs'/run/'config';folder.mkdir(parents=True)
(folder/'experiments.resolved.json').write_text(json.dumps(resolved,indent=2))
for name in ['cluster.env','requirements.txt','source-provenance.json']:
 if (root/'hpc/config'/name).exists():shutil.copy2(root/'hpc/config'/name,folder/name)
"""
    subprocess.run(ssh_args(site, cfg) + [shlex.join(['python3', '-c', code, cfg['clusters'][site]['remote_dir'], run])],
                   input=json.dumps({'graph': graph, 'cells': cells}), text=True, check=True, timeout=90)


def make_intent(site, kind, cells=None):
    run = f'ssevoh-humaneval-{kind}-' + datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ') + '-' + site
    return {'site': site, 'run_id': run, 'kind': kind, 'phase': 'reserved', 'cells': cells,
            'created_utc': datetime.now(UTC).isoformat()}


def submit_intent(state, cfg, intent, graph):
    source_current()
    site, run = intent['site'], intent['run_id']
    if intent['phase'] != 'reserved':
        raise ValueError('Submission already attempted; inspect its remote ledger')
    intent['phase'] = 'preparing'
    save(state)
    try:
        deploy(site, cfg)
        for stage in graph['stages']:
            if not stage.get('cpu_only'):
                stage['resources']['gpus'] = cfg['clusters'][site]['gpus']
        install_graph(site, cfg, run, graph, intent.get('cells'))
        intent['phase'] = 'submitting'
        save(state)
        submit(site, cfg, False, run)
        intent['phase'] = 'submitted'
    except Exception as exc:
        intent.update(phase='inspect_remote_ledger', error=str(exc))
        state['phase'] = 'needs_attention'
        raise
    finally:
        save(state)


def fingerprint():
    report_path = ROOT / 'integrations/harness2/evidence/readiness.json'
    report = json.loads(report_path.read_text())
    return {'protocol_sha256': sha(PROTOCOL), 'readiness_sha256': sha(report_path),
            'verified_sources': report['source_sha256'],
            'actual_sources': {name: sha(ROOT / name) for name in report['source_sha256']},
            'coordinator_sha256': sha(Path(__file__)),
            'fleet_sha256': sha(ROOT / 'hpc/scripts/fleet.py'),
            'submitter_sha256': sha(ROOT / 'hpc/scripts/submit_humaneval_preflight.py')}


def build_plan(observations, protocol):
    import statistics
    qualified = []
    for site in SITES:
        rows = [r for r in observations if r['site'] == site and r.get('eligible')]
        if len(rows) == 3 and {r['trial'] for r in rows} == {1, 2, 3}:
            qualified.append({'site': site, 'median_completion_cost': statistics.median(r['score_seconds'] for r in rows),
                              'model_job_seconds': {model: statistics.median(r['gpu_job_seconds'][model] for r in rows)
                                                    for model in protocol['models']}})
    qualified.sort(key=lambda r: (r['median_completion_cost'], r['site']))
    if len(qualified) < 2:
        return None
    owners = qualified[:2]
    # Greedy two-GPU-slot packing; whole streams remain unique and libraries local.
    slots = {r['site']: [0.0, 0.0] for r in owners}
    cells = [(model, seed) for model in protocol['models'] for seed in protocol['seeds']]
    cells.sort(key=lambda pair: -sum(r['model_job_seconds'][pair[0]] for r in owners))
    allocation = []
    for model, seed in cells:
        choices = []
        for owner in owners:
            site = owner['site']
            predicted = owner['model_job_seconds'][model] * (164 / 2) * 2
            if predicted > 16 * 3600:
                continue
            slot = min(range(2), key=lambda i: slots[site][i])
            choices.append((slots[site][slot] + predicted, site, slot, predicted))
        if not choices:
            raise ValueError('No qualified site fits the16-hour allocation for this stream')
        _, site, slot, predicted = min(choices)
        slots[site][slot] += predicted
        allocation.append({'site': site, 'model': model, 'seed': seed,
                           'predicted_seconds': predicted, 'prediction_note': 'Smoke extrapolation with2x context allowance, not measured full cost'})
    if any(r['predicted_seconds'] > 16 * 3600 for r in allocation):
        raise ValueError('Smoke extrapolation exceeds the16-hour allocation; inspect sizing before submission')
    if len({r['site'] for r in allocation}) != 2:
        raise ValueError('Distributed ownership requires two sites')
    return {'qualified': qualified, 'primary': owners[0]['site'], 'ownership': allocation,
            'protocol_sha256': sha(PROTOCOL), 'qualification': observations}


def tick(state, cfg, auto_full):
    if state.get('release') != fingerprint():
        raise ValueError('Campaign protocol/source drift; inspect before any further work')
    if state['phase'] in ('full_submission', 'evaluation_submission'):
        raise ValueError('Interrupted submission transition; inspect every reserved remote ledger')
    protocol = json.loads(PROTOCOL.read_text())
    intents = []
    for path in sorted((ROOT / 'hpc/fetched').glob('humaneval-*.json')):
        item = json.loads(path.read_text())
        if item.get('site') in SITES and item.get('run_id'):
            intents.append(item)
    intents.extend(state.get('full_runs', []))
    intents = list({(r['site'],r['run_id']):r for r in intents}.values())
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(refresh_site, site, cfg, intents): site for site in SITES}
        for future in concurrent.futures.as_completed(futures):
            site = futures[future]
            try:
                future.result()
                state.setdefault('site_errors', {}).pop(site, None)
            except Exception as exc:
                state.setdefault('site_errors', {})[site] = str(exc)
    for intent in intents:
        audit_path = run_root(intent) / 'audit.json'
        if audit_path.exists():
            rows = json.loads(audit_path.read_text()).get('rows', [])
            failed = [r for r in rows if r['state'] in ('FAIL', 'FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY')]
            if failed and intent.get('kind') in ('full-generation', 'full-evaluation'):
                raise RuntimeError('Native graph failure requires inspection: ' + intent['run_id'] + ' ' + str([(r['stage'], r['state']) for r in failed]))
    if state['phase'] == 'qualification':
        observations = []
        for intent in smoke_intents():
            row = qualify(intent, protocol)
            if row:
                observations.append(row)
        state['qualification'] = observations
        # Each site's first complete trial gates its next two independent submissions.
        for site in SITES:
            if any(r['site'] == site and r['trial'] == 1 and r.get('eligible') for r in observations):
                for trial in (2, 3):
                    path = ROOT / f"hpc/fetched/humaneval-smoke-{protocol['qualification_cohort']}-{site}-{trial}.json"
                    if not path.exists():
                        subprocess.run([sys.executable, str(ROOT / 'hpc/scripts/submit_humaneval_preflight.py'),
                                        '--site', site, '--coding-smoke', '--cohort', protocol['qualification_cohort'], '--trial', str(trial)],
                                       check=True, timeout=600)
        plan = build_plan(observations, protocol)
        if plan and auto_full:
            source_current()
            state['plan'] = plan
            gate_path = ROOT / 'hpc/config/research-readiness.json'
            gate = json.loads(gate_path.read_text())
            if 'humaneval-coding-full-v1' not in gate['allowed_studies']:
                gate['allowed_studies'].append('humaneval-coding-full-v1')
            gate['humaneval_full_allowed'] = True
            gate['humaneval_full_qualification'] = str(STATE.relative_to(ROOT))
            atomic_json(gate_path, gate)
            state['phase'] = 'full_submission'
            graph = json.loads((ROOT / 'hpc/config/profiles/humaneval-full.json').read_text())
            for site in sorted({r['site'] for r in plan['ownership']}):
                cells = [{k: r[k] for k in ('model', 'seed')} for r in plan['ownership'] if r['site'] == site]
                state.setdefault('full_runs', []).append(make_intent(site, 'full-generation', cells))
            if len([r for r in state['full_runs'] if r['kind'] == 'full-generation']) != 2:
                raise ValueError('Expected exactly two reserved generation owners')
            save(state)
            for intent in state['full_runs']:
                if intent['kind'] == 'full-generation':
                    submit_intent(state, cfg, intent, json.loads(json.dumps(graph)))
            state['phase'] = 'full_generation'
    elif state['phase'] == 'full_generation':
        runs = [r for r in state['full_runs'] if r['kind'] == 'full-generation']
        if len(runs) != 2:
            raise ValueError('Generation owner cardinality does not match reserved plan')
        if all(complete(r) and (run_root(r) / 'transfer.json').exists()
                                  and json.loads((run_root(r) / 'transfer.json').read_text())['verified'] for r in runs):
            target = ROOT / 'experiments/humaneval-aggregate-input'
            if target.exists():
                raise ValueError('Existing aggregate input requires identity inspection')
            target.mkdir()
            for intent in runs:
                folder = run_root(intent) / 'results/raw/llm'
                for path in folder.glob('selected-*.jsonl'):
                    if (target / path.name).exists():
                        raise ValueError('Duplicate whole-stream owner')
                    local = json.loads(path.with_suffix('.freeze.json').read_text())
                    if (local['model'], local['seed']) not in {(c['model'], c['seed']) for c in intent['cells']}:
                        raise ValueError('Generation stream receipt does not match its unique owner')
                    shutil.copy2(path, target / path.name)
                    shutil.copy2(path.with_suffix('.freeze.json'), target / path.with_suffix('.freeze.json').name)
            from importlib import import_module
            sys.path.insert(0, str(ROOT / 'experiments/scripts'))
            freeze = import_module('humaneval_freeze').freeze
            # Validate global coverage locally before any external grading submission.
            freeze(target, protocol['models'], protocol['seeds'], [f'HumanEval/{i}' for i in range(164)],
                   target / 'global-samples.jsonl', target / 'global-receipt.json', sha(PROTOCOL))
            provenance = {'generation_owners': runs, 'qualification_plan': state['plan'], 'release': state['release'],
                          'transfers': {r['run_id']: json.loads((run_root(r)/'transfer.json').read_text()) for r in runs}}
            atomic_json(target / 'generation-provenance.json', provenance)
            graph = json.loads((ROOT / 'hpc/config/profiles/humaneval-evaluate.json').read_text())
            intent = make_intent(state['plan']['primary'], 'full-evaluation')
            state['full_runs'].append(intent)
            state['phase'] = 'evaluation_submission'
            save(state)
            submit_intent(state, cfg, intent, graph)
            state['phase'] = 'external_evaluation'
    elif state['phase'] == 'external_evaluation':
        runs = [r for r in state['full_runs'] if r['kind'] == 'full-evaluation']
        if len(runs) != 1:
            raise ValueError('Evaluation intent cardinality mismatch')
        if complete(runs[0]):
            root = run_root(runs[0]);transfer=root/'transfer.json'
            if transfer.exists() and json.loads(transfer.read_text())['verified']:
                summary = json.loads((root / 'results/raw/analysis/summary.json').read_text())
                if not summary['full_164_task_coverage'] or summary['sample_rows'] != 3936:
                    raise ValueError('Full evaluation population incomplete')
                destination = ROOT / 'artifacts/benchmark-results/humaneval-full' / runs[0]['run_id']
                if destination.exists():
                    raise ValueError('Existing immutable full artifact requires inspection')
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(root / 'results/raw', destination)
                shutil.copy2(transfer, destination / 'transfer.json')
                for owner in [r for r in state['full_runs'] if r['kind'] == 'full-generation']:
                    source = run_root(owner) / 'results/raw'
                    shutil.copytree(source, destination / 'generation' / owner['site'])
                provenance = ROOT / 'experiments/humaneval-aggregate-input/generation-provenance.json'
                shutil.copy2(provenance, destination / 'generation-provenance.json')
                atomic_json(destination / 'artifact-manifest.json', {
                    'schema': 'ssevoh-humaneval-full-artifact-v1', 'release': state['release'],
                    'files': {str(p.relative_to(destination)): sha(p) for p in destination.rglob('*') if p.is_file()}})
                state['phase'] = 'complete'
                state['summary'] = str((destination / 'analysis/summary.json').relative_to(ROOT))
    save(state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--auto-full', action='store_true')
    parser.add_argument('--cycles', type=int, default=1)
    parser.add_argument('--interval', type=int, default=120)
    args = parser.parse_args()
    if args.interval < 120 or not 1 <= args.cycles <= 1440:
        parser.error('Use at least120seconds and1..1440 finite cycles')
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with STATE.with_suffix('.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('A coding campaign coordinator already holds the exclusive lock')
        run_locked(args)


def run_locked(args):
    state = json.loads(STATE.read_text()) if STATE.exists() else {
        'schema': 'ssevoh-humaneval-campaign-v1', 'phase': 'qualification', 'created_utc': datetime.now(UTC).isoformat(), 'release': fingerprint()}
    if state['phase'] in ('complete', 'needs_attention'):
        raise SystemExit('Terminal state requires inspection before continuation')
    cfg = config()
    for cycle in range(args.cycles):
        try:
            tick(state, cfg, args.auto_full)
        except Exception as exc:
            state.update(phase='needs_attention', error=f'{type(exc).__name__}: {exc}')
            save(state)
            raise
        print(json.dumps({'phase': state['phase'], 'qualification_trials': len(state.get('qualification', [])),
                          'site_errors': state.get('site_errors', {})}), flush=True)
        if state['phase'] in ('complete', 'needs_attention'):
            break
        if cycle + 1 < args.cycles:
            time.sleep(args.interval)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Slurm-only public coding streams through the original Harness² scheduler.

No evaluator or private dataset is imported. All selected outputs are frozen
before external grading. A five-entry online library uses original retain/run_task
APIs. Failed task outcomes stay in the selected-output population.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
import threading
import time
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path

from harness2_support import ROOT, ensure_runtime
from runtime import api, load_on_gpu, require_allocation


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pack(directory, archive):
    """Store a stream directory as one verified tar.gz (shared-filesystem file quotas), then remove it."""
    directory, archive = Path(directory), Path(archive)
    part = archive.with_name(archive.name + '.part')
    with tarfile.open(part, 'w:gz') as tar:
        tar.add(directory, arcname=directory.name)
    expected = sum(1 for _ in directory.rglob('*')) + 1
    with tarfile.open(part, 'r:gz') as tar:
        found = len(tar.getmembers())
    if found != expected:
        raise RuntimeError(f'Stream archive entry mismatch: {found} != {expected}')
    os.replace(part, archive)
    shutil.rmtree(directory)
    return {'file': archive.name, 'sha256': sha(archive), 'entries': found}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--lock', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    require_allocation()
    ensure_runtime()

    protocol_path = ROOT / 'experiments/humaneval/protocol.json'
    protocol = json.loads(protocol_path.read_text())
    if args.model not in protocol['models'] or args.seed not in protocol['seeds']:
        raise SystemExit('Model/seed is outside the frozen protocol')
    release = json.loads((ROOT / 'integrations/harness2/evidence/readiness.json').read_text())
    if not release['passed'] or any(sha(ROOT / p) != expected for p, expected in release['source_sha256'].items()):
        raise SystemExit('Coding verification source identity is stale')
    identity = json.loads(args.lock.read_text())['models'][args.model]['digest']
    expected = json.loads((ROOT / 'hpc/config/models.frozen.json').read_text())['models'][args.model]['digest']
    if identity != expected:
        raise SystemExit('Model lock differs from the study frozen model identity')
    if next((m['digest'] for m in api('tags')['models'] if m['name'] == args.model), None) != identity:
        raise SystemExit('Frozen model identity mismatch')
    options = {**protocol['decoding'], 'num_thread': int(os.environ.get('SLURM_CPUS_PER_TASK', '4'))}
    load_on_gpu(args.model, identity, num_ctx=options['num_ctx'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Release amendment 3: the per-call stream tree is built on node-local disk and stored as one archive.
    stream_root = Path(os.environ.get('SLURM_TMPDIR') or args.output.parent) / args.output.with_suffix('').name
    archive = args.output.with_suffix('.stream.tar.gz')
    if stream_root.exists() or args.output.exists() or archive.exists() or args.output.with_suffix('').exists():
        raise SystemExit('Existing stream must be inspected; in-memory authority is not automatically recoverable')
    stream_root.mkdir()
    try:
        stored = run_stream(args, protocol, protocol_path, identity, options, stream_root)
    except BaseException:
        pack(stream_root, args.output.with_suffix(f'.failed-{time.time_ns()}.stream.tar.gz'))
        raise
    receipt = {**stored['receipt'], 'stream_archive': pack(stream_root, archive)}
    args.output.with_suffix('.freeze.json').write_text(json.dumps(receipt, indent=2) + '\n')


def run_stream(args, protocol, protocol_path, identity, options, stream_root):
    from experiments.scripts.humaneval_adapter import adapter_class
    from harness2.core import library, schedule, selection
    from harness2.core.spec import RunView
    from ssevoh_harness2.bridge import integrated
    from experiments.scripts.humaneval_proposer import proposer_class
    raw = stream_root / 'raw'
    raw.mkdir()
    calls = []
    call_lock = threading.Lock()
    condition = None

    def client(prompt, label):
        with call_lock:
            if len(prompt.encode()) > protocol['max_client_response_bytes'] * 2:
                raise ValueError('Public context exceeds declared byte bound')
            seed = args.seed + int(hashlib.sha256((condition + '|' + label).encode()).hexdigest()[:6], 16)
            request = {'model': args.model, 'prompt': prompt, 'format': 'json', 'stream': False,
                       'keep_alive': '5m', 'options': {**options, 'seed': seed}}
            record = {'index': len(calls), 'condition': condition, 'label': label, 'task_id': task,
                      'started_utc': datetime.now(UTC).isoformat(), 'request': request, 'state': 'running'}
            path = raw / f'{len(calls):06d}.json'
            # Append intent before the call: failed attempts keep unique raw identities.
            calls.append(record)
            path.write_text(json.dumps(record, indent=2))
            start = time.perf_counter()
            print(f'CALL_START condition={condition} call={record["index"]} label={label}', flush=True)
            try:
                response = api('generate', request)
                resident = next((m for m in api('ps')['models'] if m.get('digest') == identity), None)
                fully_gpu = bool(resident and resident.get('size_vram', 0) >= resident.get('size', 1))
                record.update(response=response, fully_gpu=fully_gpu, state='complete')
                if not fully_gpu:
                    raise RuntimeError('Model lost full GPU residency')
                if response.get('prompt_eval_count', 0) >= options['num_ctx'] - options['num_predict']:
                    raise ValueError('Context saturation violates complete-context protocol')
                if len(response.get('response', '').encode()) > protocol['max_client_response_bytes']:
                    raise ValueError('Oversized model response')
                return response
            except Exception as exc:
                record.update(state='failed', error=f'{type(exc).__name__}: {exc}')
                raise
            finally:
                record['seconds'] = time.perf_counter() - start
                path.write_text(json.dumps(record, indent=2))
                print(f'CALL_END call={record["index"]} state={record["state"]} seconds={record["seconds"]:.3f}', flush=True)

    selected = []
    task_order = None
    for condition in protocol['condition_orders'][str(args.seed)]:
        root = stream_root / condition
        adapter = adapter_class()(root, ROOT / 'experiments/humaneval/public-v0.1.10.jsonl', client,
                                  model=args.model, model_digest=identity,
                                  protocol={'protocol_sha256': sha(protocol_path), 'decoding': options},
                                  public_sha256=protocol['public_sha256'])
        proposer = proposer_class()(args.model, client)
        if proposer.spec != adapter.spec.channels['selector'] or proposer.spec != adapter.spec.channels['proposer']:
            raise RuntimeError('All method channels must use the exact data-only model client')
        tasks = protocol['smoke_tasks'] if args.smoke else adapter.tasks()
        task_order = [task for _, task in schedule.stream_order({'python': tasks}, args.seed, ['python'])]
        context = integrated(adapter, root / 'authority') if condition == 'guarded' else nullcontext((adapter, None))
        with context as (active, authority):
            lib = library.Library(root=root / 'library', domain='python', surface=adapter.substrate.surface())
            for index, task in enumerate(task_order):
                started = time.perf_counter()
                call_start = len(calls)
                error = None
                answer = None
                one_shot = None
                chosen_dir = None
                try:
                    if condition == 'frozen':
                        candidates = {}
                        for rollout in range(protocol['frozen_solver_calls_per_task']):
                            label = f'agg{rollout + 1}'
                            rid = f'frozen/{args.seed}/{task}/{label}'
                            try:
                                rd = active.execute(task, None, rid)
                                candidates[label] = RunView(label=label, run_id=rid, run_dir=rd, ok=True,
                                                            delivered=active.delivered(rd), error='')
                                if rollout == 0:
                                    one_shot = active.deliverable_text(rd)
                            except Exception as exc:
                                candidates[label] = RunView(label=label, run_id=rid, run_dir=root / 'missing', ok=False,
                                                            delivered=False, error=f'{type(exc).__name__}: {exc}')
                        decision = selection.run_selection(task, len(candidates), 'agg', candidates,
                                                           adapter=active, prop=proposer,
                                                           work_dir=root / 'selection-work' / task.replace('/', '__'),
                                                           pool_kind='finals')
                        chosen = candidates.get(decision.chosen_label)
                        if decision.ok and chosen and chosen.delivered:
                            chosen_dir = chosen.run_dir
                            answer = active.deliverable_text(chosen_dir)
                        else:
                            error = decision.error or 'No selected deliverable'
                    else:
                        # Same declared bounded retention policy for both recursive conditions.
                        lib.retain(task_order[max(0, index - protocol['library_window']):index])
                        result = schedule.run_task(task, protocol['k'], adapter=active, prop=proposer,
                                                   runs_root=adapter.spec.runs_root, modes=(protocol['mode'],),
                                                   seed=args.seed, library=lib, selector_prop=proposer)
                        decision = result.selections.get(protocol['mode'], {})
                        value = decision.get('chosen_run_dir')
                        if decision.get('ok') and value and active.delivered(Path(value)):
                            chosen_dir = Path(value)
                            answer = active.deliverable_text(chosen_dir)
                        if result.errors:
                            error = '; '.join(result.errors)
                except Exception as exc:
                    error = f'{type(exc).__name__}: {exc}'
                row = {'task_id': task, 'model': args.model, 'model_digest': identity, 'seed': args.seed,
                       'condition': condition + '-selected' if condition == 'frozen' else condition,
                       'solution': answer, 'error': error, 'chosen_run_dir': str(chosen_dir) if chosen_dir else None,
                       'selection_sha256': hashlib.sha256(answer.encode()).hexdigest() if answer is not None else None,
                       'calls': len(calls) - call_start, 'seconds': time.perf_counter() - started,
                       'tokens': sum(r.get('response', {}).get('eval_count', 0) for r in calls[call_start:]),
                       'prompt_tokens': sum(r.get('response', {}).get('prompt_eval_count', 0) for r in calls[call_start:])}
                selected.append(row)
                if condition == 'frozen':
                    first_call = calls[call_start] if len(calls) > call_start else {}
                    selected.append({**row, 'condition': 'frozen-one-shot', 'solution': one_shot,
                                     'endpoint_shared_pool': True, 'calls': 1 if first_call else 0,
                                     'tokens': first_call.get('response', {}).get('eval_count', 0),
                                     'prompt_tokens': first_call.get('response', {}).get('prompt_eval_count', 0),
                                     'seconds': first_call.get('seconds', 0),
                                     'selection_sha256': hashlib.sha256(one_shot.encode()).hexdigest() if one_shot is not None else None})
                # A checkpoint is evidence, not a resume authorization.
                (root / 'selection-checkpoint.json').write_text(json.dumps(selected, indent=2))
                args.output.write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in selected))
                print(f'TASK_DONE condition={condition} task={task} delivered={answer is not None} error={error}', flush=True)
            if authority:
                (root / 'authority-events.json').write_text(json.dumps(authority.events, indent=2))
                (root / 'core-journal.json').write_text(json.dumps(authority.engine.journal, indent=2))
            (root / 'proposer-records.json').write_text(json.dumps(proposer.generated, indent=2))
            (root / 'edit-transport-events.json').write_text(json.dumps(proposer.transport_events, indent=2))
    args.output.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in selected))
    receipt = {'schema': 'ssevoh-humaneval-local-stream-freeze-v1', 'all_local_streams_frozen': True,
               'all_streams_frozen': False, 'samples_sha256': sha(args.output), 'protocol_sha256': sha(protocol_path),
               'tasks': task_order, 'model': args.model, 'model_digest': identity, 'seed': args.seed,
               'call_count': len(calls), 'fully_gpu': all(r.get('fully_gpu') is True for r in calls if 'response' in r),
               'failed_calls': sum(r.get('state') == 'failed' for r in calls),
               'output_rows': len(selected), 'utc': datetime.now(UTC).isoformat(),
               'cluster': os.environ.get('CLUSTER'), 'job_id': os.environ['SLURM_JOB_ID']}
    return {'receipt': receipt}


if __name__ == '__main__':
    main()

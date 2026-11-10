#!/usr/bin/env python3
"""Validate the complete declared stream population before enabling hidden grading."""
import argparse
import hashlib
import json
from pathlib import Path

CONDITIONS = {'frozen-one-shot', 'frozen-selected', 'original', 'guarded'}


def freeze(root, models, seeds, tasks, output, receipt, protocol_sha256):
    expected = {(m, seed, task, condition) for m in models for seed in seeds for task in tasks for condition in CONDITIONS}
    rows = []
    streams = []
    seen = set()
    for path in sorted(root.glob('selected-*.jsonl')):
        local_path = path.with_suffix('.freeze.json')
        local = json.loads(local_path.read_text())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if (local.get('all_local_streams_frozen') is not True or local.get('samples_sha256') != digest
                or local.get('protocol_sha256') != protocol_sha256):
            raise ValueError('Local stream freeze identity mismatch: ' + str(path))
        streams.append({'file': path.name, 'sha256': digest, 'model': local['model'], 'seed': local['seed']})
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if row.get('model') != local['model'] or row.get('seed') != local['seed']:
                raise ValueError('Local receipt does not own these model/seed outputs')
            key = row['model'], row['seed'], row['task_id'], row['condition']
            if key not in expected or key in seen:
                raise ValueError('Unexpected or duplicate frozen outcome: ' + str(key))
            seen.add(key)
            solution = row['solution']
            if solution is not None and (not isinstance(solution, str) or row.get('selection_sha256') != hashlib.sha256(solution.encode()).hexdigest()):
                raise ValueError('Selected bytes mismatch')
            rows.append(row)
    if seen != expected:
        raise ValueError(f'Incomplete intended population: {len(seen)}/{len(expected)}')
    body = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as target:
        target.write(body)
    report = {'schema': 'ssevoh-humaneval-global-freeze-v1', 'all_streams_frozen': True,
              'samples_sha256': hashlib.sha256(body).hexdigest(), 'protocol_sha256': protocol_sha256,
              'streams': streams, 'models': models, 'seeds': seeds, 'tasks': tasks,
              'conditions': sorted(CONDITIONS), 'expected_rows': len(expected),
              'missing_solutions': sum(row['solution'] is None for row in rows),
              'warning': 'Frozen selections establish completeness, not correctness or successful workflows.'}
    with receipt.open('x') as target:
        json.dump(report, target, indent=2)
        target.write('\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--models', nargs='+', required=True)
    parser.add_argument('--seeds', nargs='+', type=int, required=True)
    parser.add_argument('--tasks', nargs='+')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, required=True)
    args = parser.parse_args()
    tasks = args.tasks or [f'HumanEval/{i}' for i in range(164)]
    print(json.dumps(freeze(args.root, args.models, args.seeds, tasks, args.output, args.receipt,
                            hashlib.sha256(args.protocol.read_bytes()).hexdigest()), indent=2))


if __name__ == '__main__':
    main()

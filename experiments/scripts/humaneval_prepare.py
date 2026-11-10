#!/usr/bin/env python3
"""Project a pinned full HumanEval+ dataset into public method inputs.

Hidden tests and canonical solutions remain in the separate source file. This
script never imports EvalPlus, executes solutions, or creates grading feedback.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path

PUBLIC_FIELDS = frozenset({'task_id', 'prompt', 'entry_point'})


def project(source: Path, expected_sha256: str, destination: Path):
    raw = source.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if not re.fullmatch(r'[a-f0-9]{64}', expected_sha256) or actual != expected_sha256:
        raise ValueError('Private dataset identity mismatch')
    decoded = gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw
    records = [json.loads(line) for line in decoded.decode().splitlines() if line.strip()]
    ids = [r['task_id'] for r in records]
    if len(ids) != 164 or set(ids) != {f'HumanEval/{i}' for i in range(164)}:
        raise ValueError('A full unique 164-task HumanEval+ snapshot is required')
    rows = []
    for record in records:
        if any(not isinstance(record.get(key), str) or not record[key] for key in PUBLIC_FIELDS):
            raise ValueError('Malformed public task fields')
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', record['entry_point']):
            raise ValueError('Invalid entry point')
        rows.append({key: record[key] for key in sorted(PUBLIC_FIELDS)})
    rows.sort(key=lambda row: int(row['task_id'].split('/')[1]))
    body = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows).encode()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream:
        stream.write(body)
    return {'schema': 'ssevoh-humaneval-public-projection-v1', 'tasks': len(rows),
            'private_dataset_sha256': actual, 'public_sha256': hashlib.sha256(body).hexdigest(),
            'public_fields': sorted(PUBLIC_FIELDS), 'hidden_grading_performed': False}


def read_public(path: Path):
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(records) != 164 or len({r.get('task_id') for r in records}) != 164:
        raise ValueError('Expected a complete unique public task projection')
    for row in records:
        if set(row) != PUBLIC_FIELDS or any(not isinstance(v, str) or not v for v in row.values()):
            raise ValueError('Non-public fields or malformed values in method dataset')
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', row['entry_point']):
            raise ValueError('Invalid public entry-point identifier')
    if {r['task_id'] for r in records} != {f'HumanEval/{i}' for i in range(164)}:
        raise ValueError('Unexpected benchmark identifiers')
    return {row['task_id']: row for row in records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-dataset', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--public-output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    report = project(args.private_dataset, args.sha256, args.public_output)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()

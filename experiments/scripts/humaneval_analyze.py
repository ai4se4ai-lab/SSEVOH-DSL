#!/usr/bin/env python3
"""All-attempts coding summaries with descriptive whole-stream comparisons.

Online library state couples tasks. Seeds define ordered stream replications;
there are no task-bootstrap, significance, noninferiority or population-CI claims.
"""
import argparse
import collections
import hashlib
import json
import statistics
from pathlib import Path


def key(row):
    return row['model'], row['seed'], row['task_id'], row['condition']


def summarize(samples, grades, tasks):
    if len({key(r) for r in samples}) != len(samples):
        raise ValueError('Duplicate intended outcomes')
    if len({key(r) for r in grades}) != len(grades) or {key(r) for r in grades} != {key(r) for r in samples}:
        raise ValueError('Grading does not match the complete intended population')
    original = {key(row): row for row in samples}
    grouped = collections.defaultdict(list)
    streams = collections.defaultdict(list)
    for row in grades:
        if row.get('selection_sha256') != original[key(row)].get('selection_sha256'):
            raise ValueError('Graded solution identity differs from frozen selection')
        if type(row.get('passed')) is not bool or row.get('status') not in ('graded', 'missing_solution', 'evaluator_error'):
            raise ValueError('Malformed grading outcome')
        grouped[(row['model'], row['condition'])].append(row)
        streams[(row['model'], row['seed'], row['condition'])].append(row)
    def counts(rows):
        statuses = collections.Counter(row['status'] for row in rows)
        passed = sum(row['passed'] and row['status'] == 'graded' for row in rows)
        graded = statuses['graded']
        return {'planned': len(rows), 'graded': graded, 'passed': passed,
                'intention_to_evaluate_accuracy': passed / len(rows),
                'graded_only_accuracy': passed / graded if graded else None,
                'statuses': dict(statuses),
                'method_errors': sum(bool(original[key(row)].get('error')) for row in rows)}
    summaries = [{'model': model, 'condition': condition, **counts(rows)}
                 for (model, condition), rows in sorted(grouped.items())]
    stream_rows = []
    for (model, seed, condition), rows in sorted(streams.items()):
        cost = [original[key(row)] for row in rows]
        value = {'model': model, 'seed': seed, 'condition': condition, **counts(rows)}
        for name in ('calls', 'tokens', 'prompt_tokens', 'seconds'):
            value[name] = sum(row[name] for row in cost) if all(name in row for row in cost) else None
        value['cost_note'] = ('Nested one-shot endpoint shares the frozen pool; do not add endpoint costs.'
                              if condition == 'frozen-one-shot' else 'Observed condition cost; retries and failures retained.')
        for exclude, label in [({'HumanEval/0', 'HumanEval/1'}, 'excluding_two_model_smoke_tasks'),
                               ({'HumanEval/0', 'HumanEval/1', 'HumanEval/2'}, 'excluding_three_control_exposed_tasks')]:
            subset = [row for row in rows if row['task_id'] not in exclude]
            value[label] = counts(subset) if subset else None
        stream_rows.append(value)
    lookup = {(r['model'], r['seed'], r['condition']): r for r in stream_rows}
    comparisons = []
    models = sorted({row['model'] for row in samples})
    for model in models:
        seeds = sorted({row['seed'] for row in samples if row['model'] == model})
        for reference in ('original', 'frozen-selected'):
            differences = [{'seed': seed, 'guarded_minus_reference':
                            lookup[model, seed, 'guarded']['intention_to_evaluate_accuracy'] -
                            lookup[model, seed, reference]['intention_to_evaluate_accuracy']} for seed in seeds]
            values = [r['guarded_minus_reference'] for r in differences]
            comparisons.append({'model': model, 'reference': reference, 'paired_streams': differences,
                                'mean_difference': statistics.mean(values), 'minimum_difference': min(values),
                                'maximum_difference': max(values),
                                'sample_sd': statistics.stdev(values) if len(values) > 1 else None})
    return {'schema': 'ssevoh-humaneval-analysis-v2', 'summaries': summaries,
            'ordered_streams': stream_rows, 'paired_stream_comparisons': comparisons,
            'full_164_task_coverage': set(tasks) == {f'HumanEval/{i}' for i in range(164)},
            'sample_rows': len(samples), 'grade_rows': len(grades),
            'limitation': 'Descriptive fixed-benchmark evidence. Ordered online streams are the replication unit; no task-independent inference or general superiority claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=Path, required=True)
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--grades', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    frozen = json.loads(args.freeze.read_text())
    if frozen.get('all_streams_frozen') is not True or frozen.get('samples_sha256') != hashlib.sha256(args.samples.read_bytes()).hexdigest():
        raise SystemExit('Frozen population identity mismatch')
    samples = [json.loads(line) for line in args.samples.read_text().splitlines()]
    grades = [json.loads(line) for path in args.grades for line in path.read_text().splitlines()]
    report = summarize(samples, grades, frozen['tasks'])
    args.output.mkdir(parents=True, exist_ok=True)
    report['input_sha256'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in [args.samples, args.freeze, *args.grades]}
    (args.output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    text = ['# Coding benchmark results', '', '| Model | Condition | Passed / planned | Graded | All-attempts accuracy |', '|---|---|---:|---:|---:|']
    for r in report['summaries']:
        text.append(f"| {r['model']} | {r['condition']} | {r['passed']}/{r['planned']} | {r['graded']} | {r['intention_to_evaluate_accuracy']:.3f} |")
    text += ['', report['limitation'], '']
    (args.output / 'summary.md').write_text('\n'.join(text))


if __name__ == '__main__':
    main()

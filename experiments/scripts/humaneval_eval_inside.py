"""One-task evaluator entry point; invoked ONLY inside the isolated supervisor.

Uses pinned, unmodified EvalPlus test semantics. No generation/network/provider
packages are imported. Input and evaluator dependencies are mounted read-only;
only the output work directory is writable. This does not assert resistance to
an adversarial program attacking the in-container evaluator itself.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--vendor-root', type=Path, required=True)
    args = parser.parse_args()
    sys.path[:0] = [str(args.vendor_root / 'deps'), str(args.vendor_root / 'evalplus-src')]
    from evalplus.eval import PASS, untrusted_check
    from evalplus.gen.util import trusted_exec

    data = json.loads(args.input.read_text())
    problem = data['problem']
    solution = data['solution']
    references = {}
    # Trusted canonical executions are inside the same host-isolation boundary.
    for key in ('base', 'plus'):
        values, times = trusted_exec(problem['prompt'] + problem['canonical_solution'],
                                     problem[key + '_input'], problem['entry_point'], record_time=True)
        references[key] = (values, times)
    outcomes = {}
    for key in ('base', 'plus'):
        values, times = references[key]
        status, details = untrusted_check('humaneval', solution, problem[key + '_input'],
                                          problem['entry_point'], expected=values,
                                          atol=problem['atol'], ref_time=times,
                                          fast_check=False, min_time_limit=0.2,
                                          gt_time_limit_factor=4.0)
        outcomes[key] = {'status': status, 'passed': status == PASS,
                         'tests': len(problem[key + '_input']),
                         'passed_inputs': int(sum(details))}
    args.output.write_text(json.dumps({'task_id': problem['task_id'], 'outcomes': outcomes,
                                       'passed': all(r['passed'] for r in outcomes.values())}) + '\n')


if __name__ == '__main__':
    main()

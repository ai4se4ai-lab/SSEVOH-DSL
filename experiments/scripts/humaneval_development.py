#!/usr/bin/env python3
"""Disjoint development-only calibration of the model edit transport.

No HumanEval task, solution, hidden input, or grade enters the model call.
This verifies path transport, not improvement or benchmark performance.
"""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

from harness2_support import ROOT, ensure_runtime
from runtime import api, load_on_gpu, require_allocation


def coding_fixture(root):
    """Use the coding adapter's exact base without supplying any task to the model."""
    from types import SimpleNamespace
    from experiments.scripts.humaneval_adapter import coding_base
    from harness2.substrate.opencode import OpencodeSubstrate
    from harness2.core import tree
    substrate = OpencodeSubstrate()
    tree.write_tree(substrate.surface(), coding_base(substrate.surface()), root / 'base', stubs=False)
    return SimpleNamespace(substrate=substrate, base_harness=lambda: root / 'base')


def edit_check(surface, workspace, baseline):
    from harness2.core import tree
    actual = tree.read_tree(surface, workspace) if workspace else {}
    changed = {name for name in actual.keys() | baseline.keys() if actual.get(name) != baseline.get(name)}
    return changed == {'LongTermMEMORY.md'} and 'empty' in actual.get('LongTermMEMORY.md', '').lower(), sorted(changed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--lock', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require_allocation()
    ensure_runtime()
    from experiments.scripts.humaneval_proposer import proposer_class
    from harness2.core import tree
    identity = json.loads(args.lock.read_text())['models'][args.model]['digest']
    expected = json.loads((ROOT / 'hpc/config/models.frozen.json').read_text())['models'][args.model]['digest']
    if identity != expected:
        raise SystemExit('Development model differs from the frozen study identity')
    protocol = json.loads((ROOT / 'experiments/humaneval/protocol.json').read_text())
    load_on_gpu(args.model, identity, num_ctx=protocol['decoding']['num_ctx'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    root = args.output.with_suffix('')
    if root.exists():
        raise SystemExit('Existing development trial must be inspected')
    root.mkdir()
    original = coding_fixture(root / 'fixture')
    context = root / 'context'
    context.mkdir()
    shutil.copytree(original.base_harness(), context / 'harness')
    (context / 'task.md').write_text('Development-only interface calibration. No benchmark task is supplied.')
    calls = []
    def client(prompt, label):
        if 'HumanEval/' in prompt:
            raise ValueError('Benchmark task leaked into disjoint development calibration')
        payload = {'model': args.model, 'prompt': prompt, 'format': 'json', 'stream': False,
                   'options': {**protocol['decoding'], 'seed': 7021,
                               'num_thread': int(os.environ.get('SLURM_CPUS_PER_TASK', '4'))}}
        response = api('generate', payload)
        resident = next((r for r in api('ps')['models'] if r.get('digest') == identity), None)
        fully_gpu = bool(resident and resident.get('size_vram', 0) >= resident.get('size', 1))
        calls.append({'label': label, 'request': payload, 'response': response, 'fully_gpu': fully_gpu})
        if not fully_gpu:
            raise RuntimeError('Development response lost full GPU residency')
        return response
    proposer = proposer_class()(args.model, client)
    reply = proposer.call(
        'This is a mandatory development-only edit-transport check. Replace LongTermMEMORY.md with a short '
        'reminder to consider empty input lists when implementing Python functions. Keep all other files unchanged. '
        'The files object must contain exactly one key: LongTermMEMORY.md. Omit every other file; omitted bytes are inherited exactly. '
        'The objective is to verify exact allowed-path transport, not infer a benchmark improvement.',
        context, 'development.edit')
    baseline = tree.read_tree(original.substrate.surface(), original.base_harness())
    ok, changed = edit_check(original.substrate.surface(), reply.workspace, baseline)
    report = {'schema': 'ssevoh-disjoint-edit-calibration-v1', 'model': args.model, 'model_digest': identity,
              'passed': ok, 'changed_paths': sorted(changed), 'calls': calls,
              'edit_transport_events': proposer.transport_events,
              'benchmark_tasks_supplied': False, 'generated_code_executed': False,
              'job_id': os.environ['SLURM_JOB_ID'],
              'protocol_sha256': hashlib.sha256((ROOT / 'experiments/humaneval/protocol.json').read_bytes()).hexdigest()}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    if not ok:
        raise SystemExit('Development edit-transport calibration failed; benchmark stream not started')


if __name__ == '__main__':
    main()

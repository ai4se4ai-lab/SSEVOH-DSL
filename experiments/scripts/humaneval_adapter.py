"""Public-only coding substrate for the pinned original Harness² workflow.

Generation is data-only. No solution is executed, and no hidden grading is
available through this adapter. Its non-executable evolution contract requires a fresh source-scoped verification
release before any empirical generation.
"""
from __future__ import annotations

import ast
import functools
import hashlib
import json
import re
from pathlib import Path

from experiments.scripts.humaneval_prepare import read_public


def coding_base(surface):
    """Shared task-free baseline for coding and disjoint transport calibration."""
    base = {name: '' for name in surface.always_on}
    base['systemprompt.md'] = (
        'Implement the requested Python function accurately. Include required imports. '
        'Return the complete module in the solution JSON field. Use the public specification only.\n'
    )
    return base


@functools.cache
def adapter_class():
    # Import only after harness2_support.ensure_runtime() verifies the pinned runtime.
    from harness2.core import tree
    from harness2.core.spec import BenchPrompts, BenchSpec, ChannelSpec
    from harness2.substrate.opencode import OpencodeSubstrate

    class HumanEvalAdapter:
        def __init__(self, root, public_dataset, client, *, model, model_digest, protocol, public_sha256):
            self.root = Path(root)
            actual_public = hashlib.sha256(Path(public_dataset).read_bytes()).hexdigest()
            if actual_public != public_sha256 or not re.fullmatch('[a-f0-9]{64}', model_digest):
                raise ValueError('Public dataset or model identity mismatch')
            self.public = read_public(Path(public_dataset))
            self.generation_context = {'public_sha256': actual_public, 'model': model,
                                       'model_digest': model_digest, 'protocol': json.loads(json.dumps(protocol, sort_keys=True))}
            self.generation_context_sha256 = hashlib.sha256(json.dumps(self.generation_context, sort_keys=True).encode()).hexdigest()
            self.client = client
            self.substrate = OpencodeSubstrate()
            channel = ChannelSpec('opencode', 'local/' + model)
            self.spec = BenchSpec(
                name='humaneval-public-generation', runs_root=self.root / 'runs',
                install_mode='workspace_config',
                prompts=BenchPrompts(work='implement the supplied Python function from its public specification'),
                channels={'proposer': channel, 'selector': channel},
                leak_globs=('canonical_solution*', '*grading*', '*verdict*', '*eval_results*'),
            )
            base = coding_base(self.substrate.surface())
            tree.write_tree(self.substrate.surface(), base, self.base_harness(), stubs=False)

        def tasks(self, split='all'):
            if split != 'all':
                raise ValueError('Only the frozen full public split is supported')
            return sorted(self.public, key=lambda task: int(task.split('/')[1]))

        def domain_of(self, task_id):
            self.public[task_id]
            return 'python'

        def task_prompt(self, task_id):
            return self.public[task_id]['prompt']

        def task_files(self, task_id):
            self.public[task_id]
            return None

        def base_harness(self):
            return self.root / 'base'

        def validate_tree(self, files):
            tree.validate(self.substrate.surface(), files)
            for name, body in files.items():
                allowed = name in self.substrate.surface().always_on or re.fullmatch(r'skills/[a-z0-9][a-z0-9_-]*/SKILL\.md', name)
                if not allowed or not name.endswith('.md') or not isinstance(body, str):
                    raise ValueError('Coding study permits supported Markdown harness files only')
                if name in ('guardrails.md', 'tool_descriptions/tool_guidance.md') and body:
                    raise ValueError('Standing protected instructions are immutable in every coding condition')
                if len(body) > 100_000:
                    raise ValueError('Harness text exceeds coding protocol bound')

        def execute(self, task_id, harness_dir, run_id, *, timeout=None):
            if not isinstance(run_id, str) or not run_id or len(run_id) > 1000 or '\x00' in run_id:
                raise ValueError('Invalid run identifier')
            target = self.root / 'executions' / hashlib.sha256(run_id.encode()).hexdigest()
            # A failed/incomplete existing run is never silently called successful.
            if target.exists():
                manifest = json.loads((target / 'generation.json').read_text())
                if manifest['generation_context_sha256'] != self.generation_context_sha256:
                    raise ValueError('Existing run belongs to another dataset/model/protocol context')
                if manifest['run_id'] != run_id or manifest['task_id'] != task_id or not (target / 'answer.txt').is_file():
                    raise ValueError('Run identity conflict or incomplete generation')
                files = tree.read_tree(self.substrate.surface(), harness_dir or self.base_harness())
                expected = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
                if manifest['solution_sha256'] != hashlib.sha256((target / 'answer.txt').read_bytes()).hexdigest():
                    raise ValueError('Existing deliverable bytes changed')
                if manifest['harness_sha256'] != expected:
                    raise ValueError('Existing run belongs to different harness bytes')
                return target
            files = tree.read_tree(self.substrate.surface(), harness_dir or self.base_harness())
            self.validate_tree(files)
            prompt = ('Generate a complete Python module implementing this public function. '
                      'Respond as JSON with a single string field named solution. Do not execute code.\n'
                      + json.dumps({'task': self.public[task_id], 'harness': files}, sort_keys=True))
            response = self.client(prompt, 'executor.' + run_id + '.solution')
            payload = json.loads(response.get('response', ''))
            solution = payload.get('solution') if isinstance(payload, dict) else None
            if not isinstance(solution, str) or not solution.strip() or len(solution) > 100_000:
                raise ValueError('Missing, empty, or oversized solution')
            # Static feedback only, never hidden-test/canonical feedback.
            feedback = {'code_executed': False}
            try:
                module = ast.parse(solution)
                entry = self.public[task_id]['entry_point']
                feedback.update(parses=True, entry_point_present=any(
                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == entry
                    for node in module.body))
            except (SyntaxError, ValueError, RecursionError) as exc:
                feedback.update(parses=False, error=str(exc))
            target.mkdir(parents=True)
            (target / 'answer.txt').write_text(solution)
            (target / 'trajectory.md').write_text('[ACTION] Generate solution\n[OBSERVATION] '
                                                  + json.dumps(feedback) + '\n[FINAL]\n' + solution)
            manifest = {'run_id': run_id, 'task_id': task_id,
                        'generation_context': self.generation_context,
                        'generation_context_sha256': self.generation_context_sha256,
                        'task_sha256': hashlib.sha256(json.dumps(self.public[task_id], sort_keys=True).encode()).hexdigest(), 'harness_sha256': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
                        'solution_sha256': hashlib.sha256(solution.encode()).hexdigest(), 'feedback': feedback}
            (target / 'generation.json').write_text(json.dumps(manifest, indent=2) + '\n')
            activation = {'executor': 'data-only coding generation', 'code_executed': False,
                          'harness_sha256': manifest['harness_sha256'], 'solution_sha256': manifest['solution_sha256'],
                          'generation_context_sha256': self.generation_context_sha256}
            (target / 'activation.json').write_text(json.dumps(activation, indent=2) + '\n')
            return target

        def delivered(self, run_dir):
            return (Path(run_dir) / 'answer.txt').is_file()

        def trajectory(self, run_dir, *, obs_trunc):
            return (Path(run_dir) / 'trajectory.md').read_text()

        def deliverable_text(self, run_dir):
            return (Path(run_dir) / 'answer.txt').read_text()

        def deliverable_files(self, run_dir):
            return {'solution.py': self.deliverable_text(run_dir)}

        def score(self, run_dir, task_id):
            raise RuntimeError('Hidden grading is unavailable in method process; export frozen selections to the external evaluator')

    return HumanEvalAdapter

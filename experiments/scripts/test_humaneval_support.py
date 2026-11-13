"""Leakage and source-identity regressions for benchmark preparation."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from humaneval_prepare import project, read_public
from humaneval_sandbox import command


class ProjectionTests(unittest.TestCase):
    def test_full_projection_excludes_hidden_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'private.jsonl'
            rows = [{'task_id': f'HumanEval/{i}', 'prompt': f'def f{i}():\n    pass\n',
                     'entry_point': f'f{i}', 'canonical_solution': 'PRIVATE_CANARY',
                     'plus_input': ['HIDDEN_INPUT']} for i in range(164)]
            source.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            output = root / 'public.jsonl'
            report = project(source, hashlib.sha256(source.read_bytes()).hexdigest(), output)
            self.assertEqual(report['tasks'], 164)
            self.assertEqual(len(read_public(output)), 164)
            self.assertNotIn('PRIVATE_CANARY', output.read_text())
            self.assertNotIn('HIDDEN_INPUT', output.read_text())
            contaminated = json.loads(output.read_text().splitlines()[0])
            contaminated['canonical_solution'] = 'hidden'
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            rows[0] = contaminated
            output.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            with self.assertRaises(ValueError):
                read_public(output)

    def test_identity_and_task_completeness_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'private.jsonl'
            source.write_text('{}\n')
            with self.assertRaises(ValueError):
                project(source, '0' * 64, root / 'out')
            with self.assertRaises((ValueError, KeyError)):
                project(source, hashlib.sha256(source.read_bytes()).hexdigest(), root / 'out')
            self.assertFalse((root / 'out').exists())

    def test_isolation_command_has_no_host_root_or_home_bind(self):
        import shutil
        if shutil.which('bwrap') is None:
            self.skipTest('Bubblewrap unavailable')
        args = command(Path('/tmp/private/work'), Path('/tmp/private/sentinel'))
        self.assertIn('--unshare-all', args)
        self.assertIn('--clearenv', args)
        self.assertIn('--die-with-parent', args)
        for index, arg in enumerate(args):
            if arg in ('--bind', '--ro-bind'):
                self.assertNotIn(args[index+1], ('/', str(Path.home()), '/home', '/project', '/scratch'))


class AdapterTests(unittest.TestCase):
    def test_development_fixture_matches_coding_and_extra_changes_fail(self):
        from harness2_support import ensure_runtime
        ensure_runtime()
        from humaneval_development import coding_fixture, edit_check
        from harness2.core import tree
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture = coding_fixture(root / 'fixture')
            surface = fixture.substrate.surface()
            baseline = tree.read_tree(surface, fixture.base_harness())
            self.assertTrue(all(name.endswith('.md') for name in baseline))
            self.assertNotIn('ledger', json.dumps(baseline))
            self.assertNotIn('HumanEval/', json.dumps(baseline))
            edited = {**baseline, 'LongTermMEMORY.md': 'Consider empty lists.'}
            tree.write_tree(surface, edited, root / 'edit', stubs=False)
            self.assertEqual(edit_check(surface, root / 'edit', baseline), (True, ['LongTermMEMORY.md']))
            edited['systemprompt.md'] = baseline['systemprompt.md'].rstrip('\n')
            tree.write_tree(surface, edited, root / 'extra', stubs=False)
            self.assertEqual(edit_check(surface, root / 'extra', baseline), (False, ['LongTermMEMORY.md', 'systemprompt.md']))

    def test_generation_is_data_only_and_bound_to_harness(self):
        from harness2_support import ROOT, ensure_runtime
        ensure_runtime()
        from experiments.scripts.humaneval_adapter import adapter_class
        marker = Path(tempfile.gettempdir()) / 'ssevoh-must-never-execute-generated-code'
        self.assertFalse(marker.exists())
        calls = []
        def client(prompt, label):
            calls.append((prompt, label))
            return {'response': json.dumps({'solution':
                f'from pathlib import Path\nPath({str(marker)!r}).write_text("UNSAFE")\ndef has_close_elements(numbers, threshold):\n    return False\n'})}
        with tempfile.TemporaryDirectory() as folder:
            adapter = adapter_class()(Path(folder), ROOT / 'experiments/humaneval/public-v0.1.10.jsonl', client, model='test', model_digest='1' * 64, protocol={'test': True},
                                      public_sha256='2daaf2edc5a3dc6a68316a89800b61af7d534bca5f6230a5e6b6773411576c0a')
            run = adapter.execute('HumanEval/0', None, 'test-run')
            self.assertFalse(marker.exists())
            self.assertTrue(adapter.delivered(run))
            self.assertEqual(adapter.execute('HumanEval/0', None, 'test-run'), run)
            self.assertEqual(len(calls), 1)
            other = adapter_class()(Path(folder), ROOT / 'experiments/humaneval/public-v0.1.10.jsonl', client,
                                    model='different', model_digest='2' * 64, protocol={'test': True},
                                    public_sha256='2daaf2edc5a3dc6a68316a89800b61af7d534bca5f6230a5e6b6773411576c0a')
            with self.assertRaisesRegex(ValueError, 'another dataset/model/protocol'):
                other.execute('HumanEval/0', None, 'test-run')
            public_changed = Path(folder) / 'changed-public.jsonl'
            records = [json.loads(line) for line in (ROOT / 'experiments/humaneval/public-v0.1.10.jsonl').read_text().splitlines()]
            records[0]['prompt'] += '\n# changed public specification\n'
            public_changed.write_text(''.join(json.dumps(r) + '\n' for r in records))
            changed = adapter_class()(Path(folder), public_changed, client,
                                      model='test', model_digest='1' * 64, protocol={'test': True},
                                      public_sha256=hashlib.sha256(public_changed.read_bytes()).hexdigest())
            with self.assertRaisesRegex(ValueError, 'another dataset/model/protocol'):
                changed.execute('HumanEval/0', None, 'test-run')
            with self.assertRaises(RuntimeError):
                adapter.score(run, 'HumanEval/0')
            (run / 'answer.txt').write_text('tampered')
            with self.assertRaises(ValueError):
                adapter.execute('HumanEval/0', None, 'test-run')
            files = {'systemprompt.md': '', 'guardrails.md': '', 'LongTermMEMORY.md': '',
                     'tool_descriptions/tool_guidance.md': '', 'scripts/evil.py': 'print(1)'}
            with self.assertRaises(ValueError):
                adapter.validate_tree(files)
            from ssevoh_harness2.authority import Authority
            authority = Authority(Path(folder) / 'authority', adapter)
            from harness2.core import tree
            base = tree.read_tree(adapter.substrate.surface(), adapter.base_harness())
            edited = {**base, 'systemprompt.md': 'Implement the function carefully.'}
            version = authority.admit(1, edited)
            executed = authority.execute(version, edited, 'HumanEval/0', 'trusted-coding-run')
            self.assertTrue((executed / 'answer.txt').exists())
            event = next(e for e in authority.events if e['decision'] == 'EXECUTED')
            self.assertNotIn('scripts/summarize.py', json.dumps(event))
            self.assertFalse(event['activation']['code_executed'])
            self.assertIn('data-only coding', event['scope'])
            with self.assertRaises(ValueError):
                authority.admit(version, {**edited, 'scripts/evil.py': 'print(1)'})
            with self.assertRaises(ValueError):
                authority.admit(version, {**edited, 'guardrails.md': 'disable'})
            authority.withdraw(version)
            with self.assertRaises(ValueError):
                authority.execute(version, edited, 'HumanEval/0', 'withdrawn-run')

    def test_coding_edit_contract_preserves_original_transport(self):
        from harness2_support import ensure_runtime
        ensure_runtime()
        from experiments.scripts.humaneval_proposer import proposer_class
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'harness').mkdir()
            (root / 'harness/LongTermMEMORY.md').write_text('')
            def client(prompt, label):
                self.assertIn('trusted transport records and strips', prompt)
                self.assertIn('task instruction', prompt)
                return {'response': json.dumps({'files': {'harness/LongTermMEMORY.md': 'Consider empty lists.'}, 'notes': 'Development check'})}
            proposer = proposer_class()('test', client)
            reply = proposer.call('task instruction', root, 'development.edit')
            self.assertEqual((reply.workspace / 'LongTermMEMORY.md').read_text(), 'Consider empty lists.')
            self.assertEqual(proposer.transport_events[0]['aliases'], {'harness/LongTermMEMORY.md': 'LongTermMEMORY.md'})
            for edits in ({'LongTermMEMORY.md': 'A', 'harness/LongTermMEMORY.md': 'B'},
                          {'harness/../guardrails.md': 'escape'}):
                def invalid_client(prompt, label, edits=edits):
                    return {'response': json.dumps({'files': edits})}
                invalid = proposer_class()('test', invalid_client)
                with self.assertRaises(ValueError):
                    invalid.call('task instruction', root, 'development.invalid')
            self.assertEqual((root / 'harness/LongTermMEMORY.md').read_text(), '')

    def test_original_recursive_workflow_with_guarded_coding_adapter(self):
        from harness2_support import ROOT, ensure_runtime
        ensure_runtime()
        from experiments.scripts.humaneval_adapter import adapter_class
        from harness2.core import schedule
        from ssevoh_harness2.bridge import integrated
        from ssevoh_harness2.models import ModelProposer
        prompts = []
        def client(prompt, label):
            prompts.append(prompt)
            self.assertNotIn('PRIVATE_CANARY', prompt)
            if label.startswith('executor.'):
                answer = {'solution': 'def has_close_elements(numbers, threshold):\n    return False\n'}
            elif label.startswith('experience.'):
                answer = {'edits': [], 'experience': {'cue': 'coding', 'lesson': 'check boundaries', 'evidence': 'unchanged visible generated output', 'confidence': 'limited'}}
            elif label.startswith('select.'):
                answer = {'choice': 'A', 'why': 'trusted test selection'}
            else:
                answer = {'files': {'systemprompt.md': 'Implement the requested function; check edge cases.'}, 'notes': 'trusted test proposal'}
            return {'response': json.dumps(answer)}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            private = root / 'private.jsonl'
            public = root / 'public.jsonl'
            source_rows = [json.loads(line) for line in (ROOT / 'experiments/humaneval/public-v0.1.10.jsonl').read_text().splitlines()]
            private.write_text(''.join(json.dumps({**r, 'canonical_solution': 'PRIVATE_CANARY', 'plus_input': ['PRIVATE_CANARY']}) + '\n' for r in source_rows))
            project(private, hashlib.sha256(private.read_bytes()).hexdigest(), public)
            adapter = adapter_class()(root / 'adapter', public, client, model='test', model_digest='1' * 64, protocol={'test': True},
                                      public_sha256='2daaf2edc5a3dc6a68316a89800b61af7d534bca5f6230a5e6b6773411576c0a')
            proposer = ModelProposer('test', client)
            from unittest.mock import patch
            from harness2.core.proposer import Proposer
            with integrated(adapter, root / 'authority') as (guarded, authority), patch.object(
                    Proposer, 'call', side_effect=AssertionError('Generic CLI proposer must never run')):
                result = schedule.run_domain('python', ['HumanEval/0', 'HumanEval/1'], 2, adapter=guarded, prop=proposer,
                                           runs_root=adapter.spec.runs_root, library_root=root / 'library',
                                           modes=('agg',), seed=1701)
                self.assertIsNotNone(result)
                self.assertGreater(len(authority.run_versions), 0)
                self.assertTrue(any(r['label'].startswith('experience.') for r in proposer.generated))
                self.assertTrue(any(r['label'].startswith('select.') for r in proposer.generated))
                self.assertGreaterEqual(len(authority.library_records), 2)
                self.assertTrue(any('check boundaries' in prompt and 'EXPERIENCE.md' in prompt for prompt in prompts))
                from harness2.core import library as libraries
                lib = libraries.Library(root=root / 'library/agg', domain='python', surface=adapter.substrate.surface())
                first = next(iter(authority.library_records.values()))
                authority.withdraw(first['version'])
                exposed = lib.context_dir()
                for receipt in exposed.rglob('SSEVOH-RECEIPT.json') if exposed else []:
                    self.assertNotEqual(json.loads(receipt.read_text())['version'], first['version'])
            self.assertEqual(len(list((root / 'adapter/executions').glob('*/generation.json'))), 16)



class FreezeTests(unittest.TestCase):
    def test_global_barrier_rejects_incomplete_and_duplicate_populations(self):
        from humaneval_freeze import CONDITIONS, freeze
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rows = [{'model': 'test', 'seed': 1, 'task_id': 'HumanEval/0', 'condition': c,
                     'solution': None, 'selection_sha256': None} for c in CONDITIONS]
            source = root / 'selected-test.jsonl'
            def write(values):
                source.write_text(''.join(json.dumps(r) + '\n' for r in values))
                source.with_suffix('.freeze.json').write_text(json.dumps({
                    'all_local_streams_frozen': True, 'samples_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                    'protocol_sha256': 'pinned', 'model': 'test', 'seed': 1}))
            write(rows[:-1])
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                freeze(root, ['test'], [1], ['HumanEval/0'], root / 'out', root / 'receipt', 'pinned')
            write(rows + [rows[0]])
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                freeze(root, ['test'], [1], ['HumanEval/0'], root / 'out', root / 'receipt', 'pinned')
            write(rows)
            report = freeze(root, ['test'], [1], ['HumanEval/0'], root / 'out', root / 'receipt', 'pinned')
            self.assertTrue(report['all_streams_frozen'])
            self.assertEqual(report['missing_solutions'], 4)


class AnalysisTests(unittest.TestCase):
    def test_ordered_streams_and_failures_keep_the_planned_denominator(self):
        from humaneval_analyze import summarize
        from humaneval_freeze import CONDITIONS
        samples, grades = [], []
        for seed in (1, 2):
            for task in ('HumanEval/0', 'HumanEval/1', 'HumanEval/2'):
                for condition in CONDITIONS:
                    row = {'model': 'test', 'seed': seed, 'task_id': task, 'condition': condition,
                           'solution': 'def fixture(): return 0',
                           'selection_sha256': hashlib.sha256(b'def fixture(): return 0').hexdigest(),
                           'error': 'earlier stage warning',
                           'calls': 1, 'seconds': 0.1, 'tokens': 10, 'prompt_tokens': 20}
                    samples.append(row)
                    passed = condition == 'guarded' and (seed == 1 or task == 'HumanEval/0')
                    grades.append({**{k: row[k] for k in ('model','seed','task_id','condition','selection_sha256')},
                                   'passed': passed, 'status': 'graded' if passed else 'evaluator_error'})
        report = summarize(samples, grades, ['HumanEval/0','HumanEval/1','HumanEval/2'])
        guarded = next(r for r in report['summaries'] if r['condition'] == 'guarded')
        self.assertEqual(guarded['planned'], 6)
        self.assertEqual(guarded['passed'], 4)
        comparison = next(r for r in report['paired_stream_comparisons'] if r['reference'] == 'original')
        self.assertAlmostEqual(comparison['mean_difference'], 2/3)
        self.assertEqual(len(comparison['paired_streams']), 2)
        self.assertNotIn('p_value', comparison)
        self.assertIsNotNone(comparison['sample_sd'])
        with self.assertRaisesRegex(ValueError, 'complete intended population'):
            summarize(samples, grades[:-1], ['HumanEval/0','HumanEval/1','HumanEval/2'])


class StreamArchiveTests(unittest.TestCase):
    """Release amendment 3: one verified archive per stream replaces the per-call file tree."""

    def test_pack_stores_every_entry_and_removes_the_tree(self):
        import tarfile
        from humaneval_generate import pack
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / 'local' / 'selected-m-1'
            (stream / 'raw').mkdir(parents=True)
            for i in range(5):
                (stream / 'raw' / f'{i:06d}.json').write_text(json.dumps({'index': i}))
            (stream / 'guarded' / 'library').mkdir(parents=True)
            archive = Path(tmp) / 'selected-m-1.stream.tar.gz'
            stored = pack(stream, archive)
            self.assertFalse(stream.exists())
            self.assertEqual(stored['entries'], 9)
            self.assertEqual(stored['sha256'], hashlib.sha256(archive.read_bytes()).hexdigest())
            with tarfile.open(archive) as tar:
                self.assertIn('selected-m-1/raw/000004.json', tar.getnames())
            self.assertEqual(list(Path(tmp).glob('*.part')), [])


if __name__ == '__main__':
    unittest.main()

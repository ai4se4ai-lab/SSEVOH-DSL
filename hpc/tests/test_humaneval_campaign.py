"""Qualification ownership invariants for the thin native-Slurm coordinator."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import humaneval_campaign as campaign


class CodingOwnershipTests(unittest.TestCase):
    def observations(self):
        return [{'site': site, 'trial': trial, 'eligible': True,
                 'score_seconds': cost, 'gpu_job_seconds': {'small': cost / 2, 'large': cost}}
                for site, cost in [('fir', 100), ('narval', 300), ('rorqual', 150)]
                for trial in (1, 2, 3)]

    def test_three_trials_and_two_qualified_sites_are_required(self):
        protocol = {'models': ['small', 'large'], 'seeds': [1, 2, 3]}
        with patch.object(campaign, 'sha', return_value='pinned'):
            self.assertIsNone(campaign.build_plan([r for r in self.observations() if r['trial'] != 3], protocol))
            self.assertIsNone(campaign.build_plan([r for r in self.observations() if r['site'] == 'fir'], protocol))

    def test_whole_streams_have_unique_owners_on_fastest_qualified_sites(self):
        protocol = {'models': ['small', 'large'], 'seeds': [1, 2, 3]}
        with patch.object(campaign, 'sha', return_value='pinned'):
            plan = campaign.build_plan(self.observations(), protocol)
        rows = plan['ownership']
        self.assertEqual(len(rows), 6)
        self.assertEqual({(r['model'], r['seed']) for r in rows}, {(m,s) for m in protocol['models'] for s in protocol['seeds']})
        self.assertEqual({r['site'] for r in rows}, {'fir', 'rorqual'})
        self.assertEqual(plan['primary'], 'fir')
        self.assertTrue(all(r['predicted_seconds'] > 0 for r in rows))



class RecoveryAndSupplementTests(unittest.TestCase):
    """Release amendment 3: failed owners keep their completed streams; supplements own only failed cells."""

    def setUp(self):
        import hashlib, json, tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.protocol = self.root / 'protocol.json'
        self.protocol.write_text('{}')
        self.patches = [patch.object(campaign, 'ROOT', self.root), patch.object(campaign, 'PROTOCOL', self.protocol),
                        patch.object(campaign, 'save', lambda state: None)]
        for p in self.patches:
            p.start()
        self.json, self.hashlib = json, hashlib
        cells = [{'model': 'm', 'seed': s} for s in (1, 2, 3)]
        self.state = {'plan': {'ownership': [{'site': 'a', **c} for c in cells] + [{'site': 'b', 'model': 'n', 'seed': 1}]},
                      'full_runs': [{'site': 'a', 'run_id': 'gen-a', 'kind': 'full-generation', 'cells': cells},
                                    {'site': 'b', 'run_id': 'gen-b', 'kind': 'full-generation',
                                     'cells': [{'model': 'n', 'seed': 1}]}]}

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def stream(self, folder, model, seed, **overrides):
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f'selected-{model}-{seed}.jsonl'
        path.write_text('{"task_id": "HumanEval/0"}\n')
        receipt = {'all_local_streams_frozen': True, 'samples_sha256': self.hashlib.sha256(path.read_bytes()).hexdigest(),
                   'protocol_sha256': campaign.sha(self.protocol), 'fully_gpu': True, 'failed_calls': 0,
                   'model': model, 'seed': seed, **overrides}
        path.with_suffix('.freeze.json').write_text(self.json.dumps(receipt))

    def test_recovery_records_completed_and_failed_cells(self):
        folder = self.root / 'recovered'
        self.stream(folder, 'm', 1)
        self.stream(folder, 'm', 2)
        failed = campaign.recover(self.state, 'gen-a', folder, 'archive.tar.gz', 'abc', 'quota')
        self.assertEqual(failed, [{'model': 'm', 'seed': 3}])
        self.assertEqual(self.state['recovered']['gen-a']['cells'], [{'model': 'm', 'seed': 1}, {'model': 'm', 'seed': 2}])

    def test_recovery_rejects_streams_that_differ_from_their_receipt(self):
        folder = self.root / 'recovered'
        self.stream(folder, 'm', 1, samples_sha256='0' * 64)
        with self.assertRaises(ValueError):
            campaign.recover(self.state, 'gen-a', folder, 'archive.tar.gz', 'abc', 'quota')

    def test_recovery_rejects_unowned_and_failed_client_streams(self):
        folder = self.root / 'recovered'
        self.stream(folder, 'n', 1)
        with self.assertRaises(ValueError):
            campaign.recover(self.state, 'gen-a', folder, 'archive.tar.gz', 'abc', 'quota')
        other = self.root / 'other'
        self.stream(other, 'm', 1, failed_calls=2)
        with self.assertRaises(ValueError):
            campaign.recover(self.state, 'gen-a', other, 'archive.tar.gz', 'abc', 'quota')

    def test_supplement_only_for_recorded_failed_cell_at_same_site(self):
        folder = self.root / 'recovered'
        self.stream(folder, 'm', 1)
        self.stream(folder, 'm', 2)
        campaign.recover(self.state, 'gen-a', folder, 'archive.tar.gz', 'abc', 'quota')
        for site, seed in (('a', 1), ('b', 3)):
            with self.assertRaises(ValueError):
                campaign.add_supplement(self.state, {}, site, 'm', seed, 'gen-a')

    def test_sources_partition_planned_cells_and_wait_for_pending_runs(self):
        folder = self.root / 'recovered'
        self.stream(folder, 'm', 1)
        self.stream(folder, 'm', 2)
        campaign.recover(self.state, 'gen-a', folder, 'archive.tar.gz', 'abc', 'quota')
        self.state['recovered']['gen-b'] = {'cells': [{'model': 'n', 'seed': 1}], 'folder': 'recovered-b'}
        with self.assertRaises(ValueError):  # seed 3 has no owner yet
            campaign.generation_sources(self.state)
        supplement = {'site': 'a', 'run_id': 'sup-a', 'kind': 'full-generation-supplement',
                      'cells': [{'model': 'm', 'seed': 3}], 'supersedes': 'gen-a'}
        self.state['full_runs'].append(supplement)
        with patch.object(campaign, 'complete', return_value=False):
            self.assertIsNone(campaign.generation_sources(self.state))
        run = self.root / 'hpc/fetched/a/sup-a'
        run.mkdir(parents=True)
        (run / 'transfer.json').write_text('{"verified": true}')
        with patch.object(campaign, 'complete', return_value=True):
            sources = campaign.generation_sources(self.state)
        self.assertEqual(sorted(c for s in sources for c in s['cells']), [('m', 1), ('m', 2), ('m', 3), ('n', 1)])
        self.state['full_runs'].append({**supplement, 'run_id': 'sup-dup'})
        (self.root / 'hpc/fetched/a/sup-dup').mkdir(parents=True)
        (self.root / 'hpc/fetched/a/sup-dup/transfer.json').write_text('{"verified": true}')
        with patch.object(campaign, 'complete', return_value=True), self.assertRaises(ValueError):
            campaign.generation_sources(self.state)


if __name__ == '__main__':
    unittest.main()

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


if __name__ == '__main__':
    unittest.main()

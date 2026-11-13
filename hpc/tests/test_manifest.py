"""Source provenance must be independent of mutable job outputs."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from manifest import snapshot_hashes


class ManifestTests(unittest.TestCase):
    def test_only_frozen_source_affects_content_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            run = root / 'hpc/logs/run'
            (run / 'source/hpc/scripts').mkdir(parents=True)
            (run / 'source/hpc/scripts/code.py').write_text('pass\n')
            before = snapshot_hashes(run, ['hpc'])
            (run / 'changing-results.json').write_text('first output')
            self.assertEqual(before, snapshot_hashes(run, ['hpc']))
            (run / 'changing-results.json').write_text('different output')
            self.assertEqual(before, snapshot_hashes(run, ['hpc']))
            (run / 'source/hpc/scripts/code.py').write_text('raise RuntimeError()\n')
            self.assertNotEqual(before, snapshot_hashes(run, ['hpc']))

    def test_missing_snapshot_and_path_escape_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(ValueError):
                snapshot_hashes(root, ['hpc'])
            (root / 'source').mkdir()
            for name in ('../hpc', '/etc'):
                with self.assertRaises(ValueError):
                    snapshot_hashes(root, [name])


if __name__ == '__main__':
    unittest.main()

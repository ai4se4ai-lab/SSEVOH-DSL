"""Cold-start preparation must remain GPU-only and never evaluate a prompt."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'experiments/scripts'))
from gpu_bootstrap import enumerate_backends


class BootstrapTests(unittest.TestCase):
    def fixture(self, root):
        base = root / 'lib/ollama'
        (base / 'cuda_v12').mkdir(parents=True)
        (base / 'llama-server').write_bytes(b'trusted-fixture')
        (base / 'cuda_v12/libggml-cuda.so').write_bytes(b'backend-fixture')

    def test_device_probe_is_offline_and_has_no_model_or_prompt(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'SLURM_JOB_ID': 'test', 'CUDA_VISIBLE_DEVICES': '0'}):
            root = Path(folder)
            self.fixture(root)
            def runner(command, **kwargs):
                self.assertEqual(command[1:], ['--list-devices', '--offline', '--verbose'])
                self.assertIn('cuda_v12', kwargs['env']['GGML_BACKEND_PATH'])
                self.assertEqual(kwargs['timeout'], 180)
                return subprocess.CompletedProcess(command, 0, 'CUDA0: NVIDIA fixture', '')
            report = enumerate_backends(root, runner)
            self.assertTrue(report['passed'])
            self.assertFalse(report['model_loaded'])
            self.assertFalse(report['task_prompt_evaluated'])

    def test_cpu_only_discovery_and_missing_allocation_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            with patch.dict(os.environ, {'SLURM_JOB_ID': 'test', 'CUDA_VISIBLE_DEVICES': '0'}):
                report = enumerate_backends(root, lambda command, **kwargs: subprocess.CompletedProcess(command, 0, 'Available devices: none', ''))
                self.assertFalse(report['passed'])
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(RuntimeError):
                    enumerate_backends(root)


if __name__ == '__main__':
    unittest.main()

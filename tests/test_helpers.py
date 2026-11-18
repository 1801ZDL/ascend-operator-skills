"""Small offline behavior checks; no framework, Docker, profiler or device access."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TIMINGS = ROOT/'skills/ascend-benchmark/scripts/summarize_timings.py'
IDENTITY = ROOT/'skills/ascend-environment/scripts/capture_identity.py'


class TimingChecks(unittest.TestCase):
    def run_summary(self, body, *extra):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'samples.csv'
            path.write_text(body)
            return subprocess.run([
                sys.executable, str(TIMINGS), str(path), '--value-column', 'time',
                '--unit', 'us', '--kind', 'hardware', '--window', 'kernel-event', *extra,
            ], text=True, capture_output=True, timeout=5)

    def test_selection_ratios_and_long_tail_retained(self):
        p = self.run_summary(
            'variant,round,phase,time\nbase,1,warmup,0\nnew,1,warmup,0\n'
            'base,1,timed,10\nbase,1,timed,12\nnew,1,timed,5\nnew,1,timed,100\n',
            '--round-column', 'round', '--phase-column', 'phase', '--phase', 'timed',
            '--reference', 'base')
        self.assertEqual(p.returncode, 0, p.stderr)
        d = json.loads(p.stdout)
        self.assertEqual(d['selection']['included'], 4)
        self.assertEqual(d['selection']['excluded_by_explicit_phase'], 2)
        group = next(x for x in d['groups'] if x['variant']=='new')
        self.assertEqual(group['maximum'], 100)
        self.assertEqual(group['median'], 52.5)
        self.assertAlmostEqual(d['comparisons'][0]['median_speedup'], 11/52.5)
        self.assertLess(d['comparisons'][0]['median_time_reduction_percent'], 0)

    def test_invalid_timings_rejected(self):
        for value in ['nan', 'inf', '0', '-1', 'not-a-number']:
            with self.subTest(value=value):
                p = self.run_summary('variant,time\nbase,'+value+'\n')
                self.assertEqual(p.returncode, 2)
                self.assertEqual(p.stdout, '')

    def test_phase_and_row_limits_are_explicit(self):
        for opts in [('--phase', 'timed'), ('--max-rows', '1'), ('--max-bytes', '4')]:
            with self.subTest(opts=opts):
                p = self.run_summary('variant,time\nbase,1\nbase,2\n', *opts)
                self.assertEqual(p.returncode, 2)

    def test_rounds_not_pooled_and_incomplete_reference_is_visible(self):
        p = self.run_summary('variant,round,time\nbase,1,10\nnew,1,5\nnew,2,2\n',
                             '--round-column', 'round', '--reference', 'base')
        self.assertEqual(p.returncode, 0, p.stderr)
        d = json.loads(p.stdout)
        self.assertEqual(len(d['groups']), 3)
        self.assertEqual(d['comparisons'][1]['state'], 'missing_reference_in_round')

    def test_unequal_counts_do_not_claim_comparability(self):
        p = self.run_summary('variant,time\nbase,10\nbase,12\nnew,5\n', '--reference', 'base')
        self.assertEqual(p.returncode, 0, p.stderr)
        row = json.loads(p.stdout)['comparisons'][0]
        self.assertFalse(row['same_sample_count'])
        self.assertEqual(row['measurement_comparability'], 'not_checked')

    def test_missing_reference_and_duplicate_headers_rejected(self):
        for body, opts in [('variant,time\nnew,5\n', ('--reference', 'base')),
                           ('variant,time,time\nnew,5,6\n', ())]:
            with self.subTest(body=body):
                self.assertEqual(self.run_summary(body, *opts).returncode, 2)


class IdentityChecks(unittest.TestCase):
    def test_identity_hash_with_framework_imports_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'kernel.py'
            source.write_bytes(b'abc\n')
            # A fresh interpreter refuses any accidental device framework import.
            bootstrap = '''import sys,runpy
class Deny:
 def find_spec(self, fullname, path=None, target=None):
  if fullname.split('.')[0] in {'torch','torch_npu','triton'}:
   raise RuntimeError('Unexpected framework import: '+fullname)
sys.meta_path.insert(0,Deny())
sys.argv=[sys.argv[1],*sys.argv[2:]]
runpy.run_path(sys.argv[0],run_name='__main__')
'''
            p = subprocess.run([sys.executable, '-c', bootstrap, str(IDENTITY),
                                '--file', 'source='+str(source), '--distribution',
                                'ascend-skill-test-distribution-that-does-not-exist'],
                               text=True, capture_output=True, timeout=5)
            self.assertEqual(p.returncode, 0, p.stderr)
            d = json.loads(p.stdout)
            self.assertEqual(d['files'][0]['sha256'], hashlib.sha256(b'abc\n').hexdigest())
            self.assertEqual(d['files'][0]['bytes'], 4)
            self.assertEqual(d['distributions'][0]['status'], 'not_installed_in_this_interpreter')

    def test_duplicate_file_labels_rejected(self):
        p = subprocess.run([sys.executable, str(IDENTITY), '--file', 'a='+str(IDENTITY),
                            '--file', 'a='+str(IDENTITY)], text=True, capture_output=True, timeout=5)
        self.assertEqual(p.returncode, 2)
        self.assertEqual(p.stdout, '')


if __name__ == '__main__':
    unittest.main()

"""Exercise complete installations in temporary directories only, without network."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ascend_installer', ROOT/'install.py')
INSTALL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALL)
from bundle import MARKER, inventory, manifest_text, skills


class InstallerChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ascend-install-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base/'source'
        shutil.copytree(ROOT, self.source, ignore=shutil.ignore_patterns(
            '.git', '__pycache__', '*.pyc', '.pytest_cache', '.venv', 'dist', 'build', '.local'))
        self.target = self.base/'installed'
        self.names = skills(self.source)

    def call(self, *opts):
        return subprocess.run([sys.executable, str(self.source/'install.py'),
                               '--target', str(self.target), *opts], text=True,
                              capture_output=True, timeout=10)

    def success(self, *opts):
        p = self.call(*opts)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def refresh_source(self):
        (self.source/'MANIFEST.sha256').write_text(manifest_text(self.source), encoding='utf-8')

    def options(self, **overrides):
        values = dict(agent=None, target=str(self.target), dry_run=False,
                      upgrade=False, check=False, uninstall=False)
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_dry_run_does_not_create_destination(self):
        result = self.success('--dry-run')
        self.assertEqual(len(result['skills']), 7)
        self.assertFalse(self.target.exists())
        p = self.call('--check')
        self.assertEqual(p.returncode, 2)
        self.assertFalse(self.target.exists())

    def test_install_check_repeat_and_packaged_tools(self):
        result = self.success()
        self.assertTrue(all(r['action'] == 'install' for r in result['skills']))
        self.success('--check')
        again = self.success()
        self.assertTrue(all(r['action'] == 'unchanged' for r in again['skills']))
        for name in self.names:
            record = json.loads((self.target/name/MARKER).read_text())
            self.assertEqual(record['package_id'], 'ascend-operator-skills')
            self.assertEqual((self.target/name/'BUNDLE-LICENSE.txt').read_bytes(),
                             (self.source/'LICENSE').read_bytes())
        p = subprocess.run([sys.executable,
                            str(self.target/'ascend-knowledge/scripts/kg_query.py'),
                            'search', '--query', '公开查询', '--dry-run'],
                           text=True, capture_output=True, timeout=5)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)['status'], 'request_preview')

    def test_unmanaged_conflict_is_preserved_before_any_write(self):
        existing = self.target/self.names[-1]
        existing.mkdir(parents=True)
        (existing/'custom.txt').write_text('keep')
        before = inventory(self.target)
        for opts in [(), ('--upgrade',), ('--uninstall',)]:
            p = self.call(*opts)
            self.assertEqual(p.returncode, 2)
            self.assertEqual(inventory(self.target), before)

    def test_local_edits_are_preserved(self):
        self.success()
        changed = self.target/self.names[0]/'SKILL.md'
        changed.write_bytes(changed.read_bytes()+b'\nLocal user change\n')
        before = inventory(self.target)
        for opts in [('--check',), ('--upgrade',), ('--uninstall',)]:
            p = self.call(*opts)
            self.assertEqual(p.returncode, 2)
            self.assertIn('local changes', p.stderr)
            self.assertEqual(inventory(self.target), before)

    def test_upgrade_keeps_backup_and_unrelated_files(self):
        self.success()
        unrelated = self.target/'unrelated-skill'
        unrelated.mkdir()
        (unrelated/'data').write_text('keep')
        rules = self.base/'AGENTS.md'
        rules.write_text('existing global rule')
        original = (self.target/self.names[0]/'SKILL.md').read_bytes()
        updated = self.source/'skills'/self.names[0]/'SKILL.md'
        updated.write_bytes(updated.read_bytes()+b'\nNew release explanation\n')
        self.refresh_source()
        self.assertEqual(self.call().returncode, 2)
        preview = self.success('--upgrade', '--dry-run')
        self.assertEqual((self.target/self.names[0]/'SKILL.md').read_bytes(), original)
        self.assertTrue(any(r['action'] == 'upgrade' for r in preview['skills']))
        result = self.success('--upgrade')
        self.assertEqual((Path(result['backup'])/self.names[0]/'SKILL.md').read_bytes(), original)
        self.assertEqual((self.target/self.names[0]/'SKILL.md').read_bytes(), updated.read_bytes())
        self.assertEqual((unrelated/'data').read_text(), 'keep')
        self.assertEqual(rules.read_text(), 'existing global rule')
        self.success('--check')

    def test_uninstall_keeps_owned_backups_and_other_skills(self):
        self.success()
        other = self.target/'other'
        other.mkdir()
        (other/'keep').write_text('other')
        self.success('--uninstall', '--dry-run')
        self.assertTrue((self.target/self.names[0]).exists())
        result = self.success('--uninstall')
        for name in self.names:
            self.assertFalse((self.target/name).exists())
            self.assertTrue((Path(result['backup'])/name/MARKER).is_file())
        self.assertEqual((other/'keep').read_text(), 'other')
        self.success('--uninstall')

    def test_tampered_source_rejected_before_target_creation(self):
        file = self.source/'skills'/self.names[0]/'SKILL.md'
        file.write_bytes(file.read_bytes()+b'\nTamper\n')
        p = self.call()
        self.assertEqual(p.returncode, 2)
        self.assertIn('checksum mismatch', p.stderr)
        self.assertFalse(self.target.exists())

    def test_installer_does_not_follow_existing_skill_symlink(self):
        outside = self.base/'outside'
        outside.mkdir()
        self.target.mkdir()
        try:
            (self.target/self.names[0]).symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('Host does not permit symlink creation')
        p = self.call('--upgrade')
        self.assertEqual(p.returncode, 2)
        self.assertEqual(list(outside.iterdir()), [])

    def test_partial_new_install_failure_rolls_back(self):
        rows = INSTALL.prepare(self.source, self.target, self.options())
        rename = Path.rename
        def fail_second(path, dest):
            if path.parent.name.startswith('.ascend-skills-stage-') and path.name == self.names[1]:
                raise OSError('injected second install failure')
            return rename(path, dest)
        with mock.patch.object(Path, 'rename', fail_second):
            with self.assertRaisesRegex(OSError, 'injected'):
                INSTALL.apply(self.source, self.target, rows)
        self.assertFalse(any((self.target/name).exists() for name in self.names))
        self.assertFalse((self.target/'.ascend-operator-skills.lock').exists())

    def test_upgrade_failure_restores_previous_installed_content(self):
        self.success()
        before = {name: inventory(self.target/name) for name in self.names}
        for name in self.names[:2]:
            path = self.source/'skills'/name/'SKILL.md'
            path.write_bytes(path.read_bytes()+b'\nRelease change\n')
        self.refresh_source()
        rows = INSTALL.prepare(self.source, self.target, self.options(upgrade=True))
        rename = Path.rename
        def fail_second(path, dest):
            if path.parent.name.startswith('.ascend-skills-stage-') and path.name == self.names[1]:
                raise OSError('injected upgrade failure')
            return rename(path, dest)
        with mock.patch.object(Path, 'rename', fail_second):
            with self.assertRaisesRegex(OSError, 'injected'):
                INSTALL.apply(self.source, self.target, rows)
        self.assertEqual({name: inventory(self.target/name) for name in self.names}, before)
        self.assertFalse((self.target/'.ascend-operator-skills.lock').exists())

    def test_platform_presets_and_explicit_target(self):
        with mock.patch.object(Path, 'home', return_value=self.base), \
                mock.patch.dict(INSTALL.os.environ, {'XDG_CONFIG_HOME': str(self.base/'xdg')}):
            self.assertEqual(INSTALL.destination(self.options(agent='codex', target=None)),
                             self.base/'.agents/skills')
            self.assertEqual(INSTALL.destination(self.options(agent='claude', target=None)),
                             self.base/'.claude/skills')
            self.assertEqual(INSTALL.destination(self.options(agent='opencode', target=None)),
                             self.base/'xdg/opencode/skills')
            self.assertEqual(INSTALL.destination(self.options(agent='codex')), self.target)

    def test_busy_lock_is_not_removed_or_bypassed(self):
        self.target.mkdir()
        lock = self.target/'.ascend-operator-skills.lock'
        lock.write_text('another installer')
        p = self.call()
        self.assertEqual(p.returncode, 2)
        self.assertEqual(lock.read_text(), 'another installer')
        self.assertFalse(any((self.target/name).exists() for name in self.names))

    def test_new_release_version_requires_explicit_upgrade(self):
        self.success()
        (self.source/'VERSION').write_text('0.4.0\n')
        self.refresh_source()
        self.assertEqual(self.call('--check').returncode, 2)
        self.assertEqual(self.call().returncode, 2)
        self.success('--upgrade')
        self.success('--check')
        for name in self.names:
            record = json.loads((self.target/name/MARKER).read_text())
            self.assertEqual(record['version'], '0.4.0')


if __name__ == '__main__':
    unittest.main()

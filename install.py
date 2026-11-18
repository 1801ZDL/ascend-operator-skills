#!/usr/bin/env python3
"""Install, check or remove the complete skill bundle. No network or SDK install."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'scripts'))
from bundle import MARKER, PACKAGE_ID, digest, inventory, skills, verify_manifest


def destination(args):
    if args.target:
        return Path(args.target).expanduser().absolute()
    base = Path.home()
    if args.agent == 'codex':
        return base/'.agents/skills'
    if args.agent == 'claude':
        return base/'.claude/skills'
    if args.agent == 'opencode':
        return Path(os.environ.get('XDG_CONFIG_HOME') or base/'.config')/'opencode/skills'
    raise ValueError('Choose --agent codex|claude|opencode or supply --target PATH')


def read_owned(path):
    if path.is_symlink() or not path.is_dir():
        raise ValueError('Existing entry is not an owned directory: '+path.name)
    marker = path/MARKER
    if marker.is_symlink() or not marker.is_file():
        raise ValueError('Existing entry is not managed by this installer: '+path.name)
    record = json.loads(marker.read_text(encoding='utf-8'))
    if not isinstance(record, dict) or record.get('package_id') != PACKAGE_ID or \
            record.get('schema_version') != 1 or record.get('skill') != path.name:
        raise ValueError('Invalid ownership record: '+path.name)
    actual = inventory(path)
    actual.pop(MARKER, None)
    if actual != record.get('files'):
        raise ValueError('Installed content has local changes; preserve/reconcile first: '+path.name)
    return record


def prepare(root, target, args):
    verify_manifest(root)
    names = skills(root)
    version = (root/'VERSION').read_text(encoding='utf-8').strip()
    # Resolve aliases before deciding overlap, but never follow a skill symlink for replacement.
    resolved = target.resolve()
    if resolved == root.resolve() or root.resolve() in resolved.parents or \
            resolved == (root/'skills').resolve():
        raise ValueError('Install target must be outside this source repository')
    if target.exists() and not target.is_dir():
        raise ValueError('Install target is not a directory')
    if args.uninstall and args.upgrade:
        raise ValueError('--uninstall and --upgrade cannot be combined')
    if args.check and (args.uninstall or args.upgrade):
        raise ValueError('--check cannot be combined with --uninstall or --upgrade')
    rows = []
    for name in names:
        dest = target/name
        exists = dest.exists() or dest.is_symlink()
        source_files = inventory(root/'skills'/name)
        # License travels with each independently installed skill directory.
        source_files['BUNDLE-LICENSE.txt'] = digest(root/'LICENSE')
        if exists:
            owned = read_owned(dest)
            same = owned.get('files') == source_files and owned.get('version') == version
            if args.uninstall:
                action = 'remove_to_backup'
            elif same:
                action = 'unchanged'
            elif args.upgrade:
                action = 'upgrade'
            else:
                raise ValueError('Managed skill differs; use --upgrade after review: '+name)
        else:
            action = 'missing' if args.check else ('absent' if args.uninstall else 'install')
        rows.append({'skill': name, 'action': action, 'files': source_files})
    return rows


def apply(root, target, rows):
    changes = [r for r in rows if r['action'] in {'install', 'upgrade', 'remove_to_backup'}]
    if not changes:
        return None
    target.mkdir(parents=True, exist_ok=True)
    lock = target/'.ascend-operator-skills.lock'
    # Exclusive create prevents two installers from mutating the same target concurrently.
    fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    stage = None
    backup = None
    journal = []
    try:
        stage = Path(tempfile.mkdtemp(prefix='.ascend-skills-stage-', dir=str(target)))
        for row in changes:
            if row['action'] == 'remove_to_backup':
                continue
            name = row['skill']
            shutil.copytree(root/'skills'/name, stage/name,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo'))
            shutil.copyfile(root/'LICENSE', stage/name/'BUNDLE-LICENSE.txt')
            if inventory(stage/name) != row['files']:
                raise ValueError('Source changed while copying: '+name)
            record = {'schema_version': 1, 'package_id': PACKAGE_ID, 'skill': name,
                      'version': (root/'VERSION').read_text(encoding='utf-8').strip(),
                      'bundle_manifest_sha256': digest(root/'MANIFEST.sha256'), 'files': row['files']}
            (stage/name/MARKER).write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
        for row in changes:
            name = row['skill']
            dest = target/name
            # Recheck under the installer lock before mutation.
            if row['action'] == 'install':
                if dest.exists() or dest.is_symlink():
                    raise ValueError('Destination appeared during install: '+name)
            else:
                read_owned(dest)
                if backup is None:
                    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
                    backup = target/'.ascend-operator-skills-backups'/stamp
                    backup.mkdir(parents=True)
                dest.rename(backup/name)
            entry = {'name': name, 'old': row['action'] != 'install', 'new': False}
            journal.append(entry)
            if row['action'] != 'remove_to_backup':
                (stage/name).rename(dest)
                entry['new'] = True
    except BaseException:
        # Restore earlier entries if a later copy/rename fails. A hard process kill or
        # power loss cannot run this handler; retained backups remain recoverable.
        for entry in reversed(journal):
            dest = target/entry['name']
            if entry['new']:
                shutil.rmtree(dest)
            if entry['old']:
                (backup/entry['name']).rename(dest)
        raise
    finally:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)
        lock.unlink()
    return str(backup) if backup else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent', choices=('codex', 'claude', 'opencode'))
    parser.add_argument('--target', help='exact skills directory; overrides the agent preset')
    parser.add_argument('--dry-run', action='store_true', help='validate and preview without writes')
    parser.add_argument('--upgrade', action='store_true', help='upgrade unchanged managed skills, keeping backups')
    parser.add_argument('--check', action='store_true', help='read-only installed content check')
    parser.add_argument('--uninstall', action='store_true', help='move unchanged owned skills to retained backups')
    args = parser.parse_args(argv)
    try:
        target = destination(args)
        rows = prepare(ROOT, target, args)
        backup = None if args.dry_run or args.check else apply(ROOT, target, rows)
        missing = [r['skill'] for r in rows if r['action'] == 'missing']
        differs = [r['skill'] for r in rows if r['action'] == 'upgrade']
        result = {'package': PACKAGE_ID, 'version': (ROOT/'VERSION').read_text().strip(),
                  'target': str(target), 'dry_run': args.dry_run, 'check': args.check,
                  'skills': [{'skill': r['skill'], 'action': r['action']} for r in rows],
                  'backup': backup,
                  'activation': 'Files installed; verify discovery in the target Agent. Refresh or start a new session if needed.',
                  'runtime': 'No SDK/compiler/NPU/model installed or started. KG needs an optional user-provided API key.'}
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 2 if args.check and (missing or differs) else 0
    except (OSError, ValueError) as exc:
        print('Install error: '+str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

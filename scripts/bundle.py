"""Shared offline bundle inventory and checksum helpers (Python 3.8+)."""
import hashlib
import os
from pathlib import Path, PurePosixPath
import re

PACKAGE_ID = 'ascend-operator-skills'
MARKER = '.ascend-operator-skills.json'
SKIP_DIRS = {'.git', '__pycache__', '.pytest_cache', '.venv', 'dist', 'build', '.local'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root):
    result = {}
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in dirs+sorted(files):
            path = Path(current)/name
            rel = path.relative_to(root)
            if path.is_symlink():
                raise ValueError('Bundle must not contain symbolic links: '+rel.as_posix())
            if path.is_file() and path.suffix not in {'.pyc', '.pyo'}:
                result[rel.as_posix()] = digest(path)
    return dict(sorted(result.items()))


def manifest_text(root):
    return ''.join(value+'  '+name+'\n' for name, value in inventory(root).items()
                   if name != 'MANIFEST.sha256')


def verify_manifest(root):
    expected = {}
    for line in (root/'MANIFEST.sha256').read_text(encoding='utf-8').splitlines():
        value, sep, name = line.partition('  ')
        rel = PurePosixPath(name)
        if not sep or not re.fullmatch(r'[a-f0-9]{64}', value) or not name or \
                rel.is_absolute() or '..' in rel.parts or '\\' in name or name in expected:
            raise ValueError('Invalid or duplicate checksum entry')
        expected[name] = value
    current = inventory(root)
    current.pop('MANIFEST.sha256', None)
    if current != expected:
        changed = sorted(name for name in set(current) | set(expected)
                         if current.get(name) != expected.get(name))
        raise ValueError('Bundle checksum mismatch: '+', '.join(changed))
    return expected


def skills(root):
    result = []
    for path in sorted((root/'skills').iterdir()):
        if path.name in SKIP_DIRS:
            continue
        if not path.is_dir() or path.is_symlink():
            raise ValueError('Unexpected skill entry: '+path.name)
        text = (path/'SKILL.md').read_text(encoding='utf-8')
        match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)', text, re.S)
        if not match or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', path.name):
            raise ValueError('Invalid skill folder/frontmatter: '+path.name)
        fields = {}
        for line in match.group(1).splitlines():
            key, sep, value = line.partition(':')
            if sep:
                fields[key] = value.strip().strip('"\'')
        if fields.get('name') != path.name or not fields.get('description'):
            raise ValueError('Missing or mismatched skill metadata: '+path.name)
        inventory(path)
        result.append(path.name)
    if not result:
        raise ValueError('No skills found')
    return result

#!/usr/bin/env python3
"""Validate this repository offline; optionally regenerate intentional source hashes."""
import argparse
import ast
import json
from pathlib import Path
import re
import sys

from bundle import inventory, manifest_text, skills, verify_manifest

ROOT = Path(__file__).resolve().parents[1]


def validate(root, write_manifest=False):
    files = inventory(root)
    names = skills(root)
    version = (root/'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('VERSION must contain major.minor.patch')
    links = 0
    python_files = 0
    for name in files:
        path = root/name
        if path.name == '.env' or (path.name.startswith('.env.') and path.name != '.env.example'):
            raise ValueError('Personal environment files must not enter a release: '+name)
        if path.name == '.ascend-operator-skills.json':
            raise ValueError('Installed ownership records must not enter source releases')
        if path.suffix in {'.md', '.py', '.yaml', '.json', '.yml'}:
            text = path.read_text(encoding='utf-8')
            if any(line != line.rstrip() for line in text.splitlines()):
                raise ValueError('Trailing whitespace: '+name)
        if path.suffix == '.py':
            ast.parse(text, filename=name, feature_version=(3, 8))
            python_files += 1
        if path.suffix == '.md':
            for link in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)', text):
                if '://' in link or link.startswith('#'):
                    continue
                target = (path.parent/link.split('#')[0]).resolve()
                if not target.exists() or (target != root and root not in target.parents):
                    raise ValueError('Missing or external local link: '+name+' -> '+link)
                links += 1
    if write_manifest:
        (root/'MANIFEST.sha256').write_text(manifest_text(root), encoding='utf-8')
    verified = verify_manifest(root)
    return {'status': 'passed', 'version': version, 'skills': names,
            'relative_links': links, 'python_sources': python_files,
            'manifest_entries': len(verified), 'manifest_rewritten': write_manifest,
            'scope': 'files/metadata/links/grammar/checksums; not Agent or device execution'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-manifest', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(validate(ROOT, args.write_manifest), indent=2))
    except (OSError, ValueError, SyntaxError) as exc:
        print('Validation error: '+str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())

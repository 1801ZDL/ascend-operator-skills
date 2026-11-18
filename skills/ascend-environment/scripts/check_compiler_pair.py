#!/usr/bin/env python3
"""Inspect selected NPU-IR and local LLVM build directories without running tools."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def git(path, *args):
    result = subprocess.run(
        ['git', '--no-optional-locks', '-C', str(path), *args],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=10,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def gitlink(lines, mode):
    for line in (lines or '').splitlines():
        fields = line.split('\t', 1)[0].split()
        if len(fields) != 3 or fields[0] != '160000':
            continue
        if fields[1] == 'commit' and mode == 'tree':
            return fields[2]
        if fields[2] == '0' and mode == 'index':
            return fields[1]
    return None


def inspect_build(directory, npu, expected):
    cache = {}
    cache_file = directory / 'CMakeCache.txt'
    if cache_file.is_file():
        with cache_file.open(encoding='utf-8', errors='replace') as stream:
            for line in stream:
                key_type, sep, value = line.rstrip('\n').partition('=')
                if sep and not key_type.startswith(('#', '//')):
                    cache[key_type.partition(':')[0]] = value

    source = cache.get('CMAKE_HOME_DIRECTORY')
    llvm = None
    if source:
        llvm_source = Path(source).resolve()
        if llvm_source.name == 'llvm' and (llvm_source / 'CMakeLists.txt').is_file():
            root = git(llvm_source, 'rev-parse', '--show-toplevel')
            if root and Path(root).resolve() == llvm_source.parent:
                actual = git(llvm_source, 'rev-parse', 'HEAD')
                dirty = git(llvm_source.parent, 'status', '--porcelain', '--untracked-files=normal')
                llvm = {'checkout': root, 'head': actual, 'dirty': bool(dirty) if dirty is not None else None}
    external = cache.get('LLVM_EXTERNAL_BISHENGIR_SOURCE_DIR')
    binding = 'unrecorded'
    if external:
        binding = 'same' if Path(external).resolve() == npu else 'different'
    state = 'unverified'
    if expected and llvm and llvm['head']:
        state = 'checkout-mismatch' if llvm['head'] != expected else 'matching-checkout'
        if state == 'matching-checkout' and llvm['dirty'] is not False:
            state = 'matching-checkout-with-unverified-source-state'

    tools = {}
    for name in ('llvm-config', 'llvm-tblgen', 'mlir-tblgen', 'mlir-opt', 'bishengir-opt', 'bishengir-compile'):
        tool = directory / 'bin' / name
        if tool.is_file() and os.access(tool, os.X_OK):
            tools[name] = str(tool.resolve())
    config = {}
    for package in ('LLVM', 'MLIR'):
        for lib in ('lib', 'lib64'):
            candidate = directory / lib / 'cmake' / package.lower() / (package + 'Config.cmake')
            if candidate.is_file():
                config[package] = str(candidate.resolve())
                break
    keys = ('CMAKE_BUILD_TYPE', 'LLVM_ENABLE_PROJECTS', 'LLVM_TARGETS_TO_BUILD',
            'LLVM_ENABLE_RTTI', 'LLVM_ENABLE_ASSERTIONS', 'BUILD_SHARED_LIBS',
            'BSPUB_DAVINCI_BISHENGIR', 'LLVM_BSPUB_DAVINCI_BISHENGIR',
            'CMAKE_CXX_COMPILER', 'BISHENG_COMPILER_PATH')
    return {'directory': str(directory), 'llvm_source': llvm, 'source_match': state,
            'npu_source_binding': binding, 'tools': tools, 'cmake_packages': config,
            'cache_settings': {key: cache[key] for key in keys if key in cache},
            'binary_provenance': 'not-verified'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--npu-ir', required=True, type=Path)
    parser.add_argument('--build', required=True, action='append', type=Path,
                        help='Known build directory or install prefix. Repeat in preferred order.')
    args = parser.parse_args()
    npu = args.npu_ir.resolve()
    root = git(npu, 'rev-parse', '--show-toplevel') if npu.is_dir() else None
    if not root or Path(root).resolve() != npu:
        parser.error('--npu-ir must be an NPU-IR Git checkout root')
    path = 'third-party/llvm-project'
    head = gitlink(git(npu, 'ls-tree', 'HEAD', '--', path), 'tree')
    index = gitlink(git(npu, 'ls-files', '--stage', '--', path), 'index')
    if not head and not index:
        parser.error('no LLVM gitlink found; verify this release’s dependency mechanism manually')
    result = {'npu_ir': str(npu), 'npu_head': git(npu, 'rev-parse', 'HEAD'),
              'llvm_gitlink_head': head, 'llvm_gitlink_index': index,
              'gitlinks_agree': head is not None and head == index,
              'candidates': [inspect_build(p.resolve(), npu, head if head == index else None)
                             for p in args.build]}
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()

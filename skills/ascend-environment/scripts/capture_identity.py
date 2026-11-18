#!/usr/bin/env python3
"""Offline identity evidence; no framework imports, subprocesses or device probes."""
import argparse
import datetime
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
import sys


def capture(distributions, files):
    result = {
        "schema_version": 1,
        "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "python": {
            "executable": sys.executable,
            "resolved_executable": str(Path(sys.executable).resolve()),
            "version": sys.version,
            "prefix": sys.prefix,
            "base_prefix": sys.base_prefix,
        },
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "working_directory": str(Path.cwd()),
        "distributions": [],
        "files": [],
        "scope": (
            "Reads stdlib and explicitly named distribution metadata/files only. "
            "Does not import device frameworks, run tools, inspect credentials or query devices. "
            "Interpreter startup hooks, actual module loading, ABI and device readiness are not audited."
        ),
    }
    for name in dict.fromkeys(distributions):
        try:
            dist = importlib.metadata.distribution(name)
            record = {
                "requested_name": name,
                "metadata_name": dist.metadata.get("Name"),
                "version": dist.version,
                "distribution_location": str(Path(dist.locate_file("")).resolve()),
                "actual_module_loading_verified": False,
            }
        except importlib.metadata.PackageNotFoundError:
            record = {"requested_name": name, "status": "not_installed_in_this_interpreter"}
        result["distributions"].append(record)
    labels = set()
    for item in files:
        label, sep, value = item.partition("=")
        if not sep or not label.strip() or not value.strip():
            raise ValueError("--file requires a nonempty LABEL=PATH")
        if label in labels:
            raise ValueError("Duplicate file label: " + label)
        labels.add(label)
        path = Path(value).expanduser().resolve(strict=True)
        if not path.is_file():
            raise ValueError("Not a regular file: " + str(path))
        before = path.stat()
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                size += len(block)
                digest.update(block)
        after = path.stat()
        if (before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_ino, after.st_size, after.st_mtime_ns
        ) or size != after.st_size:
            raise ValueError("File changed during hashing: " + str(path))
        result["files"].append({
            "label": label, "provided_path": value, "resolved_path": str(path),
            "bytes": size, "sha256": digest.hexdigest(),
        })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--distribution", action="append", default=[])
    parser.add_argument("--file", action="append", default=[], metavar="LABEL=PATH")
    args = parser.parse_args()
    try:
        result = capture(args.distribution, args.file)
    except (OSError, ValueError) as exc:
        parser.exit(2, str(exc) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()

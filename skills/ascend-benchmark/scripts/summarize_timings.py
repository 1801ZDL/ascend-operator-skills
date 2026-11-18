#!/usr/bin/env python3
"""Offline, explicit-column timing summary. Does not execute workloads or trim outliers."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import statistics


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def percentile(values, quantile):
    position = (len(values) - 1) * quantile
    low = math.floor(position)
    high = math.ceil(position)
    weight = position - low
    return values[low] * (1 - weight) + values[high] * weight


def summary(values):
    ordered = sorted(values)
    result = {
        "samples": len(values), "median": statistics.median(ordered),
        "mean": statistics.fmean(values), "minimum": ordered[0], "maximum": ordered[-1],
        "p10": percentile(ordered, 0.1), "p90": percentile(ordered, 0.9),
        "population_stddev": statistics.pstdev(values),
    }
    if not all(math.isfinite(x) for x in result.values()):
        raise ValueError("Non-finite summary; inspect numeric scale")
    return result


def summarize(args):
    if bool(args.phase_column) != (args.phase is not None):
        raise ValueError("--phase-column and --phase must be specified together")
    with args.csv.open("rb") as source:
        data = source.read(args.max_bytes + 1)
    if len(data) > args.max_bytes:
        raise ValueError("CSV exceeds --max-bytes; choose an explicit larger bound if appropriate")
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    headers = reader.fieldnames
    if not headers or len(headers) != len(set(headers)) or any(not x for x in headers):
        raise ValueError("CSV must have nonempty, unique headers")
    required = [args.value_column, args.variant_column]
    required.extend(x for x in (args.round_column, args.phase_column) if x)
    missing = set(required) - set(headers)
    if missing:
        raise ValueError("Missing columns: " + ", ".join(sorted(missing)))
    groups = {}
    rows = 0
    excluded = 0
    for line_number, row in enumerate(reader, 2):
        rows += 1
        if rows > args.max_rows:
            raise ValueError("CSV exceeds --max-rows")
        if None in row or any(row.get(key) is None for key in required):
            raise ValueError("Malformed CSV row " + str(line_number))
        if args.phase_column and row[args.phase_column] != args.phase:
            excluded += 1
            continue
        variant = row[args.variant_column].strip()
        round_name = row[args.round_column].strip() if args.round_column else "all"
        if not variant or not round_name:
            raise ValueError("Missing variant or round at row " + str(line_number))
        try:
            duration = float(row[args.value_column])
        except ValueError as exc:
            raise ValueError("Invalid timing at row " + str(line_number)) from exc
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Timing must be finite and positive at row " + str(line_number))
        groups.setdefault((round_name, variant), []).append(duration)
    if not groups:
        raise ValueError("No selected samples")
    if args.reference and not any(variant == args.reference for _, variant in groups):
        raise ValueError("Requested reference variant is absent")
    stats = {key: summary(values) for key, values in groups.items()}
    comparisons = []
    if args.reference:
        for (round_name, variant), candidate in sorted(stats.items()):
            if variant == args.reference:
                continue
            baseline = stats.get((round_name, args.reference))
            if baseline is None:
                comparisons.append({
                    "round": round_name, "candidate": variant, "reference": args.reference,
                    "state": "missing_reference_in_round",
                })
                continue
            speedup = baseline["median"] / candidate["median"]
            reduction = (baseline["median"] - candidate["median"]) / baseline["median"] * 100
            if not math.isfinite(speedup) or not math.isfinite(reduction):
                raise ValueError("Comparison exceeds finite numeric range")
            comparisons.append({
                "round": round_name, "candidate": variant, "reference": args.reference,
                "state": "descriptive_ratio_only", "median_speedup": speedup,
                "median_time_reduction_percent": reduction,
                "same_sample_count": baseline["samples"] == candidate["samples"],
                "measurement_comparability": "not_checked",
            })
    return {
        "schema_version": 1,
        "input": {"path": str(args.csv.resolve()), "sha256": hashlib.sha256(data).hexdigest()},
        "unit": args.unit, "measurement_kind": args.kind, "window": args.window,
        "selection": {
            "value_column": args.value_column, "variant_column": args.variant_column,
            "round_column": args.round_column, "phase_column": args.phase_column,
            "phase": args.phase, "rows": rows, "included": rows - excluded,
            "excluded_by_explicit_phase": excluded, "outlier_removal": False,
        },
        "groups": [dict(round=k[0], variant=k[1], **v) for k, v in sorted(stats.items())],
        "comparisons": comparisons,
        "qualification": (
            "Descriptive statistics only. Units/kind/window are caller-declared, not verified. "
            "Does not verify correctness, task mapping, device conditions, PMU, independence or significance. "
            "Does not pool rounds, trim samples, or execute a workload."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--value-column", required=True)
    parser.add_argument("--variant-column", default="variant")
    parser.add_argument("--round-column")
    parser.add_argument("--phase-column")
    parser.add_argument("--phase")
    parser.add_argument("--unit", choices=["ns", "us", "ms", "s", "cycles"], required=True)
    parser.add_argument("--kind", choices=["hardware", "simulation", "host"], required=True)
    parser.add_argument("--window", required=True)
    parser.add_argument("--reference")
    parser.add_argument("--max-rows", type=positive_int, default=1000000)
    parser.add_argument("--max-bytes", type=positive_int, default=64 * 1024 * 1024)
    args = parser.parse_args()
    try:
        result = summarize(args)
    except (OSError, ValueError, OverflowError, csv.Error) as exc:
        parser.exit(2, str(exc) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()

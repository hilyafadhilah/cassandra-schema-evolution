#!/usr/bin/env python3
"""
Extract LOAD/UNLOAD timings from dsbulk operation.log files.

Folder-name schemas ("cases") are pluggable — see CASES below. To add a new
case, append a Case(...) entry with a regex whose named groups become CSV
columns. The first regex that matches a folder name wins.

Layout under each matched folder:
    <case_folder>/
        logs/
            LOAD_<timestamp>/operation.log
            UNLOAD_<timestamp>/operation.log

Output: one row per paired (LOAD, UNLOAD) run, sorted by timestamp ascending.
If one side has fewer runs, the extras still appear with a blank counterpart.

Usage:
    python extract_dsbulk_times.py <root_dir> [-o output.csv] [--case NAME]
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Case definitions — add new folder-name schemas here.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Case:
    name: str            # CLI selector, e.g. "rows_cols"
    pattern: re.Pattern  # regex with named groups; groups become CSV columns
    # CSV column order for the captured fields (excludes load/unload times)
    columns: tuple[str, ...]


CASES: tuple[Case, ...] = (
    Case(
        name="p1",
        pattern=re.compile(r"^(?P<num_rows>\d+)r_(?P<num_columns>\d+)c$"),
        columns=("num_rows", "num_columns"),
    ),
    Case(
        name="pn",
        pattern=re.compile(
            r"^(?P<num_partitions>\d+)p"
            r"_(?P<num_partition_rows>\d+)pr"
            r"_(?P<num_columns>\d+)c$"
        ),
        columns=("num_partitions", "num_partition_rows", "num_columns"),
    ),
    Case(
        name="agg-p1",
        pattern=re.compile(
            r"(?P<num_rows>\d+)r"
            r"_(?P<num_columns>\d+)c"
            r"_(?P<num_agg_columns>\d+)a"
            r"_(?P<num_fields>\d+)f"
            r"_(?P<num_values>\d+)v"
            r"_(?P<agg_type>\w+)$"
        ),
        columns=(
            "num_rows",
            "num_columns",
            "num_agg_columns",
            "num_fields",
            "num_values",
            "agg_type"
        ),
    ),
    Case(
        name="agg-pn",
        pattern=re.compile(
            r"(?P<num_partitions>\d+)p"
            r"_(?P<num_partition_rows>\d+)pr"
            r"_(?P<num_columns>\d+)c"
            r"_(?P<num_agg_columns>\d+)a"
            r"_(?P<num_fields>\d+)f"
            r"_(?P<num_values>\d+)v"
            r"_(?P<agg_type>\w+)$"
        ),
        columns=(
            "num_partitions",
            "num_partition_rows",
            "num_columns",
            "num_agg_columns",
            "num_fields",
            "num_values",
            "agg_type"
        ),
    ),
    # Add new cases here. Example:
    # Case(
    #     name="my_schema",
    #     pattern=re.compile(r"^(?P<foo>\d+)f_(?P<bar>\w+)b$"),
    #     columns=("foo", "bar"),
    # ),
)


def match_case(folder_name: str, cases: tuple[Case, ...]) -> tuple[Case, dict] | None:
    """Return (case, captured_fields_as_ints_when_possible) for the first match."""
    for c in cases:
        m = c.pattern.match(folder_name)
        if m:
            fields = {k: _coerce_int(v) for k, v in m.groupdict().items()}
            return c, fields
    return None


def _coerce_int(v: str):
    return int(v) if v.isdigit() else v


# ---------------------------------------------------------------------------
# Log parsing — independent of which case matched.
# ---------------------------------------------------------------------------

# Operation folder like "LOAD_..." or "UNLOAD_..."
OP_RE = re.compile(r"^(?P<kind>LOAD|UNLOAD)_")

# The "completed successfully in ..." line. Durations look like:
#   "in 2 seconds." / "in 1 second."
#   "in 1 minute and 20 seconds." / "in 3 minutes and 5 seconds."
#   "in 1 hour, 2 minutes and 15 seconds."   (defensive: handle hours too)
COMPLETED_RE = re.compile(
    r"completed successfully in\s+(?P<dur>[^.]+)\.", re.IGNORECASE
)

#   "in less than one second."  (defensive: handle this too)
ZERO_SECOND_RE = re.compile(r"less than one second")

# Extract (number, unit) pairs from a duration phrase
UNIT_RE = re.compile(r"(\d+)\s*(hours?|minutes?|seconds?)", re.IGNORECASE)

# Stat lines inside the "Final stats:" block. dsbulk uses "reads/second" for
# UNLOAD and "writes/second" for LOAD; we accept either.
FINAL_STATS_MARKER = "Final stats:"
MEMORY_RE = re.compile(
    r"Memory usage:\s*"
    r"used:\s*(?P<used>[\d,]+)\s*MB,\s*"
    r"free:\s*(?P<free>[\d,]+)\s*MB,\s*"
    r"allocated:\s*(?P<allocated>[\d,]+)\s*MB,\s*"
    r"available:\s*(?P<available>[\d,]+)\s*MB,\s*"
    r"total gc count:\s*(?P<gc_count>[\d,]+),\s*"
    r"total gc time:\s*(?P<gc_time>[\d,]+)\s*ms"
)
THROUGHPUT_RE = re.compile(
    r"Throughput:\s*(?P<value>[\d,]+(?:\.\d+)?)\s*(?:reads|writes)/second",
    re.IGNORECASE,
)
LATENCY_RE = re.compile(
    r"Latencies:\s*"
    r"mean\s*(?P<mean>[\d.,]+)\s*"
    r",?\s*75p\s*(?P<p75>[\d.,]+)\s*"
    r",?\s*99p\s*(?P<p99>[\d.,]+)\s*"
    r",?\s*999p\s*(?P<p999>[\d.,]+)\s*"
    r"milliseconds",
    re.IGNORECASE,
)


def parse_duration_to_seconds(phrase: str) -> int | None:
    """Convert e.g. '1 minute and 20 seconds' -> 80, '2 seconds' -> 2."""
    total = 0
    found = False
    if ZERO_SECOND_RE.search(phrase):
        return 0
    for n, unit in UNIT_RE.findall(phrase):
        found = True
        n = int(n)
        u = unit.lower()
        if u.startswith("hour"):
            total += n * 3600
        elif u.startswith("minute"):
            total += n * 60
        else:
            total += n
    return total if found else None


def _num(s: str):
    """Parse '1,996' -> 1996, '74.67' -> 74.67."""
    s = s.replace(",", "")
    try:
        return int(s)
    except ValueError:
        return float(s)


# Metric keys produced by extract_stats_from_log. Kept as a module constant so
# the CSV writer knows the full column set without re-introspecting logs.
METRIC_KEYS: tuple[str, ...] = (
    "time_s",
    "mem_used_mb", "mem_free_mb", "mem_allocated_mb", "mem_available_mb",
    "gc_count", "gc_time_ms",
    "throughput_per_s",
    "latency_mean_ms", "latency_p75_ms", "latency_p99_ms", "latency_p999_ms",
)


def extract_stats_from_log(log_path: Path) -> dict | None:
    """
    Parse a dsbulk operation.log and return a dict keyed by METRIC_KEYS.
    Returns None if the operation didn't complete (no 'completed successfully').
    Metrics are taken from the "Final stats:" block when present (that block
    reflects the full operation; the earlier in-line stats are partial).
    """
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"WARN: could not read {log_path}: {e}", file=sys.stderr)
        return None

    # Duration (from the "completed successfully in ..." line)
    m = COMPLETED_RE.search(text)
    if not m:
        return None
    time_s = parse_duration_to_seconds(m.group("dur"))

    # Pick the post-"Final stats:" segment if it exists; otherwise the whole log.
    idx = text.find(FINAL_STATS_MARKER)
    stats_text = text[idx:] if idx != -1 else text

    out: dict = {k: None for k in METRIC_KEYS}
    out["time_s"] = time_s

    mm = MEMORY_RE.search(stats_text)
    if mm:
        out["mem_used_mb"] = _num(mm.group("used"))
        out["mem_free_mb"] = _num(mm.group("free"))
        out["mem_allocated_mb"] = _num(mm.group("allocated"))
        out["mem_available_mb"] = _num(mm.group("available"))
        out["gc_count"] = _num(mm.group("gc_count"))
        out["gc_time_ms"] = _num(mm.group("gc_time"))

    tm = THROUGHPUT_RE.search(stats_text)
    if tm:
        out["throughput_per_s"] = _num(tm.group("value"))

    lm = LATENCY_RE.search(stats_text)
    if lm:
        out["latency_mean_ms"] = _num(lm.group("mean"))
        out["latency_p75_ms"] = _num(lm.group("p75"))
        out["latency_p99_ms"] = _num(lm.group("p99"))
        out["latency_p999_ms"] = _num(lm.group("p999"))

    return out


def collect_stats(op_dirs: list[Path]) -> list[dict | None]:
    """
    Sort op_dirs by name (==timestamp, zero-padded) ascending and return a
    stats dict (or None) per run.
    """
    out: list[dict | None] = []
    for d in sorted(op_dirs, key=lambda p: p.name):
        log = d / "operation.log"
        out.append(extract_stats_from_log(log) if log.is_file() else None)
    return out


# ---------------------------------------------------------------------------
# Folder walking
# ---------------------------------------------------------------------------

def process_root(root: Path, cases: tuple[Case, ...]) -> tuple[list[dict], set[Case]]:
    """
    Walk root, match each subfolder against the available cases, parse logs.
    Returns (rows, set_of_cases_actually_seen).
    """
    rows: list[dict] = []
    seen_cases: set[Case] = set()

    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        matched = match_case(entry.name, cases)
        if matched is None:
            continue
        case, fields = matched
        seen_cases.add(case)

        logs_dir = entry / "logs"
        if not logs_dir.is_dir():
            print(f"WARN: no logs/ directory under {entry}", file=sys.stderr)
            continue

        loads: list[Path] = []
        unloads: list[Path] = []
        for op in logs_dir.iterdir():
            if not op.is_dir():
                continue
            om = OP_RE.match(op.name)
            if not om:
                continue
            (loads if om.group("kind") == "LOAD" else unloads).append(op)

        load_stats = collect_stats(loads)
        unload_stats = collect_stats(unloads)

        # Pair by index. Pad the short side so leftovers still appear.
        for i in range(max(len(load_stats), len(unload_stats))):
            rows.append({
                "__case__": case,
                "__fields__": fields,
                "load": load_stats[i] if i < len(load_stats) else None,
                "unload": unload_stats[i] if i < len(unload_stats) else None,
            })

    return rows, seen_cases


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def _sort_key(v):
    """Numbers before strings; None last."""
    if v is None:
        return (2, 0)
    if isinstance(v, int):
        return (0, v)
    return (1, str(v))


def _metric_columns() -> tuple[str, ...]:
    """Column order for a single-kind CSV: the metric keys, in METRIC_KEYS order."""
    return METRIC_KEYS


def write_csv(rows: list[dict], case: Case, kind: str, output: Path) -> int:
    """
    Write rows for a single case and a single kind ('load' or 'unload') to CSV.
    Rows where that kind has no data are skipped. Returns rows written.
    """
    assert kind in ("load", "unload")
    fieldnames = (*case.columns, *_metric_columns())

    case_rows = [
        r for r in rows
        if r["__case__"] is case and r[kind] is not None
    ]
    case_rows.sort(
        key=lambda r: tuple(_sort_key(r["__fields__"].get(c)) for c in case.columns)
    )

    if output.exists():
        raise FileExistsError(f"{output} already exists; refusing to overwrite")

    with output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in case_rows:
            stats = r[kind]
            out_row = {c: r["__fields__"].get(c, "") for c in case.columns}
            for k in METRIC_KEYS:
                v = stats.get(k)
                out_row[k] = "" if v is None else v
            w.writerow(out_row)
    return len(case_rows)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Extract dsbulk LOAD/UNLOAD timings to CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("root", type=Path, help="Directory containing case folders")
    ap.add_argument(
        "-o", "--output", type=Path, default=Path("dsbulk_timings.csv"),
        help="Output CSV stem. Files are written as <stem>.load.csv and "
             "<stem>.unload.csv (with the case name inserted if multiple "
             "cases are present, e.g. <stem>.rows_cols.load.csv).",
    )
    ap.add_argument(
        "--case", choices=[c.name for c in CASES], default=None,
        help="Only process this case; ignore folders matching other cases.",
    )
    args = ap.parse_args()

    if not args.root.is_dir():
        ap.error(f"{args.root} is not a directory")

    active_cases = (
        tuple(c for c in CASES if c.name == args.case) if args.case else CASES
    )

    rows, seen = process_root(args.root, active_cases)
    if not rows:
        print("No matching folders found.", file=sys.stderr)
        return 1

    seen_list = [c for c in active_cases if c in seen]
    stem = args.output.with_suffix("")
    suffix = args.output.suffix or ".csv"
    multi_case = len(seen_list) > 1

    for case in seen_list:
        for kind in ("load", "unload"):
            parts = [stem.name]
            if multi_case:
                parts.append(case.name)
            parts.append(kind)
            out = stem.with_name(".".join(parts) + suffix)
            n = write_csv(rows, case, kind, out)
            tag = f"case: {case.name}, kind: {kind}"
            print(f"Wrote {n} rows to {out} ({tag})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
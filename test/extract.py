#!/usr/bin/env python3
"""
Extract dsbulk LOAD/UNLOAD stats from a parent dir of <timestamp> trees.

Expected layout (the script is given the parent of one or more <timestamp>):
    <parent>/
        <timestamp>/
            <subcase_name>/
                init/
                    <table_name>/
                        logs/
                            LOAD_<ts>/operation.log     (skipped — see note)
                            UNLOAD_<ts>/operation.log
                <evolution_name>/
                    <table_name>/
                        logs/
                            LOAD_<ts>/operation.log
                            UNLOAD_<ts>/operation.log
        <another_timestamp>/
            ...

LOAD operations under any `init/` are deliberately skipped (setup phase).
UNLOAD operations are kept everywhere.

Output: per <timestamp>, two CSVs
    <out_dir>/<timestamp>.load.csv
    <out_dir>/<timestamp>.unload.csv
with columns: subcase,stage,table_name,time_s,<dsbulk stats...>

One row per dsbulk run (multiple LOAD/UNLOAD runs in one logs/ produce multiple rows).

Usage:
    python extract_dsbulk_subcase.py <parent_dir> [-o output_dir]
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# dsbulk log parsing — same format as extract_dsbulk_times.py
# ---------------------------------------------------------------------------

OP_RE = re.compile(r"^(?P<kind>LOAD|UNLOAD)_")

COMPLETED_RE = re.compile(
    r"completed successfully in\s+(?P<dur>[^.]+)\.", re.IGNORECASE
)
UNIT_RE = re.compile(r"(\d+)\s*(hours?|minutes?|seconds?)", re.IGNORECASE)
ZERO_SECOND_RE = re.compile(r"less than one second")

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

# Order matters: this is the CSV column order after stage/table_name.
METRIC_KEYS: tuple[str, ...] = (
    "time_s",
    "mem_used_mb", "mem_free_mb", "mem_allocated_mb", "mem_available_mb",
    "gc_count", "gc_time_ms",
    "throughput_per_s",
    "latency_mean_ms", "latency_p75_ms", "latency_p99_ms", "latency_p999_ms",
)


def parse_duration_to_seconds(phrase: str) -> int | None:
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
    s = s.replace(",", "")
    try:
        return int(s)
    except ValueError:
        return float(s)


def extract_stats_from_log(log_path: Path) -> dict | None:
    """Parse a dsbulk operation.log; None if it didn't complete successfully."""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"WARN: could not read {log_path}: {e}", file=sys.stderr)
        return None

    m = COMPLETED_RE.search(text)
    if not m:
        return None

    out: dict = {k: None for k in METRIC_KEYS}
    out["time_s"] = parse_duration_to_seconds(m.group("dur"))

    # Prefer the "Final stats:" block; the earlier inline summary is partial.
    idx = text.find(FINAL_STATS_MARKER)
    stats_text = text[idx:] if idx != -1 else text

    if mm := MEMORY_RE.search(stats_text):
        out["mem_used_mb"] = _num(mm.group("used"))
        out["mem_free_mb"] = _num(mm.group("free"))
        out["mem_allocated_mb"] = _num(mm.group("allocated"))
        out["mem_available_mb"] = _num(mm.group("available"))
        out["gc_count"] = _num(mm.group("gc_count"))
        out["gc_time_ms"] = _num(mm.group("gc_time"))
    if tm := THROUGHPUT_RE.search(stats_text):
        out["throughput_per_s"] = _num(tm.group("value"))
    if lm := LATENCY_RE.search(stats_text):
        out["latency_mean_ms"] = _num(lm.group("mean"))
        out["latency_p75_ms"] = _num(lm.group("p75"))
        out["latency_p99_ms"] = _num(lm.group("p99"))
        out["latency_p999_ms"] = _num(lm.group("p999"))

    return out


# ---------------------------------------------------------------------------
# Walker
# ---------------------------------------------------------------------------

# A row is just a dict; we collect per (subcase, kind).
# Skip-rule: LOAD operations under stage == "init" are not emitted.
INIT_STAGE = "init"


def walk_subcase(subcase_dir: Path) -> dict[str, list[dict]]:
    """
    Walk one subcase folder, returning {"load": [...rows...], "unload": [...]}.
    Each row carries stage, table_name, and all metric fields.
    """
    out: dict[str, list[dict]] = {"load": [], "unload": []}

    for stage_dir in sorted(subcase_dir.iterdir()):
        if not stage_dir.is_dir():
            continue
        stage = stage_dir.name

        for table_dir in sorted(stage_dir.iterdir()):
            if not table_dir.is_dir():
                continue
            table_name = table_dir.name
            logs_dir = table_dir / "logs"
            if not logs_dir.is_dir():
                print(f"WARN: no logs/ under {table_dir}", file=sys.stderr)
                continue

            # Sort op folders by name (== timestamp) ascending so emitted rows
            # appear in chronological order.
            for op in sorted(logs_dir.iterdir(), key=lambda p: p.name):
                if not op.is_dir():
                    continue
                om = OP_RE.match(op.name)
                if not om:
                    continue
                kind_raw = om.group("kind")  # "LOAD" or "UNLOAD"
                kind = "load" if kind_raw == "LOAD" else "unload"

                # Skip rule: ignore LOAD ops in init.
                if stage == INIT_STAGE and kind == "load":
                    continue

                log = op / "operation.log"
                if not log.is_file():
                    continue
                stats = extract_stats_from_log(log)
                if stats is None:
                    # Operation didn't complete — skip rather than emit blanks.
                    print(
                        f"INFO: skipping incomplete run {op}", file=sys.stderr
                    )
                    continue

                row = {
                    "subcase": subcase_dir.name,
                    "stage": stage,
                    "table_name": table_name,
                    **stats,
                }
                out[kind].append(row)

    return out


def walk_timestamp(ts_dir: Path) -> dict[str, list[dict]]:
    """
    Walk one <timestamp> directory and merge rows from all subcases.
    Returns {"load": [...], "unload": [...]} with rows tagged by subcase.
    """
    merged: dict[str, list[dict]] = {"load": [], "unload": []}

    for subcase_dir in sorted(ts_dir.iterdir()):
        if not subcase_dir.is_dir():
            continue
        if not (subcase_dir / "init").is_dir():
            print(
                f"WARN: skipping {subcase_dir} — no init/ folder",
                file=sys.stderr,
            )
            continue
        rows = walk_subcase(subcase_dir)
        merged["load"].extend(rows["load"])
        merged["unload"].extend(rows["unload"])

    return merged


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

FIELDNAMES = ("subcase", "stage", "table_name", *METRIC_KEYS)


def write_csv(rows: list[dict], output: Path) -> int:
    with output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for r in rows:
            w.writerow({
                k: ("" if r.get(k) is None else r.get(k, ""))
                for k in FIELDNAMES
            })
    return len(rows)


def _safe_filename(name: str) -> str:
    """Replace path separators / risky chars in subcase names."""
    return re.sub(r"[^\w.\-]+", "_", name)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _looks_like_timestamp_dir(d: Path) -> bool:
    """A timestamp dir is any direct child that itself contains at least one
    subcase folder with an init/ subfolder. This filters out unrelated dirs
    in the parent without hard-coding a timestamp regex."""
    if not d.is_dir():
        return False
    try:
        for sub in d.iterdir():
            if sub.is_dir() and (sub / "init").is_dir():
                return True
    except OSError:
        pass
    return False


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "test_case",
        type=str,
        help="Test case name (directly under test/), e.g. EB06",
    )
    ap.add_argument(
        "-o", "--output-dir", type=str, default="",
        help="Directory to write CSVs into (basedir: test/<test_case>/data)",
    )
    args = ap.parse_args()

    parent = Path(__file__).parent / args.test_case / "out" / "work"

    if not parent.is_dir():
        ap.error(f"{parent} is not a directory")

    output_dir = Path(__file__).parent / args.test_case / "data"
    if args.output_dir:
        output_dir /= Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp_dirs = [
        d for d in sorted(parent.iterdir()) if _looks_like_timestamp_dir(d)
    ]
    if not timestamp_dirs:
        print(
            f"No timestamp directories found under {parent} "
            "(looked for subdirs containing <subcase>/init/).",
            file=sys.stderr,
        )
        return 1

    any_written = False
    for ts_dir in timestamp_dirs:
        rows = walk_timestamp(ts_dir)
        if not rows["load"] and not rows["unload"]:
            print(f"INFO: no usable runs under {ts_dir}", file=sys.stderr)
            continue

        safe = _safe_filename(ts_dir.name)
        for kind in ("load", "unload"):
            out = output_dir / f"{safe}.{kind}.csv"
            n = write_csv(rows[kind], out)
            print(f"Wrote {n} rows to {out}")
            any_written = any_written or n > 0

    return 0 if any_written else 1


if __name__ == "__main__":
    sys.exit(main())
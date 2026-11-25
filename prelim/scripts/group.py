#!/usr/bin/env python3
"""
Parse CSV data, group by specified key column(s), and output statistics
(mean, mode, median, trimmed mean) per group as a table or CSV.

Requires: prettytable  (pip install prettytable)

Usage:
    python csv_group_stats.py <csv_file> --group-by <col1> [<col2> ...] \
        --value-col <value_col> [--format table|csv] [--output <file>]
"""

import argparse
import csv
import statistics
import sys
from collections import defaultdict

from prettytable import PrettyTable


def trimmed_mean(values):
    """Mean after removing the single lowest and single highest value."""
    if len(values) < 3:
        return None
    trimmed = sorted(values)[1:-1]
    return sum(trimmed) / len(trimmed)


def compute_mode(values):
    """Return mode(s). '-' if every value is unique; single value as-is;
    multiple modes joined with '/'."""
    modes = statistics.multimode(values)
    if len(modes) == len(set(values)):
        return "-"
    if len(modes) == 1:
        return modes[0]
    return "/".join(str(m) for m in modes)


def coerce(s):
    """Try int, then float, otherwise leave as string."""
    s = s.strip()
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return s


def round_num(n, ndigits=2):
    """Round floats; pass ints/non-numbers through. Floats with no fractional
    part become ints so PrettyTable formats them cleanly."""
    if isinstance(n, float):
        r = round(n, ndigits)
        return int(r) if r.is_integer() else r
    return n


def parse_csv(file_path, group_keys, value_col):
    """Read CSV and bucket integer values by the composite group key.
    Group key cells are coerced to int/float when possible so they sort
    numerically and render right-aligned."""
    groups = defaultdict(list)

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        missing = [c for c in group_keys + [value_col] if c not in reader.fieldnames]
        if missing:
            sys.exit(
                f"Error: column(s) not found in CSV: {', '.join(missing)}\n"
                f"Available columns: {', '.join(reader.fieldnames)}"
            )

        for row_num, row in enumerate(reader, start=2):
            key = tuple(coerce(row[k]) for k in group_keys)
            raw = row[value_col].strip()
            try:
                value = int(raw)
            except ValueError:
                print(
                    f"Warning: skipping row {row_num}, "
                    f"non-integer value {raw!r} in column {value_col!r}",
                    file=sys.stderr,
                )
                continue
            groups[key].append(value)

    return groups


def sort_key(key):
    """Sort tuples that may mix numbers and strings by treating each cell
    as (is_string, value) so types don't collide on comparison."""
    return tuple((isinstance(v, str), v) for v in key)


def build_rows(groups, group_keys):
    """Produce header + rows of stats, one row per group.
    Numeric cells stay numeric so PrettyTable right-aligns them."""
    header = list(group_keys) + [
        "count", "sorted", "mean", "median", "mode", "trimmed_mean"
    ]
    rows = []
    for key in sorted(groups.keys(), key=sort_key):
        values = groups[key]
        sorted_vals = sorted(values)
        tm = trimmed_mean(values)
        row = list(key) + [
            len(values),
            " ".join(str(v) for v in sorted_vals),
            round_num(statistics.mean(values)),
            round_num(statistics.median(values)),
            compute_mode(values),
            round_num(tm) if tm is not None else "N/A",
        ]
        rows.append(row)
    return header, rows


def print_table(header, rows, stream):
    """Print rows using prettytable. Numbers right-align, strings left-align."""
    table = PrettyTable()
    table.field_names = header
    for r in rows:
        table.add_row(r)
    for col in header:
        # Right-align columns whose values are all numeric; left-align otherwise.
        col_idx = header.index(col)
        all_numeric = all(isinstance(r[col_idx], (int, float)) for r in rows)
        table.align[col] = "r" if all_numeric else "l"
    print(table, file=stream)


def write_csv(header, rows, stream):
    writer = csv.writer(stream)
    writer.writerow(header)
    writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Group CSV rows and output stats per group as a table or CSV.",
    )
    parser.add_argument("csv_file", help="Path to the CSV file")
    parser.add_argument(
        "--group-by", nargs="+", required=True, metavar="COL",
        help="One or more column names to group by",
    )
    parser.add_argument(
        "--value-col", required=True,
        help="Name of the integer column to summarise",
    )
    parser.add_argument(
        "-f", "--format", choices=("table", "csv"), default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "-o", "--output", help="Write output to this file instead of stdout",
    )

    args = parser.parse_args()

    groups = parse_csv(args.csv_file, args.group_by, args.value_col)
    if not groups:
        print("No data to summarise.")
        return

    header, rows = build_rows(groups, args.group_by)

    out_stream = open(args.output, "w", newline="", encoding="utf-8") \
        if args.output else sys.stdout
    try:
        if args.format == "csv":
            write_csv(header, rows, out_stream)
        else:
            print_table(header, rows, out_stream)
    finally:
        if args.output:
            out_stream.close()
            print(f"Wrote {len(rows)} group(s) to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
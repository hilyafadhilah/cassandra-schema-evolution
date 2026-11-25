#!/usr/bin/env python3
"""Append one or more CSV files into a target CSV file, in the order given.

The target file's existing contents are kept, and each source file's data
rows are appended after it. Source files are processed in the order they
appear on the command line.

By default all files are assumed to share the same header row: the source
headers are skipped when appending, and a mismatch is reported as an error
(override with --no-header-check or --no-header).

Examples:
    # Append b.csv then c.csv onto a.csv (in place)
    python merge_csv.py a.csv b.csv c.csv

    # Write the result to a new file instead of modifying the target
    python merge_csv.py a.csv b.csv c.csv -o merged.csv

    # Files have no header row at all
    python merge_csv.py a.csv b.csv --no-header
"""

import argparse
import csv
import sys
from pathlib import Path


def read_rows(path):
    """Read a CSV file and return (header, data_rows).

    header is the first row (or None if the file is empty).
    """
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return None, []
    return rows[0], rows[1:]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Append CSV files into a target CSV, in the order specified."
    )
    parser.add_argument("target", help="The CSV file that others are appended to.")
    parser.add_argument(
        "sources",
        nargs="+",
        help="One or more CSV files to append, in order.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write the merged result here instead of modifying the target in place.",
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="Treat files as having no header row (every row is data).",
    )
    parser.add_argument(
        "--no-header-check",
        action="store_true",
        help="Skip source headers without checking that they match the target's.",
    )
    args = parser.parse_args(argv)

    target_path = Path(args.target)
    if not target_path.is_file():
        parser.error(f"target file not found: {target_path}")

    missing = [s for s in args.sources if not Path(s).is_file()]
    if missing:
        parser.error("source file(s) not found: " + ", ".join(missing))

    target_header, target_data = read_rows(target_path)

    if args.no_header:
        # No headers anywhere: everything (including each first row) is data.
        merged = ([] if target_header is None else [target_header]) + target_data
        for src in args.sources:
            h, data = read_rows(src)
            if h is not None:
                merged.append(h)
            merged.extend(data)
        header_out = None
    else:
        if target_header is None:
            parser.error(f"target file is empty, cannot determine header: {target_path}")
        merged = list(target_data)
        for src in args.sources:
            h, data = read_rows(src)
            if h is None:
                continue  # empty source, nothing to append
            if not args.no_header_check and h != target_header:
                parser.error(
                    f"header of {src} does not match target.\n"
                    f"  target: {target_header}\n"
                    f"  {src}: {h}\n"
                    f"Use --no-header-check to append anyway, or --no-header "
                    f"if the files have no header row."
                )
            merged.extend(data)
        header_out = target_header

    out_path = Path(args.output) if args.output else target_path
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if header_out is not None:
            writer.writerow(header_out)
        writer.writerows(merged)

    total = len(merged) + (1 if header_out is not None else 0)
    print(
        f"Merged {len(args.sources)} file(s) into {out_path} "
        f"({total} rows total)."
    )


if __name__ == "__main__":
    main()
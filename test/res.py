import argparse
from collections import defaultdict
import csv
from decimal import Decimal
from pathlib import Path
import sys
from typing import TextIO

import pandas as pd

from test.lib.cost import EvolCost
from test.lib.evol import TestCaseConfig
from test.lib.res import load_series
from test.lib.run import get_config
from test.lib.utils import number_format


def print_results(
    config: TestCaseConfig,
    subconf_class: type,
    series: pd.Series,
    out: TextIO,
    op_filter: EvolCost.Operation | None = None,
) -> None:
    subcases = {
        subcase: subconf_class(**subconfig)
        for subcase, subconfig in config.subcases.items()
    }

    if config.cost:
        evol_cost = EvolCost(config.cost)
        for subcase, subconfig in subcases.items():
            evol_cost.add_subconfig(subcase, subconfig)

    if config.results:
        writer = csv.writer(out, delimiter='\t')
        headers: list[tuple[str, ...]] = []

        times: dict[tuple, float] = defaultdict(float)
        costs: dict[tuple, Decimal] = defaultdict(Decimal)

        for subcase, subconfig in subcases.items():
            for group in config.results.values():
                if not group.data:
                    continue

                for table, ops in group.data.items():
                    for op in ops:
                        op_time = series.get((subcase, op.group, op.table, op.op))
                        if op_time is None:
                            continue
                        if len(op.subcases) and subcase not in op.subcases:
                            continue
                        if op_filter and op.op != op_filter:
                            continue
                        times[(subcase, group.name, table)] += op_time
                        times[(subcase, group.name)] += op_time

                    if (group.name, table) not in headers:
                        headers.append((group.name, table))

                if (group.name, '') not in headers:
                    headers.append((group.name, ''))

        if evol_cost:
            for subcase in config.subcases:
                for group in config.results.values():
                    if not group.data:
                        continue

                    for table, ops in group.data.items():
                        for op in ops:
                            cost_table = op.cost if op.cost is not None else table
                            costs[(subcase, group.name, table)] = evol_cost.get_cost(subcase, cost_table, op_filter)
                            if op.op == 'load':
                                costs[(subcase, group.name)] += evol_cost.get_cost(subcase, cost_table, op_filter)

        writer.writerow(['subcase', 'key'] + [
            f'{g}.{t}' if t else g
            for g, t in headers
        ])

        for subcase in config.subcases:
            # cost
            row = [subcase, 'cost']
            for gname, table in headers:
                if table:
                    c = costs.get((subcase, gname, table), Decimal(0))
                else:
                    c = costs.get((subcase, gname), Decimal(0))
                row.append(number_format(c) if c != Decimal(0) else '0')
            writer.writerow(row)

            # result
            row = [subcase, 'res']
            for gname, table in headers:
                if table:
                    t = times.get((subcase, gname, table), float('nan'))
                else:
                    t = times.get((subcase, gname), float('nan'))
                row.append(number_format(t, precision=1) + 's')
            writer.writerow(row)


if __name__ == '__main__':
    argparser = argparse.ArgumentParser()
    argparser.add_argument('module')
    argparser.add_argument('--work', '-w', type=str, default='')
    argparser.add_argument(
        '--print', '-p',
        action='store_true',
    )
    argparser.add_argument(
        '--load-only', '-l',
        action='store_true',
    )

    args = argparser.parse_args()

    data_dir = Path(__file__).parent / args.module / 'data'
    if args.work:
        data_dir /= args.work

    files: list[tuple[Path, str]] = []
    for file in data_dir.glob('*.csv'):
        timestamp, op, _ = file.name.split('.')
        files.append((file, op))

    s = load_series(files)

    config, subconf_class = get_config(args.module)

    path = data_dir / 'res.tsv'
    if args.print:
        out = sys.stdout
    else:
        out = open(path, 'w', newline='')

    print_results(
        config=config,
        subconf_class=subconf_class,
        series=s,
        out=out,
        op_filter='load' if args.load_only else None
    )

    if out is not sys.stdout:
        out.close()
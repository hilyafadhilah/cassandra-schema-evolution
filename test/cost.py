import argparse
from collections import defaultdict
import csv
from decimal import Decimal
from pathlib import Path
import sys
import sys
from typing import Literal, TextIO

from test.lib.base import base_config
from test.lib.cost import EvolCost
from test.lib.evol import TestCaseConfig
from test.lib.run import get_config
from test.lib.utils import number_format


class CostPrinter:
    def __init__(
        self,
        config: TestCaseConfig,
        subconf_cls: type,
        basedir: Path,
    ):
        self.config = config
        self.subcases = {
            subcase: subconf_cls(**subconfig)
            for subcase, subconfig in config.subcases.items()
        }
        self.basedir = basedir
        self.base_config = base_config()

        if config.cost:
            self.evol_cost = EvolCost(config.cost)
            for subcase, subconfig in self.subcases.items():
                self.evol_cost.add_subconfig(subcase, subconfig)


    def print_costs(
        self,
        to_file: bool = True,
        op: EvolCost.Operation | None = None
    ) -> None:
        if not self.evol_cost or not self.config.cost:
            return
        
        tables = list(self.config.cost.keys())
        
        costs = {
            tbl: [
                self.evol_cost.get_cost(subcase, tbl, op)
                for subcase in self.subcases
            ] for tbl in tables
        }

        out: TextIO
        if to_file:
            path = self.basedir / 'cost.tsv'
            out = open(path, 'w', newline='', encoding='utf-8')
        else:
            out = sys.stdout
            print('\n === Costs === \n')

        writer = csv.writer(out, delimiter='\t')
        writer.writerow(['table'] + list(self.subcases.keys()))
        for tbl in self.config.cost:
            writer.writerow([tbl] + [
                number_format(cost) if cost != Decimal(0) else '0'
                for cost in costs[tbl]
            ])
        
        if to_file:
            out.close()


    def print_subcases(
        self,
        to_file: bool = True,
    ) -> None:
        if not self.config.cost:
            return
        
        out: TextIO
        if to_file:
            path = self.basedir / 'subcases.tsv'
            out = open(path, 'w', newline='', encoding='utf-8')
        else:
            out = sys.stdout
            print('\n === Subcases === \n')

        headers = {}
        for subconfig in self.subcases.values():
            for field in subconfig.__dataclass_fields__.keys():
                if field not in headers:
                    headers[field] = True

        writer = csv.writer(out, delimiter='\t')
        writer.writerow(['subcase'] + list(headers.keys()))
        for subcase, subconfig in self.subcases.items():
            writer.writerow([subcase] + [
                getattr(subconfig, field, '')
                for field in headers
            ])

        if to_file:
            out.close()


    def print_read_costs(
        self,
        to_file: bool = True,
    ):
        if not self.config.read:
            return

        queries = self.config.read.queries
        aliases = self.base_config.aliases

        data: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
        for qname, query in queries.items():
            for plan in query.plans:
                for tbl in plan.tables:
                    cost = tbl.cost_str(aliases=aliases.mids)
                    data[(qname, plan.name)].append({
                        'step': tbl.name.upper() if tbl.name.startswith('cf') else tbl.name,
                        'n': str(tbl.n),
                        'w': str(tbl.w),
                        'T': cost,
                        'overhead': '-',
                    })
                if plan.filters:
                    data[(qname, plan.name)].extend({
                        'step': f'Filter {f.short_name}',
                        'n': '-',
                        'w': '-',
                        'T': '-',
                        'overhead': f.cost_str(),
                    } for f in plan.filters)
                if plan.sorts:
                    data[(qname, plan.name)].extend({
                        'step': f'Sort {s.short_name}',
                        'n': '-',
                        'w': '-',
                        'T': '-',
                        'overhead': s.cost_str(),
                    } for s in plan.sorts)

        out: TextIO
        if to_file:
            path = self.basedir / 'cost_read.tsv'
            out = open(path, 'w', newline='', encoding='utf-8')
        else:
            out = sys.stdout
            print('\n === Read Costs === \n')

        headers = {
            'plan': 'plan',
            'step': 'step',
            'n': 'n',
            # 'w': 'w',
            'T': 'T',
            'Δ': 'overhead',
            '∑C×f': 'sum',
        }

        writer = csv.writer(out, delimiter='\t')
        writer.writerow(list(headers.keys()))

        for query in queries.values():
            writer.writerow(
                [query.name.upper()] +
                ['' for _ in range(len(headers) - 1)]
            )

            for plan_no, plan in enumerate(query.plans, start=1):
                plan_cost = plan.cost_str(aliases=aliases.shorts)
                for j, row in enumerate(data[(query.name, plan.name)]):
                    writer.writerow([
                        '' if j > 0 else f'{plan_no}',
                        row['step'],
                        row['n'],
                        # row['w'],
                        row['T'],
                        row['overhead'],
                        '' if j > 0 else plan_cost,
                    ])



    def print_cost_comparison(
        self,
        to_file: bool = True,
    ):
        config = self.config
        if not config.cost or not config.read or not config.results:
            return
        
        bconf = self.base_config
        queries = config.read.queries
        evol_cost = self.evol_cost
        subcases = self.subcases

        groups = ['init'] + list(config.results.keys())
        m_costs: dict[tuple[str, str], Decimal | Literal[0] | None] = {}
        r_costs: dict[tuple[str, str], Decimal | Literal[0] | None] = {}

        for subcase, subconfig in subcases.items():
            m_costs[('init', subcase)] = None
            r_costs[('init', subcase)] = sum(
                bconf.queries[query.name].plan.calc_cost(subconfig)
                if query.name in bconf.queries else Decimal(0)
                for query in queries.values()
            )

            if r_costs[('init', subcase)] == Decimal(0):
                r_costs[('init', subcase)] = None

        for group_name, group in config.results.items():
            for subcase, subconfig in subcases.items():
                if group.data:
                    m_costs[(group_name, subcase)] = sum(
                        evol_cost.get_cost(subcase, tbl)
                        for tbl in group.data
                    )
                else:
                    m_costs[(group_name, subcase)] = 0

                r_costs[(group_name, subcase)] = sum(
                    queries[query].plans[plan - 1].calc_cost(subconfig)
                    for query, plan in group.plans.items()
                )

        out: TextIO
        if to_file:
            path = self.basedir / 'cost_comparison.tsv'
            out = open(path, 'w', newline='', encoding='utf-8')
        else:
            out = sys.stdout
            print('\n === Cost Comparison === \n')

        writer = csv.writer(out, delimiter='\t')
        writer.writerow(['group'] + list(subcases.keys()))
        for group_name in groups:
            writer.writerow([group_name] + [
                number_format(m_costs[(group_name, subcase)])
                if m_costs[(group_name, subcase)] is not None else '-'
                for subcase in subcases
            ])
            writer.writerow([''] + [
                number_format(r_costs[(group_name, subcase)])
                if r_costs[(group_name, subcase)] is not None else '-'
                for subcase in subcases
            ])


if __name__ == '__main__':
    argparser = argparse.ArgumentParser()
    argparser.add_argument('module')
    argparser.add_argument(
        '--print', '-p',
        action='store_true',
    )
    argparser.add_argument(
        '--operation', '-t',
        type=str,
        choices=['unload', 'load', 'all'],
        default='all',
    )

    args = argparser.parse_args()

    config, subconf_class = get_config(args.module)

    basedir = Path(__file__).parent / args.module / 'data'
    basedir.mkdir(exist_ok=True)

    printer = CostPrinter(config, subconf_class, basedir)

    printer.print_subcases(to_file=not args.print)

    op = None if args.operation == 'all' else args.operation
    printer.print_costs(to_file=not args.print, op=op)

    printer.print_read_costs(to_file=not args.print)

    printer.print_cost_comparison(to_file=not args.print)

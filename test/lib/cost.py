from collections import defaultdict
from dataclasses import field
from decimal import Decimal
from typing import Any, Iterable, Literal, cast
from warnings import warn

from pydantic.dataclasses import dataclass

from test.lib.utils import number_format


type EvolCostConfig = dict[str, list[TableOpCostConfig] | Literal[0]]


class EvolCost:
    type Operation = Literal['unload', 'load']

    costs: dict[tuple[str, str, EvolCost.Operation | None], Decimal]

    def __init__(
        self,
        input: EvolCostConfig,
    ):
        self.cost_conf = input
        self.costs = defaultdict(Decimal)

    def calc_cost(self, table: str, conf: Any, ops: Iterable[Operation] | None = None) -> Decimal:
        if table not in self.cost_conf:
            return Decimal(0)

        op_costs = self.cost_conf[table]
        if op_costs == 0:
            return Decimal(0)

        cost = Decimal(0)
        for op_cost in op_costs:
            if ops and op_cost.op not in ops:
                continue
            cost += op_cost.calc_cost(conf)

        return cost


    def add_subconfig(self, name: str, conf: Any) -> None:
        for table in self.cost_conf:
            self.costs[(name, table, 'unload')] = self.calc_cost(table, conf, ops=['unload'])
            self.costs[(name, table, 'load')] = self.calc_cost(table, conf, ops=['load'])
            self.costs[(name, table, None)] = self.calc_cost(table, conf, ops=None)


    def get_cost(self, subcase: str, table: str, op: EvolCost.Operation | None = None) -> Decimal:
        return self.costs.get((subcase, table, op), Decimal(0))


@dataclass(frozen=True)
class TableOpCostConfig:
    op: Literal['unload', 'load']
    c: int
    p: str
    r: str | Literal[1]
    agg: tuple[AggCostConfig, ...] | None = None

    def calc_cost(self, conf: Any) -> Decimal:
        if self.op == 'unload':
            return self.calc_unload_cost(conf)
        elif self.op == 'load':
            return self.calc_load_cost(conf)
        else:
            raise ValueError(f'Invalid op type: {self.op}')

    def get_cpr(self, conf: Any) -> tuple[int, int, int]:
        c = self.c
        p = getattr(conf, self.p, 0)
        r = getattr(conf, self.r, 0) if self.r != 1 else 1
        return c, p, r
    
    def calc_unload_cost(self, conf: Any) -> Decimal:
        c, p, r = self.get_cpr(conf)
        return calc_table_unload_cost(c=c, p=p, r=r)
    
    def calc_load_cost(self, conf: Any) -> Decimal:
        c, p, r = self.get_cpr(conf)
        return (
            calc_table_load_cost(c=c, p=p, r=r)
            + self.calc_agg_cost(conf)
        )
    
    def calc_agg_cost(self, conf: Any) -> Decimal:
        if self.agg is None:
            return Decimal(0)
        
        _, p, r = self.get_cpr(conf)

        agg_cost = Decimal(0)
        for agg_conf in self.agg:
            if agg_conf.type == 'set':
                if isinstance(agg_conf.v, int):
                    v = agg_conf.v
                else:
                    v = getattr(conf, agg_conf.v, 0)
                agg_cost += calc_set_overhead_cost(p=p, r=r, v=v)
            elif agg_conf.type == 'map':
                if isinstance(agg_conf.v, int):
                    v = agg_conf.v
                else:
                    v = getattr(conf, agg_conf.v, 0)
                agg_cost += calc_map_overhead_cost(p=p, r=r, v=v)
        return Decimal(0) if agg_cost < 0 else agg_cost


@dataclass(frozen=True)
class AggCostConfig:
    type: Literal['set', 'map']
    v: str | int


def calc_table_unload_cost(c: int, p: int, r: int) -> Decimal:
    if p >= 5_000 and r <= 100:
        _p = Decimal(p).scaleb(-5)
        cost = (
            + Decimal('0.02')   * c
            + Decimal('1.40')   * _p
            - Decimal('0.17')
        )
    elif p <= 1_000:
        _p = Decimal(p).scaleb(-3)
        _r = Decimal(r).scaleb(-3)
        _c = Decimal(c).scaleb(-1)
        cost = (
            - Decimal('0.42')   * c
            + Decimal('0.66')   * _p
            + Decimal('0.68')   * _r
            + Decimal('5.71')   * _p * _r * _c
            + Decimal('0.30')
        )
    else:
        raise ValueError(f'Out of range: p={p}, r={r}')
    return Decimal(0) if cost < 0 else cost


def calc_table_load_cost(c: int, p: int, r: int) -> Decimal:
    if p >= 5_000 and r <= 100:
        _p = Decimal(p).scaleb(-5)
        return (
              Decimal('0.47')   * c
            + Decimal('11.47')  * _p
            + Decimal('0.07')  * r
            + Decimal('1.02')   * _p * r
            - Decimal('3.26')
        )
    elif p <= 1_000:
        _p = Decimal(p).scaleb(-3)
        _r = Decimal(r).scaleb(-3)
        return (
              Decimal('0.32')   * c
            + Decimal('0.86')   * _p
            + Decimal('0.45')   * _r
            + Decimal('25.08')  * _p * _r
            - Decimal('3.24')
        )
    else:
        raise ValueError(f'Out of range: p={p}, r={r}')


def calc_set_overhead_cost(p: int, r: int, v: int) -> Decimal:
    _p = Decimal(p).scaleb(-2)
    _r = Decimal(r).scaleb(-2)
    _v = Decimal(v).scaleb(-2)
    _prv = _p * _r * _v

    return (
          Decimal('1.52') * _prv
        - Decimal('0.4')
    )


def calc_map_overhead_cost(p: int, r: int, v: int) -> Decimal:
    _p = (Decimal(p) ** Decimal('0.87')).scaleb(-2)
    _r = (Decimal(r) ** Decimal('0.8')).scaleb(-2)
    _v = (Decimal(v) ** Decimal('0.81')).scaleb(-2)
    _prv = _p * _r * _v

    return (
        Decimal('82.95') * _prv
    )


# READ COST


@dataclass
class ReadConfig:
    tables: dict[str, ReadTableConfig]
    queries: dict[str, ReadQueryConfig]

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> 'ReadConfig':
        tables_data = data.get('tables', {})
        queries_data = data.get('queries', {})

        tables = {
            table_name: ReadTableConfig(
                name=table_name,
                **table_conf
            )
            for table_name, table_conf in tables_data.items()
        }

        queries: dict[str, ReadQueryConfig] = {}
        for qname, q_conf in queries_data.items():
            if not isinstance(q_conf.get('plans'), list):
                raise ValueError(f'Invalid query plan configuration for {qname}')
            
            f = q_conf.get('f', 1)

            plans: list[QueryPlan] = []
            for i, plan_conf in enumerate(q_conf['plans']):
                if not isinstance(plan_conf, dict):
                    raise ValueError(f'Invalid query plan configuration for {qname}.{i}')

                plans.append(QueryPlan.from_config(
                    name=f'{qname}.{i}',
                    config=plan_conf,
                    f=f,
                    reftables=tables,
                ))

            queries[qname] = ReadQueryConfig(
                name=qname,
                f=f,
                plans=plans
            )

        return cls(tables=tables, queries=queries)


@dataclass
class ReadTableConfig:
    name: str
    w: int


@dataclass
class ReadQueryConfig:
    name: str
    f: int
    plans: list[QueryPlan]


@dataclass
class QueryPlan:
    name: str
    tables: list[QueryPlanTable]
    filters: list[QueryPlanFilter] | None = None
    sorts: list[QueryPlanSort] | None = None

    f: int = 1

    @classmethod
    def from_config(
        cls,
        name: str,
        config: dict[str, Any],
        reftables: dict[str, ReadTableConfig] | None = None,
        f: int = 1
    ) -> 'QueryPlan':
        tables: list[QueryPlanTable] = []
        filters: list[QueryPlanFilter] = []
        sorts: list[QueryPlanSort] = []

        for step_name, step_conf in config.items():
            if step_name == 'filter':
                if not isinstance(step_conf, list):
                    raise ValueError(f'Invalid filter configuration for {name}')
                filters.extend([
                    QueryPlanFilter.from_string(filter_conf)
                    for filter_conf in step_conf
                ])
            elif step_name == 'sort':
                if not isinstance(step_conf, list):
                    raise ValueError(f'Invalid sort configuration for {name}')
                sorts.extend([
                    QueryPlanSort.from_string(sort_conf)
                    for sort_conf in step_conf
                ])
            else:
                tblname = step_name
                rest = step_conf if step_conf else {}

                if reftables and tblname in reftables:
                    tbl_conf = reftables[tblname]
                    rest.setdefault('w', tbl_conf.w)

                tables.append(
                    QueryPlanTable(
                        name=tblname,
                        **rest
                    )
                )

        return cls(
            name=name,
            tables=tables,
            filters=filters if filters else None,
            sorts=sorts if sorts else None,
            f=f,
        )

    def calc_cost(self, subcase: Any | None = None) -> Decimal:
        cost = Decimal(0)
        for table in self.tables:
            cost += table.calc_cost(subcase)
        if self.filters:
            for filter in self.filters:
                cost += filter.calc_cost()
        if self.sorts:
            for sort in self.sorts:
                cost += sort.calc_cost()
        return cost * self.f

    def cost_str(self, aliases: dict[str, str] = {}) -> str:
        nparts: dict[str, Decimal] = defaultdict(Decimal)
        const = Decimal(0)

        for table in self.tables:
            coeff, k, c = table.terms()
            nparts[k] += coeff
            const += c
        if self.filters:
            for filter in self.filters:
                const += filter.calc_cost()
        if self.sorts:
            for sort in self.sorts:
                const += sort.calc_cost()

        nparts = {
            k: coeff * self.f for k, coeff in nparts.items()
            if coeff != Decimal(0)
        }

        const = const * self.f
    
        v_str = ' + '.join([
            f'{number_format(coeff, intify=True)}'
            f'N{aliases.get(k, k)}'
            for k, coeff in nparts.items()
        ])

        return (
            f'{v_str} + {number_format(const)}'
            if v_str else number_format(const)
        )


@dataclass(kw_only=True)
class QueryPlanTable:
    name: str
    n: int = 1
    w: int = 1
    n_var: str | None = None

    def calc_cost(self, subcase: Any | None = None) -> Decimal:
        n = self.n
        if self.n_var:
            if subcase is not None:
                n = getattr(subcase, self.n_var, 1) * self.n
            else:
                warn(f'QueryPlanTable has n_var="{self.n_var}" but no subcase provided, defaulting to n={self.n}')
        return calc_table_read_cost(w=self.w, n=n)

    def terms(self) -> tuple[Decimal, str, Decimal]:
        if self.n_var:
            coeff, const = calc_table_read_cost_n(self.w, self.n)
            return (coeff, self.n_var, const)
        else:
            return (Decimal(0), '', calc_table_read_cost(w=self.w, n=self.n))

    def cost_str(self, aliases: dict[str, str] = {}) -> str:
        coeff, varname, const = self.terms()
        terms = []
        if varname and coeff != Decimal(0):
            k = aliases.get(varname, varname)
            terms.append(f'{number_format(coeff, intify=True)}N{k}')
        if const != Decimal(0):
            terms.append(number_format(const))
        return ' + '.join(terms)


@dataclass
class QueryPlanFilter:
    attr: str
    op: Operand
    val: str | None = None

    short_name: str = field(init=False)

    type Operand = Literal['=', '<', '>', '>=', '<=', 'in']

    @classmethod
    def from_string(cls, s: str) -> 'QueryPlanFilter':
        attr, op, value = s.split(maxsplit=2)
        if op not in ('=', '<', '>', '>=', '<=', 'in'):
            raise ValueError(f'Invalid filter string: {s}')
        return cls(
            attr=attr.strip(),
            op=cast(QueryPlanFilter.Operand, op),
            val=value.strip() if value else None
        )

    def __post_init__(self):
        self.short_name = '.'.join(a[0] for a in self.attr.split('.'))

    def calc_cost(self) -> Decimal:
        return Decimal('1')

    def cost_str(self) -> str:
        return '1'


@dataclass
class QueryPlanSort:
    attr: str
    order: Order

    short_name: str = field(init=False)

    type Order = Literal['asc', 'desc']

    @classmethod
    def from_string(cls, s: str) -> 'QueryPlanSort':
        attr, order = s.split(maxsplit=1)
        if order not in ('asc', 'desc'):
            raise ValueError(f'Invalid sort string: {s}')
        return cls(
            attr=attr.strip(),
            order=cast(QueryPlanSort.Order, order)
        )
    
    def __post_init__(self):
        self.short_name = '.'.join(a[0] for a in self.attr.split('.'))

    def calc_cost(self) -> Decimal:
        return Decimal('1')

    def cost_str(self) -> str:
        return '1'


def calc_table_read_cost(w: int, n: int) -> Decimal:
    return (
        + Decimal('0.5') * n
        + Decimal('1') * w
        + Decimal('0.01') * n * w
        + Decimal('5')
    )


def calc_table_read_cost_n(w: int, n: int = 1) -> tuple[Decimal, Decimal]:
    return (
        + Decimal('0.5') * n
        + Decimal('0.01') * w * n
    ), (
        + Decimal('1') * w
        + Decimal('5')
    )
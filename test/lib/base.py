from dataclasses import field
from pathlib import Path
from typing import Any, Literal

from pydantic.dataclasses import dataclass
import yaml

from test.lib.cost import QueryPlan, ReadQueryConfig, ReadTableConfig


@dataclass
class BaseTable(ReadTableConfig):
    p: str | Literal[1] = 1
    r: str | Literal[1] = 1


@dataclass
class BaseQuery(ReadQueryConfig):
    @property
    def plan(self) -> QueryPlan:
        return self.plans[0]
    

@dataclass
class Alias:
    long: str
    mid: str
    short: str


@dataclass
class Aliases:
    aliases: dict[str, Alias]

    longs: dict[str, str] = field(init=False)
    mids: dict[str, str] = field(init=False)
    shorts: dict[str, str] = field(init=False)

    def __post_init__(self):
        self.longs = {name: alias.long for name, alias in self.aliases.items()}
        self.mids = {name: alias.mid for name, alias in self.aliases.items()}
        self.shorts = {name: alias.short for name, alias in self.aliases.items()}


@dataclass
class BaseConfig:
    tables: dict[str, BaseTable]
    queries: dict[str, BaseQuery]
    aliases: Aliases

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> 'BaseConfig':
        tables_data = data.get('tables', {})
        queries_data = data.get('queries', {})
        aliases_data = data.get('aliases', {})

        tables: dict[str, BaseTable] = {
            table_name: BaseTable(
                name=table_name,
                **table_conf
            )
            for table_name, table_conf in tables_data.items()
        }

        queries: dict[str, BaseQuery] = {}
        for qname, q_conf in queries_data.items():
            f = q_conf.get('f', 1)
            plan_conf = q_conf.get('plan', {})
            plan = QueryPlan.from_config(
                name=qname,
                config=plan_conf,
                f=f,
                reftables=tables
            )

            queries[qname] = BaseQuery(
                name=qname,
                f=f,
                plans=[plan]
            )

        aliases = Aliases(aliases=aliases_data)

        return cls(
            tables=tables,
            queries=queries,
            aliases=aliases
        )


def base_config() -> BaseConfig:
    with open(Path(__file__).parent / 'base.yml') as f:
        conf = yaml.safe_load(f)

    return BaseConfig.from_config(conf)

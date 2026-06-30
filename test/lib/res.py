from pathlib import Path
from typing import Any

import pandas as pd
from pydantic.dataclasses import dataclass


type EvolResultConfig = dict[str, EvolResultGroup]


@dataclass
class EvolResultGroup:
    name: str
    plans: dict[str, int]
    data: dict[str, list[OpResultConfig]] | None = None


@dataclass(frozen=True)
class OpResultConfig:
    group: str
    table: str
    op: str

    cost: str | None = None
    subcases: tuple[str, ...] = ()


def evol_result_config(data: Any) -> EvolResultConfig:
    config: EvolResultConfig = {}
    for group_name, group_conf in data.items():
        config[group_name] = EvolResultGroup(
            name=group_name,
            plans=group_conf.get('plans', {}),
            data=group_conf.get('data', None)
        )

    return config


def load_series(files: list[tuple[Path, str]]) -> pd.Series:
    dfs = []
    for file, op in files:
        df = pd.read_csv(
            file,
            usecols=['subcase', 'stage', 'table_name', 'time_s'],
            dtype={
                'subcase': 'category',
                'stage': 'category',
                'table_name': 'category',
                'time_s': float,
            }
        )
        df = df.groupby(['subcase', 'stage', 'table_name'])['time_s'].mean().reset_index()
        df['op'] = op
        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)

    df = df.rename(columns={ 'stage': 'group', 'table_name': 'table' })
    s = df.set_index(['subcase', 'group', 'table', 'op'])['time_s']

    return s
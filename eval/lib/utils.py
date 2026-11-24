from collections.abc import Iterable
from decimal import Decimal
import json
from typing import Any


class RunFilter:
    def __init__(self, pick: Iterable[str] = (), skip: Iterable[str] = ()):
        self.pick: set[str] = set(pick)
        self.skip: set[str] = set(skip)

    def should_run(self, tag: str) -> bool:
        if self.pick and tag not in self.pick:
            return False
        if tag in self.skip:
            return False
        return True


def serialize(value: Any) -> str:
    return json.dumps(value, separators=(',', ':'))


def number_format(
    value: Any,
    precision = 2,
    intify: bool = False, # strip trailing zeros and dot if possible
) -> str:
    if isinstance(value, float):
        if intify and value.is_integer():
            return str(int(value))
        return f'{value:.{precision}f}'.replace('.', ',')
    elif isinstance(value, Decimal):
        if intify and is_integral(value):
            return str(int(value))
        return f'{value:.{precision}f}'.replace('.', ',')
    elif isinstance(value, int):
        return str(value)
    else:
        return str(value)
    

def is_integral(d: Decimal) -> bool:
    return d == d.to_integral_value()
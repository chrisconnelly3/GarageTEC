"""Metric registry. Each MetricDef.fn takes a MetricContext and returns a
list[Metric]. defs/* modules call register() at import time; importing this
module imports them so registration happens once.
"""
from dataclasses import dataclass
from typing import Callable, List, Sequence

from store.models import Metric

# Forward type only; avoid a circular import with context.py at module load.
MetricFn = Callable[[object], List[Metric]]


@dataclass(frozen=True)
class MetricDef:
    name: str
    view: str                 # "face_on" or "down_line"
    contexts: Sequence[str]   # e.g. ("address", "top", "impact")
    fn: MetricFn


REGISTRY: List[MetricDef] = []


def register(metric_def: MetricDef) -> MetricDef:
    REGISTRY.append(metric_def)
    return metric_def


def all_defs() -> List[MetricDef]:
    # Import defs so their register() side-effects populate REGISTRY exactly once.
    from metrics import defs  # noqa: F401  (triggers defs.__init__ imports)
    return list(REGISTRY)

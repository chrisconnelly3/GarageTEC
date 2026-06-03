"""Orchestrator: build a MetricContext for a swing, run every registered metric
def, and REPLACE the swing's metric rows (clear then save) for idempotent
recompute.
"""
from typing import List

from store import repo
from store.models import Metric
from metrics.context import build_context
from metrics.registry import all_defs


def compute_metrics(conn, swing_id: int) -> List[Metric]:
    """Compute and persist all metrics for one swing. Returns the saved list."""
    ctx = build_context(conn, swing_id)
    results: List[Metric] = []
    for metric_def in all_defs():
        try:
            results.extend(metric_def.fn(ctx))
        except Exception:
            # A single metric must never sink the whole recompute; skip + move on.
            # (Pose gaps / missing moments are already guarded inside each fn.)
            continue
    repo.clear_metrics(conn, swing_id)
    repo.save_metrics(conn, swing_id, results)
    return results

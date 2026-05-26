from __future__ import annotations

from pathlib import Path
from typing import Any

from .store import find_experiment


def compare_experiments(root: Path, left_ref: str, right_ref: str) -> dict[str, Any]:
    left = find_experiment(root, left_ref)
    right = find_experiment(root, right_ref)
    if left is None:
        raise ValueError(f"experiment not found: {left_ref}")
    if right is None:
        raise ValueError(f"experiment not found: {right_ref}")
    left_metrics = left.get("metrics", {})
    right_metrics = right.get("metrics", {})
    metric_delta: dict[str, dict[str, float]] = {}
    for key in sorted(set(left_metrics) | set(right_metrics)):
        if key in left_metrics and key in right_metrics:
            try:
                lhs = float(left_metrics[key])
                rhs = float(right_metrics[key])
            except Exception:
                continue
            metric_delta[key] = {"left": lhs, "right": rhs, "delta": rhs - lhs}
    return {
        "left": {"id": left.get("id"), "version": left.get("version"), "title": left.get("title")},
        "right": {"id": right.get("id"), "version": right.get("version"), "title": right.get("title")},
        "metric_delta": metric_delta,
        "left_only_metrics": sorted(set(left_metrics) - set(right_metrics)),
        "right_only_metrics": sorted(set(right_metrics) - set(left_metrics)),
        "left_run_paths": left.get("run_paths", []),
        "right_run_paths": right.get("run_paths", []),
    }

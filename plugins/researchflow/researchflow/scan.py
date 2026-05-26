from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .schema import new_experiment_record, utc_now
from .store import init_project, load_data, load_experiments, rel_path, save_experiment

RUN_MARKERS = {
    "config.json",
    "resolved_config.json",
    "summary.json",
    "train_metrics.jsonl",
    "metrics.json",
    "metrics.csv",
    "val_metrics.csv",
    "val_pair_metrics.csv",
}


def _hash_id(root: Path, run_dir: Path) -> str:
    rel = rel_path(root, run_dir)
    return "EXP-" + hashlib.sha1(rel.encode("utf-8")).hexdigest()[:10].upper()


def _json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return load_data(path)
    except Exception:
        return {}


def _last_jsonl(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    last: dict[str, Any] = {}
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            last = item
    return last


def _csv_summary(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    try:
        with path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
    except Exception:
        return {}
    if not rows:
        return {}
    numeric: dict[str, list[float]] = {}
    for row in rows:
        for key, value in row.items():
            try:
                numeric.setdefault(key, []).append(float(value))
            except Exception:
                pass
    return {f"{key}_mean": sum(values) / len(values) for key, values in numeric.items() if values}


def _flatten_numeric(prefix: str, value: Any, out: dict[str, float]) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        out[prefix] = float(value)
    elif isinstance(value, dict):
        for key, nested in value.items():
            _flatten_numeric(f"{prefix}.{key}" if prefix else str(key), nested, out)


def _version_from_path(run_dir: Path) -> str | None:
    for part in reversed(run_dir.parts):
        if part.startswith("v") and any(char.isdigit() for char in part):
            return part[1:] if re.match(r"^v\d", part) else part
    return None


def _infer_kind(run_dir: Path, config: dict[str, Any], summary: dict[str, Any]) -> str:
    text = " ".join([str(run_dir), str(config.get("name", "")), str(config.get("description", "")), str(summary.get("version", ""))]).lower()
    if "lora" in text:
        return "lora"
    if "refiner" in text or "prv2" in text or "patch" in text:
        return "refiner"
    if "validation" in text or "validate" in text:
        return "validation"
    if "precompute" in text:
        return "precompute"
    return "training"


def _artifact_files(run_dir: Path) -> list[str]:
    patterns = [
        "*.json",
        "*.jsonl",
        "*.csv",
        "*.log",
        "*.png",
        "*.jpg",
        "*.jpeg",
        "*.ipynb",
        "adapter/*",
        "refiner/*",
        "epoch_visuals/**/*",
    ]
    files: set[str] = set()
    for pattern in patterns:
        for path in run_dir.glob(pattern):
            if path.is_file():
                files.add(str(path))
    return sorted(files)


def _find_run_dirs(root: Path, run_roots: list[str]) -> list[Path]:
    found: set[Path] = set()
    for run_root in run_roots:
        base = root / run_root
        if not base.exists():
            continue
        for marker in RUN_MARKERS:
            for path in base.rglob(marker):
                found.add(path.parent)
    return sorted(found)


def _collect_parent_refs(config: dict[str, Any]) -> list[str]:
    refs: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)
        elif isinstance(value, str):
            if "workspace/runs/" in value or "/runs/" in value or value.startswith("runs/"):
                refs.add(value)

    visit(config)
    return sorted(refs)


def scan_runs(root: Path, *, run_roots: list[str] | None = None) -> dict[str, Any]:
    project = init_project(root)
    run_roots = run_roots or list(project.get("run_roots", []))
    existing = {record["id"]: record for record in load_experiments(root) if record.get("id")}
    created = 0
    updated = 0
    skipped = 0
    run_dirs = _find_run_dirs(root, run_roots)
    for run_dir in run_dirs:
        config = _json(run_dir / "resolved_config.json") or _json(run_dir / "config.json")
        summary = _json(run_dir / "summary.json")
        metrics: dict[str, float] = {}
        _flatten_numeric("", summary, metrics)
        _flatten_numeric("last_train", _last_jsonl(run_dir / "train_metrics.jsonl"), metrics)
        metrics.update({f"val_csv.{key}": value for key, value in _csv_summary(run_dir / "val_metrics.csv").items()})
        metrics.update({f"val_pair_csv.{key}": value for key, value in _csv_summary(run_dir / "val_pair_metrics.csv").items()})

        exp_id = _hash_id(root, run_dir)
        record = existing.get(exp_id) or new_experiment_record(exp_id, run_dir.name)
        record["title"] = summary.get("version") or config.get("name") or run_dir.name
        record["version"] = summary.get("version") or config.get("version") or _version_from_path(run_dir)
        record["kind"] = _infer_kind(run_dir, config, summary)
        record["status"] = "completed" if summary else "partial"
        record["run_paths"] = [rel_path(root, run_dir)]
        record["config_paths"] = [rel_path(root, path) for path in (run_dir / "config.json", run_dir / "resolved_config.json") if path.exists()]
        record["summary_paths"] = [rel_path(root, run_dir / "summary.json")] if (run_dir / "summary.json").exists() else []
        record["metric_paths"] = [
            rel_path(root, path)
            for path in (run_dir / "train_metrics.jsonl", run_dir / "val_metrics.csv", run_dir / "val_pair_metrics.csv")
            if path.exists()
        ]
        record["metrics"] = metrics
        record["params"] = {
            "version": record["version"],
            "gpu_id": config.get("gpu_id", config.get("gpu_ids")),
            "model": config.get("model", {}).get("model_id") if isinstance(config.get("model"), dict) else config.get("model"),
        }
        record["parent_run_refs"] = _collect_parent_refs(config)
        record["artifacts"] = [rel_path(root, Path(path)) for path in _artifact_files(run_dir)]
        record["updated_at"] = utc_now()
        save_experiment(root, record)
        if exp_id in existing:
            updated += 1
        else:
            created += 1
    return {"run_dirs": len(run_dirs), "created": created, "updated": updated, "skipped": skipped}

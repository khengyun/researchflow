from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPERIMENT_STATUSES = {
    "planned",
    "running",
    "completed",
    "failed",
    "partial",
    "superseded",
    "merged",
    "unknown",
}

EXPERIMENT_KINDS = {
    "experiment",
    "training",
    "validation",
    "diagnostic",
    "precompute",
    "lora",
    "refiner",
    "ablation",
    "notebook",
    "unknown",
}

EDGE_FIELDS = (
    "parents",
    "merged_from",
    "cites",
    "supersedes",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_id(value: str) -> str:
    return value.strip().upper().replace(" ", "-")


def project_dirs(root: Path) -> dict[str, Path]:
    base = root / ".researchflow"
    return {
        "base": base,
        "experiments": base / "experiments",
        "states": base / "states",
        "prompts": base / "prompts",
        "sessions": base / "sessions",
        "indexes": base / "indexes",
    }


def validate_experiment(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not record.get("id"):
        errors.append("experiment is missing id")
    if record.get("status", "unknown") not in EXPERIMENT_STATUSES:
        errors.append(f"{record.get('id', '<unknown>')}: invalid status {record.get('status')!r}")
    if record.get("kind", "unknown") not in EXPERIMENT_KINDS:
        errors.append(f"{record.get('id', '<unknown>')}: invalid kind {record.get('kind')!r}")
    for field in EDGE_FIELDS:
        value = record.get(field, [])
        if value is None:
            record[field] = []
        elif not isinstance(value, list):
            errors.append(f"{record.get('id', '<unknown>')}: {field} must be a list")
    for field in ("improves", "regresses", "claims", "artifacts", "run_paths", "prompts", "research_states"):
        value = record.get(field, [])
        if value is None:
            record[field] = []
        elif not isinstance(value, list):
            errors.append(f"{record.get('id', '<unknown>')}: {field} must be a list")
    return errors


def new_experiment_record(exp_id: str, title: str) -> dict[str, Any]:
    return {
        "id": exp_id,
        "title": title,
        "version": None,
        "kind": "experiment",
        "status": "planned",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "tags": [],
        "parents": [],
        "merged_from": [],
        "cites": [],
        "supersedes": [],
        "improves": [],
        "regresses": [],
        "claims": [],
        "metrics": {},
        "params": {},
        "artifacts": [],
        "run_paths": [],
        "prompts": [],
        "research_states": [],
        "decision": "",
        "next_steps": [],
        "notes": "",
    }

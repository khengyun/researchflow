from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .schema import project_dirs, utc_now, validate_experiment


def load_data(path: Path) -> dict[str, Any]:
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(f"YAML support requires PyYAML to read {path}") from exc
        data = yaml.safe_load(path.read_text()) or {}
        if not isinstance(data, dict):
            raise ValueError(f"{path} must contain an object")
        return data
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def init_project(root: Path, *, name: str | None = None) -> dict[str, Any]:
    dirs = project_dirs(root)
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    gitignore_path = dirs["base"] / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text("indexes/chroma/\n")
    project_path = dirs["base"] / "project.json"
    if project_path.exists():
        return load_data(project_path)
    project = {
        "name": name or root.name,
        "created_at": utc_now(),
        "version": 1,
        "record_format": "json",
        "description": "ResearchFlow local experiment store.",
        "run_roots": ["workspace/runs", "runs", "outputs", "experiments"],
    }
    write_json(project_path, project)
    return project


def list_record_files(root: Path, collection: str) -> list[Path]:
    dirs = project_dirs(root)
    folder = dirs[collection]
    if not folder.exists():
        return []
    files: list[Path] = []
    for suffix in ("*.json", "*.yaml", "*.yml"):
        files.extend(folder.glob(suffix))
    return sorted(files)


def load_records(root: Path, collection: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in list_record_files(root, collection):
        record = load_data(path)
        record.setdefault("_path", str(path))
        records.append(record)
    return records


def load_experiments(root: Path) -> list[dict[str, Any]]:
    return load_records(root, "experiments")


def experiment_by_id(root: Path) -> dict[str, dict[str, Any]]:
    return {str(record["id"]): record for record in load_experiments(root) if record.get("id")}


def save_experiment(root: Path, record: dict[str, Any]) -> Path:
    errors = validate_experiment(record)
    if errors:
        raise ValueError("; ".join(errors))
    record["updated_at"] = utc_now()
    path = project_dirs(root)["experiments"] / f"{record['id']}.json"
    write_json(path, {key: value for key, value in record.items() if key != "_path"})
    return path


def next_numeric_id(root: Path, prefix: str) -> str:
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    numbers: list[int] = []
    for record in load_records(root, "experiments" if prefix == "EXP" else "states"):
        match = pattern.match(str(record.get("id", "")))
        if match:
            numbers.append(int(match.group(1)))
    return f"{prefix}-{(max(numbers) + 1 if numbers else 1):04d}"


def find_experiment(root: Path, ref: str) -> dict[str, Any] | None:
    ref = ref.strip()
    by_id = experiment_by_id(root)
    if ref in by_id:
        return by_id[ref]
    for record in by_id.values():
        if str(record.get("version", "")) == ref:
            return record
        if ref in [str(path) for path in record.get("run_paths", [])]:
            return record
    return None


def rel_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)

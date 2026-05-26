from __future__ import annotations

from pathlib import Path
from typing import Any

from .lineage import build_graph
from .store import find_experiment, load_experiments


def experiment_markdown(record: dict[str, Any]) -> str:
    lines = [
        f"# {record.get('id')} - {record.get('title') or record.get('version') or 'Untitled'}",
        "",
        f"- Version: `{record.get('version')}`",
        f"- Status: `{record.get('status')}`",
        f"- Kind: `{record.get('kind')}`",
    ]
    for field in ("parents", "merged_from", "cites", "supersedes"):
        values = record.get(field, [])
        if values:
            lines.append(f"- {field}: " + ", ".join(f"`{value}`" for value in values))
    if record.get("run_paths"):
        lines.append("")
        lines.append("## Run Paths")
        lines.extend(f"- `{path}`" for path in record["run_paths"])
    if record.get("metrics"):
        lines.append("")
        lines.append("## Metrics")
        for key, value in sorted(record["metrics"].items())[:80]:
            lines.append(f"- `{key}`: {value}")
    for field in ("improves", "regresses", "claims", "artifacts"):
        values = record.get(field, [])
        if values:
            lines.append("")
            lines.append(f"## {field.replace('_', ' ').title()}")
            lines.extend(f"- {value}" for value in values[:80])
    if record.get("decision"):
        lines.append("")
        lines.append("## Decision")
        lines.append(str(record["decision"]))
    return "\n".join(lines) + "\n"


def show_experiment(root: Path, ref: str) -> str:
    record = find_experiment(root, ref)
    if record is None:
        raise ValueError(f"experiment not found: {ref}")
    return experiment_markdown(record)


def render_index(root: Path) -> str:
    experiments = load_experiments(root)
    lines = ["# ResearchFlow Experiment Index", ""]
    for record in sorted(experiments, key=lambda item: str(item.get("version") or item.get("id"))):
        lines.append(
            f"- `{record.get('id')}` `{record.get('version')}` "
            f"{record.get('status')} {record.get('kind')} - {record.get('title')}"
        )
    return "\n".join(lines) + "\n"


def write_indexes(root: Path) -> dict[str, Any]:
    graph = build_graph(root, write=True)
    index_path = root / ".researchflow" / "indexes" / "experiment_index.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(render_index(root))
    return {"experiments": len(graph["nodes"]), "edges": len(graph["edges"]), "index": str(index_path)}

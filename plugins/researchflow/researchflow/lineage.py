from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import EDGE_FIELDS, project_dirs
from .store import load_experiments, rel_path, write_json


def _run_ref_map(root: Path, experiments: list[dict[str, Any]]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for record in experiments:
        exp_id = str(record.get("id"))
        for run_path in record.get("run_paths", []):
            refs[str(run_path)] = exp_id
            refs[str((root / run_path).resolve())] = exp_id
    return refs


def resolve_parent_refs(root: Path, record: dict[str, Any], ref_map: dict[str, str]) -> list[str]:
    resolved: set[str] = set(record.get("parents", []))
    for ref in record.get("parent_run_refs", []):
        candidates = [ref]
        try:
            candidates.append(str((root / ref).resolve()))
        except Exception:
            pass
        for candidate in candidates:
            for run_ref, exp_id in ref_map.items():
                if candidate == run_ref or run_ref in candidate or candidate in run_ref:
                    if exp_id != record.get("id"):
                        resolved.add(exp_id)
    return sorted(resolved)


def build_graph(root: Path, *, write: bool = True) -> dict[str, Any]:
    experiments = load_experiments(root)
    ref_map = _run_ref_map(root, experiments)
    nodes = []
    edges = []
    for record in experiments:
        exp_id = str(record.get("id"))
        nodes.append(
            {
                "id": exp_id,
                "label": record.get("version") or record.get("title") or exp_id,
                "kind": record.get("kind"),
                "status": record.get("status"),
            }
        )
        parents = resolve_parent_refs(root, record, ref_map)
        for parent in parents:
            edges.append({"source": parent, "target": exp_id, "type": "derived_from"})
        for field in EDGE_FIELDS:
            if field == "parents":
                continue
            for source in record.get(field, []):
                edges.append({"source": str(source), "target": exp_id, "type": field})
    graph = {"nodes": nodes, "edges": edges}
    if write:
        index_dir = project_dirs(root)["indexes"]
        write_json(index_dir / "graph.json", graph)
        (index_dir / "graph.mmd").write_text(render_mermaid(graph) + "\n")
    return graph


def render_mermaid(graph: dict[str, Any]) -> str:
    lines = ["flowchart TD"]
    for node in graph.get("nodes", []):
        label = str(node.get("label") or node.get("id")).replace('"', "'")
        lines.append(f'  {node["id"]}["{label}"]')
    for edge in graph.get("edges", []):
        label = edge.get("type", "")
        lines.append(f'  {edge["source"]} -- "{label}" --> {edge["target"]}')
    return "\n".join(lines)


def trace(root: Path, ref: str) -> dict[str, Any]:
    graph = build_graph(root, write=False)
    incoming: dict[str, list[dict[str, Any]]] = {}
    outgoing: dict[str, list[dict[str, Any]]] = {}
    for edge in graph["edges"]:
        incoming.setdefault(edge["target"], []).append(edge)
        outgoing.setdefault(edge["source"], []).append(edge)
    target = ref
    by_label = {str(node.get("label")): node["id"] for node in graph["nodes"]}
    if target not in {node["id"] for node in graph["nodes"]} and target in by_label:
        target = by_label[target]

    ancestors: list[str] = []
    seen: set[str] = set()

    def walk_back(node: str) -> None:
        for edge in incoming.get(node, []):
            source = edge["source"]
            if source in seen:
                continue
            seen.add(source)
            ancestors.append(source)
            walk_back(source)

    descendants: list[str] = []
    seen_desc: set[str] = set()

    def walk_forward(node: str) -> None:
        for edge in outgoing.get(node, []):
            dest = edge["target"]
            if dest in seen_desc:
                continue
            seen_desc.add(dest)
            descendants.append(dest)
            walk_forward(dest)

    walk_back(target)
    walk_forward(target)
    return {
        "target": target,
        "ancestors": ancestors,
        "descendants": descendants,
        "incoming": incoming.get(target, []),
        "outgoing": outgoing.get(target, []),
    }


def validate_graph(root: Path) -> dict[str, Any]:
    experiments = load_experiments(root)
    ids = [record.get("id") for record in experiments]
    errors: list[str] = []
    duplicates = sorted({exp_id for exp_id in ids if ids.count(exp_id) > 1})
    for exp_id in duplicates:
        errors.append(f"duplicate experiment id: {exp_id}")
    known = {str(exp_id) for exp_id in ids if exp_id}
    graph = build_graph(root, write=False)
    for edge in graph["edges"]:
        if edge["source"] not in known:
            errors.append(f"missing edge source {edge['source']} for {edge['target']}")
        if edge["target"] not in known:
            errors.append(f"missing edge target {edge['target']}")
    for record in experiments:
        for path_value in record.get("run_paths", []) + record.get("config_paths", []) + record.get("summary_paths", []) + record.get("metric_paths", []):
            if not (root / str(path_value)).exists():
                errors.append(f"{record.get('id')}: missing path {path_value}")
    return {"ok": not errors, "errors": errors, "experiments": len(experiments)}

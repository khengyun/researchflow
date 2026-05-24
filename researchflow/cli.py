from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .compare import compare_experiments
from .lineage import build_graph, trace, validate_graph
from .render import show_experiment, write_indexes
from .scan import scan_runs
from .search import search_experiments
from .schema import new_experiment_record, utc_now
from .store import init_project, load_experiments, next_numeric_id, save_experiment
from .vector_search import (
    DEFAULT_VECTOR_MODEL,
    VectorSearchUnavailable,
    build_vector_index,
    vector_index_status,
    vector_search_experiments,
)


def _root(args: argparse.Namespace) -> Path:
    return Path(getattr(args, "root", ".")).resolve()


def cmd_init(args: argparse.Namespace) -> dict[str, Any]:
    project = init_project(_root(args), name=args.name)
    return {"ok": True, "project": project}


def cmd_scan(args: argparse.Namespace) -> dict[str, Any]:
    return scan_runs(_root(args), run_roots=args.run_root)


def cmd_status(args: argparse.Namespace) -> dict[str, Any]:
    root = _root(args)
    init_project(root)
    experiments = load_experiments(root)
    validation = validate_graph(root)
    latest = sorted(experiments, key=lambda item: str(item.get("updated_at", "")), reverse=True)[:5]
    return {
        "root": str(root),
        "experiments": len(experiments),
        "validation_ok": validation["ok"],
        "errors": validation["errors"][:10],
        "vector_index": vector_index_status(root),
        "latest": [
            {
                "id": item.get("id"),
                "version": item.get("version"),
                "status": item.get("status"),
                "kind": item.get("kind"),
            }
            for item in latest
        ],
    }


def cmd_search(args: argparse.Namespace) -> dict[str, Any]:
    return {"results": search_experiments(_root(args), args.query, limit=args.limit)}


def cmd_build_vector_index(args: argparse.Namespace) -> dict[str, Any]:
    try:
        return build_vector_index(
            _root(args),
            model_name=args.model,
            reset=args.reset,
            batch_size=args.batch_size,
        )
    except VectorSearchUnavailable as exc:
        return {"ok": False, "error": str(exc), "install": 'pip install "researchflow[vector]"'}


def cmd_vector_search(args: argparse.Namespace) -> dict[str, Any]:
    try:
        return {
            "ok": True,
            "results": vector_search_experiments(_root(args), args.query, limit=args.limit, model_name=args.model),
        }
    except VectorSearchUnavailable as exc:
        return {"ok": False, "error": str(exc), "install": 'pip install "researchflow[vector]"', "results": []}


def cmd_trace(args: argparse.Namespace) -> dict[str, Any]:
    return trace(_root(args), args.ref)


def cmd_compare(args: argparse.Namespace) -> dict[str, Any]:
    return compare_experiments(_root(args), args.left, args.right)


def cmd_validate(args: argparse.Namespace) -> dict[str, Any]:
    return validate_graph(_root(args))


def cmd_graph(args: argparse.Namespace) -> dict[str, Any]:
    graph = build_graph(_root(args), write=True)
    return {"nodes": len(graph["nodes"]), "edges": len(graph["edges"])}


def cmd_show(args: argparse.Namespace) -> str:
    return show_experiment(_root(args), args.ref)


def cmd_add_exp(args: argparse.Namespace) -> dict[str, Any]:
    root = _root(args)
    init_project(root)
    exp_id = args.id or next_numeric_id(root, "EXP")
    record = new_experiment_record(exp_id, args.title)
    record["version"] = args.version
    record["kind"] = args.kind
    record["status"] = args.status
    record["parents"] = args.parent or []
    path = save_experiment(root, record)
    return {"id": exp_id, "path": str(path)}


def cmd_close_session(args: argparse.Namespace) -> dict[str, Any]:
    root = _root(args)
    init_project(root)
    scan_result = scan_runs(root)
    index_result = write_indexes(root)
    vector_result: dict[str, Any] | None = None
    if getattr(args, "build_vector_index", False):
        try:
            vector_result = build_vector_index(root, model_name=getattr(args, "vector_model", DEFAULT_VECTOR_MODEL))
        except VectorSearchUnavailable as exc:
            vector_result = {"ok": False, "error": str(exc), "install": 'pip install "researchflow[vector]"'}
    validation = validate_graph(root)
    session_id = "SESSION-" + utc_now().replace(":", "").replace("+", "Z")
    session = {
        "id": session_id,
        "created_at": utc_now(),
        "summary": args.summary or "",
        "scan": scan_result,
        "indexes": index_result,
        "vector_index": vector_result,
        "validation": validation,
    }
    session_path = root / ".researchflow" / "sessions" / f"{session_id}.json"
    session_path.write_text(json.dumps(session, indent=2, sort_keys=True) + "\n")
    return {"session": session_id, "path": str(session_path), "validation_ok": validation["ok"], "errors": validation["errors"]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rf", description="ResearchFlow local research experiment manager")
    parser.add_argument("--root", default=".", help="Research project root")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--name")
    init.set_defaults(func=cmd_init)

    scan = sub.add_parser("scan")
    scan.add_argument("--run-root", action="append")
    scan.set_defaults(func=cmd_scan)

    status = sub.add_parser("status")
    status.set_defaults(func=cmd_status)

    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)
    search.set_defaults(func=cmd_search)

    build_vector = sub.add_parser("build-vector-index")
    build_vector.add_argument("--model", default=DEFAULT_VECTOR_MODEL)
    build_vector.add_argument("--batch-size", type=int, default=32)
    build_vector.add_argument("--reset", action="store_true")
    build_vector.set_defaults(func=cmd_build_vector_index)

    vector_search = sub.add_parser("vector-search")
    vector_search.add_argument("query")
    vector_search.add_argument("--limit", type=int, default=10)
    vector_search.add_argument("--model", default=DEFAULT_VECTOR_MODEL)
    vector_search.set_defaults(func=cmd_vector_search)

    similar = sub.add_parser("similar")
    similar.add_argument("query")
    similar.add_argument("--limit", type=int, default=10)
    similar.add_argument("--model", default=DEFAULT_VECTOR_MODEL)
    similar.set_defaults(func=cmd_vector_search)

    trace_parser = sub.add_parser("trace")
    trace_parser.add_argument("ref")
    trace_parser.set_defaults(func=cmd_trace)

    compare = sub.add_parser("compare")
    compare.add_argument("left")
    compare.add_argument("right")
    compare.set_defaults(func=cmd_compare)

    validate = sub.add_parser("validate")
    validate.set_defaults(func=cmd_validate)

    graph = sub.add_parser("build-graph")
    graph.set_defaults(func=cmd_graph)

    show = sub.add_parser("show")
    show.add_argument("ref")
    show.set_defaults(func=cmd_show)

    add_exp = sub.add_parser("add-exp")
    add_exp.add_argument("title")
    add_exp.add_argument("--id")
    add_exp.add_argument("--version")
    add_exp.add_argument("--kind", default="experiment")
    add_exp.add_argument("--status", default="planned")
    add_exp.add_argument("--parent", action="append")
    add_exp.set_defaults(func=cmd_add_exp)

    close = sub.add_parser("close-session")
    close.add_argument("--summary")
    close.add_argument("--build-vector-index", action="store_true")
    close.add_argument("--vector-model", default=DEFAULT_VECTOR_MODEL)
    close.set_defaults(func=cmd_close_session)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = args.func(args)
    if isinstance(result, str):
        print(result, end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

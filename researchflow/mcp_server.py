from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from researchflow.cli import (  # noqa: E402
    cmd_close_session,
    cmd_compare,
    cmd_init,
    cmd_scan,
    cmd_search,
    cmd_status,
    cmd_trace,
    cmd_validate,
)
from researchflow.render import show_experiment  # noqa: E402


class Args:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


def _root(arguments: dict[str, Any]) -> str:
    return str(arguments.get("root") or ".")


def _call(fn: Callable[[Any], Any], **kwargs: Any) -> Any:
    return fn(Args(**kwargs))


def _tool_result(data: Any) -> dict[str, Any]:
    text = data if isinstance(data, str) else json.dumps(data, indent=2, sort_keys=True)
    return {"content": [{"type": "text", "text": text}]}


def tools_list() -> list[dict[str, Any]]:
    schema_root = {"type": "string", "description": "Research project root. Defaults to current working directory."}
    return [
        {
            "name": "status",
            "description": "Show ResearchFlow project status and validation health.",
            "inputSchema": {"type": "object", "properties": {"root": schema_root}},
        },
        {
            "name": "init_project",
            "description": "Initialize .researchflow in the target repo.",
            "inputSchema": {"type": "object", "properties": {"root": schema_root, "name": {"type": "string"}}},
        },
        {
            "name": "scan_runs",
            "description": "Scan run folders and create/update experiment records.",
            "inputSchema": {
                "type": "object",
                "properties": {"root": schema_root, "run_root": {"type": "array", "items": {"type": "string"}}},
            },
        },
        {
            "name": "search_experiments",
            "description": "Search old experiments by text, version, method, config, metric, or artifact.",
            "inputSchema": {
                "type": "object",
                "required": ["query"],
                "properties": {"root": schema_root, "query": {"type": "string"}, "limit": {"type": "integer"}},
            },
        },
        {
            "name": "trace_experiment",
            "description": "Trace ancestors and descendants for an experiment id or version.",
            "inputSchema": {
                "type": "object",
                "required": ["ref"],
                "properties": {"root": schema_root, "ref": {"type": "string"}},
            },
        },
        {
            "name": "compare_experiments",
            "description": "Compare metrics and artifacts between two experiments.",
            "inputSchema": {
                "type": "object",
                "required": ["left", "right"],
                "properties": {"root": schema_root, "left": {"type": "string"}, "right": {"type": "string"}},
            },
        },
        {
            "name": "validate_graph",
            "description": "Validate experiment records, links, and artifact paths.",
            "inputSchema": {"type": "object", "properties": {"root": schema_root}},
        },
        {
            "name": "close_session",
            "description": "Scan runs, rebuild indexes, validate, and write a session record.",
            "inputSchema": {"type": "object", "properties": {"root": schema_root, "summary": {"type": "string"}}},
        },
    ]


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    root = _root(arguments)
    if name == "status":
        return _tool_result(_call(cmd_status, root=root))
    if name == "init_project":
        return _tool_result(_call(cmd_init, root=root, name=arguments.get("name")))
    if name == "scan_runs":
        return _tool_result(_call(cmd_scan, root=root, run_root=arguments.get("run_root")))
    if name == "search_experiments":
        return _tool_result(_call(cmd_search, root=root, query=arguments["query"], limit=int(arguments.get("limit", 10))))
    if name == "trace_experiment":
        return _tool_result(_call(cmd_trace, root=root, ref=arguments["ref"]))
    if name == "compare_experiments":
        return _tool_result(_call(cmd_compare, root=root, left=arguments["left"], right=arguments["right"]))
    if name == "validate_graph":
        return _tool_result(_call(cmd_validate, root=root))
    if name == "close_session":
        return _tool_result(_call(cmd_close_session, root=root, summary=arguments.get("summary")))
    raise ValueError(f"unknown tool: {name}")


def resources_list(root: str = ".") -> list[dict[str, Any]]:
    return [
        {"uri": "researchflow://project", "name": "ResearchFlow project", "mimeType": "application/json"},
        {"uri": "researchflow://graph", "name": "ResearchFlow graph", "mimeType": "application/json"},
        {"uri": "researchflow://indexes/experiment_index.md", "name": "Experiment index", "mimeType": "text/markdown"},
    ]


def read_resource(uri: str, root: str = ".") -> dict[str, Any]:
    base = Path(root)
    if uri == "researchflow://project":
        path = base / ".researchflow" / "project.json"
    elif uri == "researchflow://graph":
        path = base / ".researchflow" / "indexes" / "graph.json"
    elif uri == "researchflow://indexes/experiment_index.md":
        path = base / ".researchflow" / "indexes" / "experiment_index.md"
    elif uri.startswith("researchflow://experiments/"):
        exp_id = uri.rsplit("/", 1)[-1]
        return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": show_experiment(base, exp_id)}]}
    else:
        raise ValueError(f"unknown resource: {uri}")
    text = path.read_text() if path.exists() else ""
    mime = "text/markdown" if path.suffix == ".md" else "application/json"
    return {"contents": [{"uri": uri, "mimeType": mime, "text": text}]}


def prompts_list() -> list[dict[str, Any]]:
    return [
        {"name": "search_prior_work", "description": "Search old experiments before proposing new work."},
        {"name": "plan_experiment", "description": "Plan a new experiment with lineage and success criteria."},
        {"name": "close_research_session", "description": "Close a session by scanning, validating, and summarizing work."},
    ]


def get_prompt(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "search_prior_work":
        text = "Before proposing new work, call search_experiments and find_similar-style queries for prior experiments, failed attempts, related metrics, and cited prompts."
    elif name == "plan_experiment":
        text = "Create a planned experiment record with parents/cites, hypothesis, expected improvements, possible regressions, artifacts to collect, and stop criteria."
    elif name == "close_research_session":
        text = "Run scan_runs, validate_graph, build indexes via close_session, then summarize created/updated experiments and unresolved metadata gaps."
    else:
        raise ValueError(f"unknown prompt: {name}")
    return {"messages": [{"role": "user", "content": {"type": "text", "text": text}}]}


def handle(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params") or {}
    try:
        if method == "initialize":
            result = {
                "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                "serverInfo": {"name": "researchflow", "version": "0.1.0"},
            }
        elif method == "notifications/initialized":
            return None
        elif method == "tools/list":
            result = {"tools": tools_list()}
        elif method == "tools/call":
            result = call_tool(params["name"], params.get("arguments") or {})
        elif method == "resources/list":
            result = {"resources": resources_list()}
        elif method == "resources/read":
            result = read_resource(params["uri"], params.get("arguments", {}).get("root", "."))
        elif method == "prompts/list":
            result = {"prompts": prompts_list()}
        elif method == "prompts/get":
            result = get_prompt(params["name"], params.get("arguments") or {})
        else:
            raise ValueError(f"unsupported method: {method}")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as exc:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": str(exc)}}


def serve_stdio() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        response = handle(json.loads(line))
        if response is not None:
            print(json.dumps(response), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdio", action="store_true")
    args = parser.parse_args()
    if args.stdio:
        serve_stdio()
    else:
        parser.error("only --stdio is supported")


if __name__ == "__main__":
    main()

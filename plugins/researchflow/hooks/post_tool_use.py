from __future__ import annotations

from common import emit, read_payload, run_rf, workspace_from_payload


def main() -> None:
    payload = read_payload()
    root = workspace_from_payload(payload)
    tool_name = str(payload.get("tool_name") or payload.get("toolName") or "")
    if tool_name and tool_name not in {"Bash", "shell", "exec_command", "apply_patch"}:
        emit("ResearchFlow skipped post-tool scan", {"tool": tool_name})
        return
    result = run_rf(root, "scan", timeout=20)
    emit("ResearchFlow scanned changed run artifacts", result)


if __name__ == "__main__":
    main()

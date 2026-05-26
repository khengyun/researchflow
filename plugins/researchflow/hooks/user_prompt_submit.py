from __future__ import annotations

import json

from common import emit, read_payload, run_rf, workspace_from_payload


def has_vector_results(result: dict) -> bool:
    if result.get("returncode") != 0:
        return False
    try:
        payload = json.loads(str(result.get("stdout") or "{}"))
    except Exception:
        return False
    return bool(payload.get("ok") and payload.get("results"))


def main() -> None:
    payload = read_payload()
    root = workspace_from_payload(payload)
    prompt = str(payload.get("prompt") or payload.get("message") or "")
    if len(prompt.strip()) < 4:
        emit("ResearchFlow skipped prompt search")
        return
    result = run_rf(root, "similar", prompt[:500], "--limit", "5", timeout=15)
    if not has_vector_results(result):
        result = run_rf(root, "search", prompt[:500], "--limit", "5", timeout=15)
    emit("ResearchFlow related experiments", result)


if __name__ == "__main__":
    main()

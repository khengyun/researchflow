from __future__ import annotations

from common import emit, read_payload, run_rf, workspace_from_payload


def main() -> None:
    payload = read_payload()
    root = workspace_from_payload(payload)
    summary = str(payload.get("summary") or "Codex session closed.")
    result = run_rf(root, "close-session", "--summary", summary[:1000], timeout=30)
    emit("ResearchFlow session closed", result)


if __name__ == "__main__":
    main()

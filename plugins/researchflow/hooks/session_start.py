from __future__ import annotations

from common import emit, read_payload, run_rf, workspace_from_payload


def main() -> None:
    root = workspace_from_payload(read_payload())
    result = run_rf(root, "status", timeout=15)
    emit("ResearchFlow status loaded", result)


if __name__ == "__main__":
    main()

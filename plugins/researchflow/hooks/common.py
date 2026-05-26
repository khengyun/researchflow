from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def read_payload() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def workspace_from_payload(payload: dict[str, Any]) -> Path:
    for key in ("cwd", "workspace", "workspaceRoot", "root"):
        value = payload.get(key)
        if value:
            return Path(str(value)).resolve()
    return Path.cwd().resolve()


def run_rf(root: Path, *args: str, timeout: int = 30) -> dict[str, Any]:
    plugin_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(plugin_root) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-m", "researchflow.cli", "--root", str(root), *args],
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def emit(message: str, data: dict[str, Any] | None = None) -> None:
    print(json.dumps({"message": message, "data": data or {}}, sort_keys=True))

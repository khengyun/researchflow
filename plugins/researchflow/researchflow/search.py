from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .store import load_experiments


def _text(record: dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, default=str).lower()


def search_experiments(root: Path, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
    terms = [term.lower() for term in re.findall(r"[\w.\-:/]+", query) if term.strip()]
    if not terms:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for record in load_experiments(root):
        haystack = _text(record)
        score = 0
        for term in terms:
            count = haystack.count(term)
            score += count
            if str(record.get("id", "")).lower() == term or str(record.get("version", "")).lower() == term:
                score += 10
        if score:
            scored.append((score, record))
    scored.sort(key=lambda item: (-item[0], str(item[1].get("id", ""))))
    return [
        {
            "id": record.get("id"),
            "version": record.get("version"),
            "title": record.get("title"),
            "status": record.get("status"),
            "kind": record.get("kind"),
            "score": score,
            "run_paths": record.get("run_paths", []),
        }
        for score, record in scored[:limit]
    ]

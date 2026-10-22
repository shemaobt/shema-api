from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.services.internalization_room.canon.kept import CANON_DIR, canon_path

PORTUGUESE_TITLES = CANON_DIR / "ui-labels.pt.json"


def scene_title(pericope_num: str, number: int | None, heading: str, language: str) -> str:
    if language != "pt":
        return heading
    return portuguese_titles().get(pericope_num, {}).get(f"S{number}") or heading


def portuguese_titles() -> dict[str, dict[str, str]]:
    return _portuguese(canon_path(PORTUGUESE_TITLES))


@lru_cache(maxsize=8)
def _portuguese(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    scenes: dict[str, dict[str, str]] = json.loads(path.read_text(encoding="utf-8"))["scenes"]
    return scenes

from __future__ import annotations

from app.services.internalization_room.canon.parse_map import load_map


def scene_ids_for(pericope_num: str) -> list[str]:
    return [f"S{scene.number}" for scene in load_map(pericope_num).scenes]

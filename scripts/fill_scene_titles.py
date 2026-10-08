from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from pathlib import Path

import anthropic

from app.core.served_books import SERVED_BOOKS
from app.services.internalization_room.canon.parse_map import load_book
from app.services.internalization_room.canon.titles import PORTUGUESE_TITLES

Titles = dict[str, dict[str, str]]

HER_MODEL = "claude-opus-4-8"
HER_INSTRUCTION = (
    "You translate short biblical scene titles from English into Brazilian Portuguese for an "
    "oral Bible-translation tool. "
    "Plain, warm, everyday Portuguese at an 8th-grade level (the readers are adults with limited "
    "formal education). "
    "Keep them SHORT noun phrases, faithful to the English — never add or interpret beyond it. "
    "Use Almeida-style proper names (Ester, Jonas, Rute, Noemi, Boaz, Mardoqueu, Assuero). "
    "Reply with ONLY a JSON object of the exact same shape as the input "
    "(pericope → scene id → translated title). No prose, no fences."
)
FENCE = re.compile(r"^```json?\s*|```$")


def missing(listed: dict) -> Titles:
    have = listed.get("scenes", {})
    todo: Titles = {}
    for book in sorted(SERVED_BOOKS):
        for meaning_map in load_book(book):
            done = have.get(meaning_map.pericope_num, {})
            lacking = {
                f"S{scene.number}": scene.title
                for scene in meaning_map.scenes
                if not done.get(f"S{scene.number}")
            }
            if lacking:
                todo[meaning_map.pericope_num] = lacking
    return todo


def with_claude(todo: Titles) -> Titles:
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID", "").strip()
    client = anthropic.Anthropic(
        default_headers={"anthropic-workspace-id": workspace} if workspace else None
    )
    reply = client.messages.create(
        model=HER_MODEL,
        max_tokens=8192,
        thinking={"type": "adaptive"},
        system=HER_INSTRUCTION,
        messages=[{"role": "user", "content": json.dumps(todo, ensure_ascii=False)}],
    )
    text = "".join(block.text for block in reply.content if block.type == "text").strip()
    translated: Titles = json.loads(FENCE.sub("", text).strip())
    return translated


def fill(
    path: Path = PORTUGUESE_TITLES, translate: Callable[[Titles], Titles] = with_claude
) -> int:
    listed = json.loads(path.read_text(encoding="utf-8"))
    todo = missing(listed)
    if not todo:
        print("scene titles: nothing to fill, every scene has one")
        return 0
    translated = translate(todo)
    for pericope_num, scenes in todo.items():
        for scene_id in scenes:
            listed["scenes"].setdefault(pericope_num, {})[scene_id] = translated[pericope_num][
                scene_id
            ].strip()
    path.write_text(json.dumps(listed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"scene titles: filled {sum(len(scenes) for scenes in todo.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(fill())

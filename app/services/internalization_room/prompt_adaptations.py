from __future__ import annotations

from collections.abc import Mapping
from typing import NamedTuple


class Adaptation(NamedTuple):
    key: str
    hers: str
    ours: str
    source: str


HER_FILES: dict[str, str] = {
    "book_panorama": "book_overview_system_prompt.md",
    "coverage_classifier": "classifier_system_prompt.md",
    "validator": "validator_system_prompt.md",
}

ADAPTATIONS: tuple[Adaptation, ...] = (
    Adaptation(
        "book_panorama",
        "quando\nquiserem falar comigo, toquem no círculo; toquem de novo quando terminarem",
        "quando\nquiserem falar comigo, toquem no círculo; toquem de novo quando terminarem",
        "PENDING — K1, asked in ENG-975 (r4:52)",
    ),
)


def adapt(key: str, body: str, rows: tuple[Adaptation, ...]) -> str:
    for row in rows:
        if row.key != key:
            continue
        found = body.count(row.hers)
        if found != 1:
            raise ValueError(f"{key}: her text occurs {found} times, not once: {row.hers!r}")
        body = body.replace(row.hers, row.ours, 1)
    return body


def faults(bodies: Mapping[str, str], rows: tuple[Adaptation, ...]) -> list[str]:
    found = []
    for row in rows:
        if not row.source:
            found.append(f"{row.key}: a row names no source: {row.hers!r}")
        if row.key not in bodies:
            found.append(f"{row.key}: a row for a prompt that does not read her body: {row.hers!r}")
    for key, body in bodies.items():
        try:
            adapt(key, body, rows)
        except ValueError as error:
            found.append(str(error))
    return found

"""normalize participant_register and places enum fields

Revision ID: 20260522_0001
Revises: 20260519_0001
Create Date: 2026-05-22 00:00:00.000000

Backfills `participant_register[*].type`, `participant_register[*].entity_type`,
and `places[*].type` so existing rows match the new StrEnums introduced for
BCD validation (`ParticipantType`, `ParticipantEntityType`, `PlaceType`).

Any out-of-enum value is replaced with a safe default and the original is
preserved alongside as `_legacy_<field>` on the same JSON object. The Pydantic
models use `model_config = {"extra": "allow"}`, so the marker survives reads
without affecting validation. `downgrade()` restores `<field>` from
`_legacy_<field>`.
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision: str = "20260522_0001"
down_revision: str | None = "20260519_0001"
branch_labels: str | None = None
depends_on: str | None = None


VALID_PARTICIPANT_TYPES = {"named", "unnamed", "group", "divine", "role"}
VALID_PARTICIPANT_ENTITY_TYPES = {"person", "person_common", "ambiguous"}
VALID_PLACE_TYPES = {
    "city",
    "country",
    "region",
    "district",
    "empire",
    "village",
    "mountain",
    "valley",
    "river",
    "well",
    "field",
    "road",
    "gate",
    "tower",
    "wall",
    "structure",
    "other",
}

PARTICIPANT_TYPE_DEFAULT = "named"
PARTICIPANT_ENTITY_TYPE_DEFAULT = "person"
PLACE_TYPE_DEFAULT = "other"


def _normalize_list(
    items: object, field: str, valid: set[str], default: str
) -> bool:
    if not isinstance(items, list):
        return False
    changed = False
    for entry in items:
        if not isinstance(entry, dict):
            continue
        current = entry.get(field)
        if current in valid:
            continue
        entry[f"_legacy_{field}"] = current
        entry[field] = default
        changed = True
    return changed


def _restore_legacy_list(items: object) -> bool:
    if not isinstance(items, list):
        return False
    changed = False
    for entry in items:
        if not isinstance(entry, dict):
            continue
        for field in ("type", "entity_type"):
            legacy_key = f"_legacy_{field}"
            if legacy_key in entry:
                entry[field] = entry.pop(legacy_key)
                changed = True
    return changed


def _load_json(value: object) -> object:
    if value is None or isinstance(value, (list, dict)):
        return value
    if isinstance(value, (str, bytes, bytearray)):
        return json.loads(value)
    return value


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, participant_register, places "
            "FROM book_context_documents "
            "WHERE participant_register IS NOT NULL OR places IS NOT NULL"
        )
    ).fetchall()

    for bcd_id, participant_register_raw, places_raw in rows:
        participant_register = _load_json(participant_register_raw)
        places = _load_json(places_raw)

        changed = False
        if isinstance(participant_register, list):
            changed |= _normalize_list(
                participant_register,
                "type",
                VALID_PARTICIPANT_TYPES,
                PARTICIPANT_TYPE_DEFAULT,
            )
            changed |= _normalize_list(
                participant_register,
                "entity_type",
                VALID_PARTICIPANT_ENTITY_TYPES,
                PARTICIPANT_ENTITY_TYPE_DEFAULT,
            )
        if isinstance(places, list):
            changed |= _normalize_list(
                places, "type", VALID_PLACE_TYPES, PLACE_TYPE_DEFAULT
            )

        if changed:
            bind.execute(
                sa.text(
                    "UPDATE book_context_documents "
                    "SET participant_register = :pr, places = :pl "
                    "WHERE id = :id"
                ),
                {
                    "id": bcd_id,
                    "pr": json.dumps(participant_register)
                    if participant_register is not None
                    else None,
                    "pl": json.dumps(places) if places is not None else None,
                },
            )


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, participant_register, places "
            "FROM book_context_documents "
            "WHERE participant_register IS NOT NULL OR places IS NOT NULL"
        )
    ).fetchall()

    for bcd_id, participant_register_raw, places_raw in rows:
        participant_register = _load_json(participant_register_raw)
        places = _load_json(places_raw)

        changed = False
        if isinstance(participant_register, list):
            changed |= _restore_legacy_list(participant_register)
        if isinstance(places, list):
            changed |= _restore_legacy_list(places)

        if changed:
            bind.execute(
                sa.text(
                    "UPDATE book_context_documents "
                    "SET participant_register = :pr, places = :pl "
                    "WHERE id = :id"
                ),
                {
                    "id": bcd_id,
                    "pr": json.dumps(participant_register)
                    if participant_register is not None
                    else None,
                    "pl": json.dumps(places) if places is not None else None,
                },
            )

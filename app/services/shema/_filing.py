"""What the three services of a filed project share: the form read as a project, and the stamp.

OBT-547. A project the mesa's approval files is built from the request's Parte A, and whoever
decides it — the approval that files it, the Admin who confirms it — writes the project onto the
requests it belongs to. Both questions are asked by more than one file, so each has one answer
here.

**The form is read from its frozen document, never from its tables.** The caller hands over the
snapshot the mesa evaluated (``rr_snapshots.document``) as a value, and this file reads the four
things the form carries that a project has a column for: the language's name and code (A1 — the
full variant asks them in two fields, the slim one in a table of names and codes), the place
(A2's *Localização geográfica* on a translation request, A1's *país, região* on the other two),
and the team (A4: a name and a role per row, and never an e-mail). The link's holder joins the
list under the requester's name the form signed with (``tpp_name``), because the platform has
their address and the Admin should not have to type it. Nothing is invented: an absent answer is
an empty field the Admin completes, and the registered name (A0) is the name of last resort for a
project whose language nobody typed.

**Every value is cut to its column**, because a decision the mesa takes must not fail on the
length of a free-text answer the form never bounded.

**The stamp writes the sibling's column and nothing else of it.** ``rr_requests.shema_project_id``
has two writes by its own docstring — the project a member opens from, and this one, when a
link's request gets the project its approval filed — and this file imports no service of the
form's module, for ``_request_notices.py``'s reason: the form's module imports this one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, NamedTuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource_request import RRRequest

#: ``shema_projects``' own widths for the three columns the form fills.
_LANGUAGE_NAME_WIDTH = 200
_LANGUAGE_CODE_WIDTH = 50
_PLACE_WIDTH = 500


class ProposedMember(NamedTuple):
    """One person the form proposes: a row of its team table, or the link's holder."""

    name: str
    role: str
    email: str


class PartA(NamedTuple):
    """The request's Parte A, read as the project it files."""

    language_name: str
    language_code: str
    place: str
    members: tuple[ProposedMember, ...]


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def part_a(document: Mapping[str, Any], *, link_email: str) -> PartA:
    """The project a frozen request document files, and the people it proposes."""
    raw_fields = document.get("fields")
    fields: Mapping[str, Any] = raw_fields if isinstance(raw_fields, Mapping) else {}
    langs = _rows(document.get("langs"))
    first = langs[0] if langs else {}

    language_name = (
        _text(fields.get("lang_name")) or _text(first.get("name")) or _text(fields.get("reg_name"))
    )
    language_code = _text(fields.get("lang_iso")) or _text(first.get("code"))
    place = _text(fields.get("people_location")) or _text(fields.get("tr_location"))

    members = [
        ProposedMember(name=_text(row.get("name")), role=_text(row.get("role")), email="")
        for row in _rows(document.get("team"))
        if _text(row.get("name")) or _text(row.get("role"))
    ]
    if link_email:
        members.append(
            ProposedMember(name=_text(fields.get("tpp_name")), role="", email=link_email.lower())
        )

    return PartA(
        language_name=language_name[:_LANGUAGE_NAME_WIDTH],
        language_code=language_code[:_LANGUAGE_CODE_WIDTH],
        place=place[:_PLACE_WIDTH],
        members=tuple(members),
    )


async def stamp_request(db: AsyncSession, request_id: str, project_id: str) -> None:
    """Point one request with no project at ``project_id``. Staged, never committed."""
    await db.execute(
        update(RRRequest)
        .where(RRRequest.id == request_id, RRRequest.shema_project_id.is_(None))
        .values(shema_project_id=project_id)
    )


async def stamp_link_requests(db: AsyncSession, link_id: str, project_id: str) -> list[str]:
    """Point every request the link sent and no project owns at ``project_id``; answer their ids.

    Every one and not only the approved one: the link stood in for a team that had no project,
    and the team now has one. The link holds at most one open instance, and the project is new,
    so the one-open-per-project index has nothing to collide with.
    """
    ids = list(
        (
            await db.execute(
                select(RRRequest.id)
                .where(RRRequest.request_link_id == link_id, RRRequest.shema_project_id.is_(None))
                .order_by(RRRequest.created_at, RRRequest.id)
            )
        ).scalars()
    )
    if ids:
        await db.execute(
            update(RRRequest).where(RRRequest.id.in_(ids)).values(shema_project_id=project_id)
        )
    return ids

"""Whether a team has already heard the book's panorama for the passage they stand on.

The app asks for `"OV"` at every launch, and the server honoured it every time without
looking at anything: a team reopening the tablet on the passage they were working heard the
whole panorama again before reaching their own passage. The server never inserts a panorama
on its own, so the decision belongs where the request lands — one question, asked once,
before the request is honoured. `create_session` is the only caller.

**Derived, never stored** — `progression`'s rule, and the same one. There is no "seen"
column, counter or event, and there should not be one: a flag would be a second opinion
about what happened, obeyed over the rows that say what happened. A panorama session by
itself cannot answer this: it names the book (`OV-Ruth`) and not the passage the team was
standing on. The session the wooden bead opens *after* the panorama carries both — the
passage the team entered, with `after_panorama` set because the app said which panorama it
came after. That row is what a wordless room writes down when a team has heard the panorama
and gone on, and it is what this reads. It holds because the app names `after_session` only
for the session the bead opens once the panorama has been spoken; the route sets the flag
for any `after_session` without asking what kind of session it was, so an app that chained
passage to passage through it would mark every passage heard. The flag's meaning is on the
column and on the request field.

**Heard means went on.** A panorama session that was opened and never followed into a
passage — the audio never came, the app was closed on the invite — is a request and not a
hearing, and the next launch plays it again. Nothing else can tell the two apart, and
replaying to a team that heard it beats skipping it for a team that did not.

**Once per pericope, as specified, and the objection is not settled here.** The issue
records that the panorama is the book's, so once per passage plays the same thing fourteen
times through Ruth. That is the product owner's call. The rule is `_heard_key` below and
nothing else keys on the passage: once per book is replacing its last clause, and the
docstring there says with what.

**Two tablets of one team** asking in the same moment both find nothing and both play it.
There is no lock, and the second hearing is the outcome a lock would only make rarer.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession


def _heard_key(project_id: str, pericope: str) -> tuple[ColumnElement[bool], ...]:
    """What "once" is scoped to: the team and — today — the passage, which names its book.

    Once per book is the last clause replaced by an ``in_`` over the passages of the
    pericope's book — `load_book` in `canon.parse_map` lists them; `book_of` lives in
    `sessions`, which imports this module, so take the book from the caller rather than
    importing it here. Nothing else moves: `create_session` still resolves where the team
    stands, because a team standing on no passage is still given the panorama. The clause
    is not carried today as a dead predicate beside the exact match — the exact match
    subsumes it, and a ``WHERE`` that lists fourteen passages on every launch to filter
    nothing is a cost paid for a change nobody has asked for yet.
    """
    return (
        IRSession.project_id == project_id,
        IRSession.after_panorama.is_(True),
        IRSession.pericope == pericope,
    )


async def heard_panorama(db: AsyncSession, *, project_id: str | None, pericope: str) -> bool:
    """Whether this team went on from the book's panorama into this passage before.

    A tablet that never said whose it is has no history to read, so nothing was heard.
    """
    if project_id is None:
        return False
    result = await db.execute(
        select(IRSession.id).where(*_heard_key(project_id, pericope)).limit(1)
    )
    return result.scalar_one_or_none() is not None

"""Whether a team has already heard the book's panorama and gone on into the book.

The app asks for `"OV"` at every launch, and the server honoured it every time without
looking at anything: a team reopening the tablet on the passage they were working heard the
whole panorama again before reaching their own passage. The server never inserts a panorama
on its own, so the decision belongs where the request lands — one question, asked before
the request is honoured. `create_session` asks it to decide what the launch is answered
with; the session route asks it again, after the session exists, to decide whether an
opening is written ahead for a panorama. Both only read, and neither writes anything the
other could then read differently.

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

**Once per book.** The panorama is the book's, and once per passage played the same thing
fourteen times through Ruth: a tablet with no mark asked at every launch, and a team that
had gone on into the first passage and finished it sat through the whole book again on the
way to the second. The rule is `_heard_key` below, and nothing else keys on the passage.
What stops a team from hearing it *again on purpose* is not this module: `create_session`
asks it only for the app's automatic launch request, never for a request the team chose.

**Two tablets of one team** asking in the same moment both find nothing and both play it.
There is no lock, and the second hearing is the outcome a lock would only make rarer.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services.internalization_room.canon.parse_map import load_book


def _heard_key(project_id: str, book: str) -> tuple[ColumnElement[bool], ...]:
    """What "once" is scoped to: the team and the book, read as an ``in_`` over the book's
    passages, because the row that records a hearing names the passage the team went on
    into and not the book. The book comes from the caller: `book_of` lives in `sessions`,
    which imports this module. `create_session` still resolves where the team stands,
    because a team standing on no passage is still given the panorama.
    """
    return (
        IRSession.project_id == project_id,
        IRSession.after_panorama.is_(True),
        IRSession.pericope.in_([meaning_map.pericope_num for meaning_map in load_book(book)]),
    )


async def heard_panorama(db: AsyncSession, *, project_id: str | None, book: str) -> bool:
    """Whether this team went on from this book's panorama into one of its passages before.

    A tablet that never said whose it is has no history to read, so nothing was heard.
    """
    if project_id is None:
        return False
    result = await db.execute(select(IRSession.id).where(*_heard_key(project_id, book)).limit(1))
    return result.scalar_one_or_none() is not None

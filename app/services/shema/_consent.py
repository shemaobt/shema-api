"""The consent gate — ``docs/shema.md`` §6.4's second row, and the only reader of three columns.

Prayer requests and needs are shared only with the field leader's explicit authorization (the
ecosystem's ``CLAUDE.md`` §6.2). Three rules hold, and each is a sentence somebody can get
wrong in a way that is invisible until it is published:

* **It is a visibility level, not a published boolean.** ``coordenacao`` is a real
  destination — the people who follow up and support — and not a queue for something
  unpublished. A team in trouble that has not consented to being shared still gets help, so a
  gate that reads *unshared* as *unreachable* would withhold help rather than privacy.
* **Absence of consent is not consent.** ``prayer_visibility`` is nullable with no default and
  no server default, and NULL means ``coordenacao``: nothing has to be written for a request
  to stay private, and something has to be written for it to travel. A migration that
  backfills it to ``rede`` publishes every request in the database, which is why BE-02 wrote
  the column without a default and why :func:`prayer_visibility` — not a column default — is
  where NULL is interpreted.
* **One owner for the gate.** This file is the only reader of ``prayer_requests``,
  ``prayer_visibility`` and ``prayer_requests_audio`` in ``app/services/shema/`` and
  ``app/api/shema/``, and ``tests/test_shema/test_privacy_owners.py`` globs both packages and
  fails on a second one. FE-44's frontend has the same scan test over its own shipped files;
  this is it, on the side that actually holds.

**What this file does not decide.** Whose wall it is, what the entry looks like and how the
needs beside it are gathered belong to BE-09. What is here is the predicate and the two
readers of the text, so that the wall, the export, the ETEN report, the Pulse and the
notification bodies reach the same answer without four copies of it —
*an unauthorized prayer request is absent from all four output paths* being the acceptance
line the delivery plan names for the whole of §8.

**Consent and the sensitive-country rule are two rules and compose.** A request that reaches
the wall still travels inside a shape that withholds the place, because the shape is a
:class:`~app.models.shema_privacy.LeavingShape`. Neither file re-implements the other.

**BE-09 built the rest of the gate here, so it keeps one owner** (``docs/shema.md`` §5.6).
:func:`authorized_requests` is the one assembly of what may leave — the project's request under
its visibility and every need under its own ``prayer_shared`` — and the wall, the Prayer Pulse
and BE-14's export all read it rather than the rows. The two questions the issue added are
answered beside it: **who reads a request nobody authorized** (:data:`PRAYER_AUDIENCE`, applied
to the record by :func:`request_as_read` and to every write of a request or a share by
:func:`refuse_prayer_decisions`), and **what an authorization is attached to** — the
request it was given for, so a new text arriving without one is unauthorized again
(:func:`request_written`, :func:`need_written`) — and the Resource Circle hears of a request
when an applied Pulse puts it on the wall (:func:`newly_shared_request`, OBT-554, OBT-566).
Taking an authorization back is named here too (:func:`withdraws_authorization`, OBT-561),
because *did the team stop sharing* is a question about the gate; the archive owns the erasure.
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Iterable, Mapping, Sequence
from datetime import date
from typing import Any, Final, NamedTuple

from pydantic.alias_generators import to_camel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaPrayerVisibility
from app.db.models.shema_need import ShemaNeed
from app.models.shema import ShemaProjectUpdate
from app.models.shema_need import ShemaNeedWrite
from app.models.shema_prayer import PrayerSource
from app.services.shema._health_audience import HEALTH_AUDIENCE
from app.services.shema._redaction import log_reference

logger = logging.getLogger(__name__)

#: What a project that has said nothing has said. NULL is not *unknown* here — it is the
#: product's own answer, written down once so that no query has to remember it.
DEFAULT_VISIBILITY = ShemaPrayerVisibility.COORDENACAO


def prayer_visibility(project: ShemaProject) -> ShemaPrayerVisibility:
    """How far this project's prayer request may travel, with NULL read as the default.

    The interpretation lives here rather than in a column default because a default is
    written *into the row*: the day somebody backfills it, every request that stayed private
    by saying nothing becomes a request that consented. Reading NULL at the gate keeps the
    silence in the database, where it can still be told apart from a decision.
    """
    return project.prayer_visibility or DEFAULT_VISIBILITY


def reaches_prayer_wall(project: ShemaProject) -> bool:
    """Whether this project's request may leave coordination — FE-44's ``reachesPrayerWall``.

    Every surface that emits prayer text calls this and no surface re-derives it. It is
    deliberately a question about the *project*, not about the text: a request with nothing
    written in it is still governed by the same permission, and answering *no* because the
    string is empty would make the gate agree with the right answer for the wrong reason.
    """
    return prayer_visibility(project) == ShemaPrayerVisibility.REDE


def shared_prayer_text(project: ShemaProject) -> str:
    """The request as it may leave coordination — ``""`` when it may not.

    The gate and the read are one call on purpose. A caller that could ask for the text
    without asking the question is a caller that will, eventually, in a file that is
    forwarded; there is no spelling of this module that returns the column unasked.

    ``""`` and not ``None``: a caller filtering out the empty strings is the shape FE-44's
    export already has, and a ``None`` beside a ``""`` invites a consumer to tell *withheld*
    from *nothing was written*, which is a distinction this function exists not to publish.
    """
    return project.prayer_requests.strip() if reaches_prayer_wall(project) else ""


def shared_prayer_audio(project: ShemaProject) -> str | None:
    """The recording that goes with the request, under the same gate.

    A separate function rather than a field of a tuple because the audio is a storage key
    whose caller has to sign or serve it, and a caller that wants only the text should not
    have to hold one to discard it. ``None`` is *no recording*, which is the column's own
    state and is not a second answer to the consent question.
    """
    return project.prayer_requests_audio if reaches_prayer_wall(project) else None


#: The three columns this file guards, as the names a write carries them under.
REQUEST_TEXT: Final = "prayer_requests"
REQUEST_AUDIO: Final = "prayer_requests_audio"
REQUEST_VISIBILITY: Final = "prayer_visibility"
REQUEST_COLUMNS: Final = (REQUEST_TEXT, REQUEST_VISIBILITY, REQUEST_AUDIO)

#: Who reads a request nobody authorized to leave coordination — **the health assessment's
#: audience, by reference**. The request is raised in the assessment and kept in the record's
#: health tab, and ``coordenacao`` is *the people who follow up and support*: the coordination
#: and the OBT Lab, inside their own scope. ``resourceCircle`` is the wall's own audience and the
#: role that shares with the network, so it reads what the team authorized and nothing else —
#: the reading BE-12 already took for the submission inbox (``read_submission.py``) and FE-44
#: §5.8 for the prayer notice. One list for both, so the two cannot drift.
PRAYER_AUDIENCE: Final = HEALTH_AUDIENCE


class AuthorizedRequest(NamedTuple):
    """One request that may leave coordination — FE-44's ``PrayerRequest`` before its place.

    What the gate lets through and nothing about where the team is: the place is the leaving
    shape's to reduce (``app/models/shema_prayer.py``), so this tuple carries no column the
    sensitive-country rule guards.
    """

    id: str
    project_id: str
    source: PrayerSource
    text: str
    answered: bool
    day: date | None


def _request_day(project: ShemaProject) -> date | None:
    """FE-44's ``healthAssessmentDate || lastUpdated`` — the day an entry is dated by."""
    return project.health_assessment_date or project.last_updated


def authorized_requests(
    project: ShemaProject, needs: Iterable[ShemaNeed]
) -> list[AuthorizedRequest]:
    """Every request of ``project`` that may leave coordination — FE-44's ``buildPrayerRequests``.

    **The one assembly**, so the wall, the Pulse and the export cannot disagree about what is
    authorized: the project's own request under :func:`reaches_prayer_wall`, each need under its
    own ``prayer_shared``. Per request and never per project — a team that shares three needs
    and not the fourth has the fourth absent here whatever the project's visibility says.

    ``needs`` may be every need of the project; the flag is asked again here, so a caller that
    hands in the unshared ones still gets none of them. A request with no text does not leave:
    the recording is not served by any output yet (``docs/shema.md`` §5.6's BE-09 note).
    """
    day = _request_day(project)
    requests: list[AuthorizedRequest] = []
    text = shared_prayer_text(project)
    if text:
        requests.append(
            AuthorizedRequest(
                id=f"{project.id}-pr",
                project_id=project.id,
                source=PrayerSource.FORM,
                text=text,
                answered=False,
                day=day,
            )
        )
    for need in needs:
        if need.project_id != project.id or not need.prayer_shared:
            continue
        description = (need.description or "").strip()
        if description:
            requests.append(
                AuthorizedRequest(
                    id=f"{project.id}-need-{need.id}",
                    project_id=project.id,
                    source=PrayerSource.NEED,
                    text=description,
                    answered=bool(need.prayer_answered),
                    day=day,
                )
            )
    return requests


async def authorized_requests_by_project(
    db: AsyncSession, projects: Sequence[ShemaProject]
) -> dict[str, list[AuthorizedRequest]]:
    """:func:`authorized_requests` for a list of rows the caller's scope already handed over.

    **The name BE-14 reuses**: an export's ``sharedPrayerRequests`` are the texts in here and
    nothing read off the columns. The shared needs are one query for the whole list, filtered by
    the flag in SQL and again in :func:`authorized_requests`; the projects are taken as given,
    because *which* projects is ``_scope.py``'s question and this file does not ask it twice.
    Every project gets an entry, an empty list included.
    """
    ids = [project.id for project in projects]
    shared: dict[str, list[ShemaNeed]] = {project_id: [] for project_id in ids}
    if ids:
        rows = await db.execute(
            select(ShemaNeed)
            .where(ShemaNeed.project_id.in_(ids), ShemaNeed.prayer_shared.is_(True))
            .order_by(ShemaNeed.created_at, ShemaNeed.id)
        )
        for need in rows.scalars():
            shared[need.project_id].append(need)
    return {project.id: authorized_requests(project, shared[project.id]) for project in projects}


def reads_withheld_requests(granted: Collection[str], *, platform_admin: bool) -> bool:
    """Whether a caller holding ``granted`` reads a request nobody authorized.

    The role half only — *which* projects is the scope's, and every read that serves the text
    has already been scoped. An installation admin reads, as they pass every guard here.
    """
    return platform_admin or any(role in granted for role in PRAYER_AUDIENCE)


def request_as_read(project: ShemaProject, *, reads_withheld: bool) -> dict[str, Any]:
    """What the record's three request fields become for this reader — an update, or nothing.

    A reader outside :data:`PRAYER_AUDIENCE` gets ``""`` and no recording for a request that
    has not been authorized, and the whole request once it has been — it is on their wall
    already. The visibility stays: it says the request is kept in coordination, which is the
    withholding made visible and names nothing of what was withheld.
    """
    if reads_withheld or reaches_prayer_wall(project):
        return {}
    return {REQUEST_TEXT: "", REQUEST_AUDIO: None}


def unreadable_request_writes(sent: Collection[str], *, reads_withheld: bool) -> list[str]:
    """The request fields of ``sent`` this reader may not write — sorted, or empty.

    *Não dá para editar o que não se vê*, OBT-528's rule, arriving at the request: a reader
    handed ``""`` for a request kept in coordination would overwrite a text they cannot see, and
    one who set ``rede`` would publish it unseen. So the text, the recording and the
    authorization are written by the audience that reads them, on every record — the role that
    shares with the network does not also decide what the team authorized. Answered from the
    names sent, never from their values, so the refusal is no oracle.
    """
    if reads_withheld:
        return []
    return sorted(set(sent) & set(REQUEST_COLUMNS))


#: A need's authorization, in the client's spelling — the one name a refused batch is given.
NEED_SHARE: Final = "needsItems.prayerShared"


def undecidable_shares(
    creates: Iterable[ShemaNeedWrite],
    updates: Iterable[tuple[ShemaNeed, ShemaNeedWrite]],
    *,
    reads_withheld: bool,
) -> list[str]:
    """``[NEED_SHARE]`` when a needs batch decides a need's authorization this reader may not.

    A need's ``prayer_shared`` is the team's authorization as much as the project's visibility
    is, so the rule of :func:`unreadable_request_writes` holds for it: the role that shares with
    the network does not decide it, in either direction — raising a need already shared, sharing
    one, unsharing one, or keeping one shared over a description it was not given for. **Read
    off the values and not the names**, unlike the request's fields: the console sends a need
    back whole, flag included, and a row that leaves the share where it stood decides nothing —
    refusing the name would refuse the Resource Circle every save of the needs it works. The
    reader already reads every need's flag, so the answer tells them nothing.

    A rewritten description sent without the flag still unshares the need (:func:`need_written`):
    that is the rule withdrawing an authorization given for another text, not the reader
    deciding one.
    """
    if reads_withheld:
        return []
    decided = any(row.prayer_shared for row in creates) or any(
        _decides_share(need, row) for need, row in updates
    )
    return [NEED_SHARE] if decided else []


def _decides_share(need: ShemaNeed, row: ShemaNeedWrite) -> bool:
    """Whether ``row``'s flag leaves ``need`` shared otherwise than the rule would without it.

    Without the flag, :func:`need_written` keeps the stored share or, for a rewritten
    description, withdraws it. A flag that agrees with that is a restatement; one that does not
    is a decision — the flag moving, or ``prayerShared: true`` beside a new description, which is
    the share carried over to a text nobody authorized.
    """
    if "prayer_shared" not in row.model_fields_set:
        return False
    sent = {name: getattr(row, name) for name in row.model_fields_set - {"prayer_shared"}}
    left: bool = need_written(need, sent).get("prayer_shared", need.prayer_shared)
    return row.prayer_shared != left


def authorized_on_create(payload: ShemaProjectUpdate, *, reads_withheld: bool) -> list[str]:
    """The request's authorization, when a create by a reader outside the audience carries it.

    A create shows its author what they type, so the text and the recording are theirs to write
    — OBT-528's exception for the place, for the same reason. The decision to share them is not:
    ``rede`` on a new record is the same decision as on an old one. By value, because the
    console's create sends every field it holds.
    """
    if reads_withheld or payload.prayer_visibility is not ShemaPrayerVisibility.REDE:
        return []
    return [REQUEST_VISIBILITY]


def refuse_prayer_decisions(
    project: ShemaProject, refused: Sequence[str], *, user: User, operation: str
) -> None:
    """Raise ``refused`` as a 403 naming the fields in the client's spelling, and log it.

    One sentence for the three answers above, because the rule is one: the request, the
    recording and every authorization are the coordination's and the OBT Lab's to write.
    """
    if not refused:
        return
    named = [name if "." in name else to_camel(name) for name in refused]
    logger.warning(
        "shema authorization refused: a prayer request or share this reader may not write",
        extra={
            "shema_operation": operation,
            "shema_user_id": user.id,
            "shema_refused_fields": named,
            **log_reference(project),
        },
    )
    raise AuthorizationError(
        f"{', '.join(named)}: only the coordination and the OBT Lab write a prayer request and "
        "decide what is shared with the network"
    )


def request_written(project: ShemaProject, sent: Mapping[str, Any]) -> dict[str, Any]:
    """``sent``, with the authorization withdrawn when the request moves without it.

    **An authorization belongs to the request it was given for, not to the field it sits in.**
    The project holds one request, so the fourth one a team writes lands where the third was —
    and would inherit the third's ``rede`` if nothing said otherwise. The Pulso Mensal writes
    the visibility only when the leader answers it (``app/utils/shema_forms.py``), which is
    exactly that path. So a new text or recording written without the visibility in the same
    write clears it to NULL, which is ``coordenacao``; stating it — the health wizard and the
    console's consent control do — keeps whatever was stated. The media rule, *replacing the
    artifact resets the decision*, applied to the request.

    Only an authorized request is touched: an unauthorized one is already where this puts it,
    and rewriting ``coordenacao`` as NULL would be a trail row about nothing.
    """
    written = dict(sent)
    if REQUEST_VISIBILITY in written or not reaches_prayer_wall(project):
        return written
    moved = (REQUEST_TEXT in written and written[REQUEST_TEXT] != project.prayer_requests) or (
        REQUEST_AUDIO in written and written[REQUEST_AUDIO] != project.prayer_requests_audio
    )
    if moved:
        written[REQUEST_VISIBILITY] = None
    return written


def withdraws_authorization(project: ShemaProject, sent: Mapping[str, Any]) -> bool:
    """Whether ``sent`` takes back the authorization of the request on the wall (OBT-561).

    Read **before** the write lands, off the record as it stands: a request that reaches the
    wall, and a write that **states** a visibility other than ``rede`` — the team stopping the
    sharing. Then every archived Pulse that shared a request is cleaned
    (``_submission_archive.erase_shared_requests``).

    **A new text arriving without a visibility is not a withdrawal**, although
    :func:`request_written` clears the authorization for it: the team did not stop sharing, it
    wrote something new, and nothing it shared before is taken back. Compared with ``==``, not
    ``is``: ``sent`` is a mapping, and a raw ``"rede"`` read as a withdrawal would erase.
    """
    if REQUEST_VISIBILITY not in sent or not reaches_prayer_wall(project):
        return False
    return bool(sent[REQUEST_VISIBILITY] != ShemaPrayerVisibility.REDE)


def need_written(need: ShemaNeed, sent: Mapping[str, Any]) -> dict[str, Any]:
    """:func:`request_written` for a need: a rewritten description is unshared unless restated.

    Only the audience restates: :func:`undecidable_shares` refuses the restatement to anybody
    else before this runs.
    """
    written = dict(sent)
    if "prayer_shared" in written or not need.prayer_shared:
        return written
    if "description" in written and written["description"] != need.description:
        written["prayer_shared"] = False
    return written


def newly_shared_request(project: ShemaProject, before: str) -> bool:
    """Whether the record now shares a request it did not share — the prayer notice's gate.

    Asked **after** a coordinator applied a Pulse (OBT-566), of the record as written, against
    ``before`` — :func:`shared_prayer_text` read just ahead of that write. The record is the one
    truth by then: :func:`request_written` has already given the Pulse's answer to the text it
    came with, so a new text without ``rede`` left the wall rather than borrowing last month's
    authorization, and the wall shows exactly what the network may now read. *Now on the wall
    and not before* is a request the Resource Circle has not heard of — the first share above
    all, which the notice at arrival, before anybody applied anything, could never see.

    **The same request sent again is not news**, and neither is a Pulse that left the wall as it
    was. And the link alone never reaches this: its answer is archived and waits for a
    coordinator, so a leader claiming ``rede`` through the weakest credential in the system
    makes the network hear of nothing until the record agrees.
    """
    now = shared_prayer_text(project)
    return now != "" and now != before

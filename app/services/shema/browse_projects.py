"""The Projetos screen's one query — the list and every facet count, from one set.

``list_projects`` is the scoped collection read and stays exactly that. This is the screen
built on it: four reads to assemble what a card and a facet need, one pass to filter and
count, then order and cut the window.

**The order of the four steps is the DoD's second line.** Scope first, because it is a
``WHERE`` and every later step has to sit on top of it; then the filter *and* the counts
together over the same records, so that neither can be computed from a set the other did not
see; then the sort; and only then the page. A ``LIMIT`` moved up even one step would count a
page instead of a set, and the sidebar would promise results the list does not hold — which is
the exact failure the issue describes as *the sidebar says 12 Critical and the list shows 11*.

**Four reads and not one join, and the reason is shape rather than taste.** A project has
many needs and many media items, so a single joined statement returns the cross product and
the rows have to be regrouped in Python anyway; the aggregate the progress table needs is a
``GROUP BY`` that cannot ride on the same statement as the rows. Each of the three child reads
is keyed on ids that came out of the scoped read, so none of them can reach a project the
caller cannot — the property ``_scope.py`` states as *there is no unscoped query to call*,
held here by there being no id to query with.

**This file names no guarded column.** The redaction is applied by the act of validating a row
into :class:`~app.models.shema_projects.ShemaProjectCard`, which inherits
:class:`~app.models.shema_privacy.LeavingShape` — that is what ``from_attributes`` is for, and
``app/models/shema_privacy.py`` says so. The one guarded question this file does ask, *what may
a search match this project on*, it asks ``_redaction.py``, which is the owner.

**Each card is built for its reader (OBT-528)**, which the caller's
:class:`~app.services.shema._scope.Readership` answers per project: a coordination reader's card
carries the truth, everybody else's the region, and the search and the facets read the card the
reader was given — so a count cannot name a place the card beside it withholds, from anybody.

**And how many are withheld is coordination's, by the count as by the notice (OBT-556).**
``locationsWithheld`` was already ``null`` for a caller who coordinates nothing, and the
``sensitive`` facet gave them the same number. :func:`_facets_as_read` leaves that group out of
their counts, and :func:`_query_as_read` ignores their ``?sensitive=``, whose ``matched`` would
be the number again. The card's own free text is the shape's to withhold, so the card needs
nothing here for it.

**And a team's health is reduced the same way, before anything is counted (OBT-553).** A reader
outside ``_health_audience.HEALTH_READERS`` gets every health field empty on the card
(:func:`_card_as_read`), so the tone, the health score and the *atenção* preset the pass computes
from it cannot say which team is struggling. What the card cannot carry the search must not ask:
:func:`_query_as_read` drops the health filter — ignored, as an unknown preset is, so no value of
it carves out a subset — and turns the health order into the default one, and
:func:`_facets_as_read` leaves the health group out of the counts rather than publish *na* for
every project. Each is the one place its surface is reduced for who reads it beyond the place.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaMediaKind
from app.db.models.shema_media import ShemaMediaItem
from app.db.models.shema_need import ShemaNeed
from app.db.models.shema_progress import ShemaProgressEntry
from app.models.shema_projects import (
    DEFAULT_SORT,
    ShemaFacetCounts,
    ShemaNeedCard,
    ShemaProjectCard,
    ShemaProjectDerived,
    ShemaProjectPage,
    ShemaProjectQuery,
)
from app.services.shema._health_audience import health_as_read
from app.services.shema._redaction import searchable_text, withheld_note
from app.services.shema._scope import Readership, RegionScope
from app.services.shema.list_projects import list_projects
from app.utils.shema_facets import collation_key, filter_projects, sort_records


async def _needs_by_project(db: AsyncSession, ids: list[str]) -> dict[str, list[ShemaNeedCard]]:
    """Every need of every project in ``ids``, grouped — for three facets and two presets.

    Read whole rather than aggregated because the four questions the screen asks of needs
    (*which categories*, *any open*, *any urgent and open*, *any shared or answered for
    prayer*) are four different reductions of the same small set, and four ``GROUP BY``
    statements would be four chances for one of them to be scoped differently from the rest.
    """
    if not ids:
        return {}
    rows = (await db.execute(select(ShemaNeed).where(ShemaNeed.project_id.in_(ids)))).scalars()
    grouped: dict[str, list[ShemaNeedCard]] = defaultdict(list)
    for need in rows:
        grouped[need.project_id].append(ShemaNeedCard.model_validate(need))
    return grouped


async def _projects_with_media(db: AsyncSession, ids: list[str]) -> set[str]:
    """The projects in ``ids`` that hold at least one photo or video with content in it.

    **Content, not authorization.** ``hasMedia`` answers *is there anything on this record*,
    which is what the sidebar's checkbox means; whether an item may be **shared** is
    ``_media_sharing.py``'s question and belongs to a path that shares something. Reading the
    authorization columns here would also make this file a second reader of them, which
    ``tests/test_shema/test_privacy_owners.py`` refuses and is right to.

    A photo counts when it has a stored file *or* a caption, and a video when it has a URL —
    ``hasPhotoContent`` and ``hasVideoContent`` on the frontend, which is where an empty slot
    stops being a photo. Answered as a ``DISTINCT`` over ids rather than by loading the rows:
    the question is a boolean per project and the items are never rendered by this screen.
    """
    if not ids:
        return set()
    has_photo = (ShemaMediaItem.kind == ShemaMediaKind.PHOTO) & (
        ShemaMediaItem.storage_key.is_not(None) | (func.trim(ShemaMediaItem.caption) != "")
    )
    has_video = (ShemaMediaItem.kind == ShemaMediaKind.VIDEO) & (
        ShemaMediaItem.url.is_not(None) & (func.trim(ShemaMediaItem.url) != "")
    )
    stmt = (
        select(ShemaMediaItem.project_id)
        .where(ShemaMediaItem.project_id.in_(ids), or_(has_photo, has_video))
        .distinct()
    )
    return set((await db.execute(stmt)).scalars())


async def _last_progress_dates(db: AsyncSession, ids: list[str]) -> dict[str, date]:
    """The newest progress entry per project — the date staleness is measured from.

    Deliberately not ``shema_projects.last_updated``, which is the Pulse-cycle freshness signal
    the ``recent`` preset reads. Two different questions, kept apart on purpose (FE-44 §7.3):
    *when did the counts last move* and *when did we last hear anything at all*.
    """
    if not ids:
        return {}
    stmt = (
        select(ShemaProgressEntry.project_id, func.max(ShemaProgressEntry.entry_date))
        .where(ShemaProgressEntry.project_id.in_(ids))
        .group_by(ShemaProgressEntry.project_id)
    )
    return dict((await db.execute(stmt)).all())  # type: ignore[arg-type]


#: The facet group that counts the withheld projects — ``locationWithheld`` per card.
SENSITIVE_GROUP = "sensitive"

#: The name the health dimension goes by in the query, the order and the facet counts.
_HEALTH = "health"


def _card_as_read(card: ShemaProjectCard, readership: Readership) -> dict[str, Any]:
    """What this reader may not read on a card, beyond the place — one update, or nothing.

    The place and the card's own free text are the shape's (``LeavingShape.read_by``); a team's
    health is ``_health_audience.py``'s, applied before the pass that filters, counts and derives.
    """
    return health_as_read(card, reads_health=readership.reads_health)


def _query_as_read(query: ShemaProjectQuery, readership: Readership) -> ShemaProjectQuery:
    """What this reader may ask the collection — without what the cards and counts withhold.

    **``sensitive`` is the truth-readers' (OBT-556; the Resource Circle too since OBT-571).** How
    many projects are withheld is told to whoever reads the truth and to nobody else (GATE-04,
    1.3: ``withheld_note``, addressed by ``reads_truth_anywhere``), and a filter on the bit would
    hand everybody else the same number as ``matched``. So for them the filter is **ignored** —
    the list and every other count are what the same request without it answers — rather than
    refused like a value that is no option: an empty list would say *none of these is withheld*,
    which is false, and a link a coordinator saved still opens with its other filters applied.

    **The health filter and order are the health audience's (OBT-553)**, ignored the same way,
    which is what this endpoint already does with a preset it does not know, and the health
    order falls back to the default, as an unknown sort does: the answer is the same whatever
    the teams' health, so neither is an oracle.
    """
    update: dict[str, Any] = {}
    if not readership.reads_truth_anywhere:
        update[SENSITIVE_GROUP] = None
    if not readership.reads_health:
        update["health"] = None
        if query.sort == _HEALTH:
            update["sort"] = DEFAULT_SORT
    return query.model_copy(update=update) if update else query


def _facets_as_read(counts: ShemaFacetCounts, readership: Readership) -> ShemaFacetCounts:
    """The counts this reader may read — without the groups it may not be told.

    The withheld projects' count is the truth-readers' (OBT-556, OBT-571), and the health group
    is the health readers' (OBT-553, OBT-571). A group left out is absent from ``groups`` and from
    ``groupAll`` rather than answered with zeros or ``{"na": total}``, which would be a number
    that lies; the console reads a missing group as one it has nothing to show for. The
    ``locationWithheld`` bit itself stays on every card — GATE-04 decided the notice, not the bit.
    """
    hidden: set[str] = set()
    if not readership.reads_truth_anywhere:
        hidden.add(SENSITIVE_GROUP)
    if not readership.reads_health:
        hidden.add(_HEALTH)
    if not hidden:
        return counts
    return counts.model_copy(
        update={
            "groups": {
                group: options for group, options in counts.groups.items() if group not in hidden
            },
            "group_all": {group: n for group, n in counts.group_all.items() if group not in hidden},
        }
    )


async def _cards(
    db: AsyncSession, projects: list[ShemaProject], readership: Readership
) -> list[ShemaProjectCard]:
    """One card per project, built for its reader, with what a row cannot answer joined in —
    in the order of the name each card carries.

    **That order is the tiebreak of every sort the screen has** (OBT-563). ``sort_records`` is
    stable, so two cards with the same deadline, the same team or no deadline at all keep the
    order they arrived in; had that been the real name, a reader who is not coordination could
    place a sensitive project by its real name from where it sits among its ties. Ordered by the
    name the card carries, a card sits where the name the reader reads puts it.

    The card is validated **off the row**, which is what applies the sensitive-country rule
    without this file naming the flag: a shape that inherits ``LeavingShape`` is redacted by
    the act of being constructed, for the reader it is read by. The four joined values are
    attached afterwards with ``model_copy``, which does not re-run the boundary and keeps the
    reader.
    """
    ids = [project.id for project in projects]
    needs = await _needs_by_project(db, ids)
    with_media = await _projects_with_media(db, ids)
    newest = await _last_progress_dates(db, ids)

    cards = []
    for project in projects:
        reader = readership.reader_of(project.region_key)
        card = ShemaProjectCard.read_by(project, reader)
        cards.append(
            card.model_copy(
                update={
                    "needs": needs.get(project.id, []),
                    "has_media": project.id in with_media,
                    "last_progress_date": newest.get(project.id),
                    "search_text": searchable_text(project, reader),
                    **_card_as_read(card, readership),
                }
            )
        )
    return sorted(cards, key=_by_name_read)


def _by_name_read(card: ShemaProjectCard) -> tuple[bool, tuple[str, str], str]:
    """The name the card carries, blanks last — ``sort_key``'s rule, for its stated reason."""
    name = card.language_name or ""
    return (not name, collation_key(name), card.id)


async def browse_projects(
    db: AsyncSession,
    scope: RegionScope,
    query: ShemaProjectQuery,
    *,
    readership: Readership,
    today: date,
) -> ShemaProjectPage:
    """The Projetos screen's answer: the filtered list, its facet counts and the window.

    ``scope`` is positional and has no default, for ``list_projects``'s stated reason: a
    keyword with a permissive default is how a scope stops being applied. ``today`` is
    injected rather than read here, so the whole path from the request to a staleness band is
    a pure function of a day the caller names — which is what the parity replay pins and what
    lets a test move the calendar without moving the machine.

    With an empty ``query`` this returns the whole scoped collection with its counts, which is
    FE-44 §9.1's frozen default. Every filter, the sort and the window are things a caller asks
    for, and the counts are the one thing it cannot decline: they are computed from the same
    pass as the list, so *never the filter alone* is a property of the return type rather than
    a rule somebody has to follow.

    ``readership`` has no default either: it decides which cards carry the truth, and the one
    caller that shows no place at all (the notification panel) says so with ``NO_COORDINATION``.
    The withheld notice is addressed to the caller — coordination when they coordinate any
    region, and then only (GATE-04) — and so are the count and the filter of the withheld
    projects (OBT-556): one addressee for the three, so they cannot disagree.
    """
    cards = await _cards(db, await list_projects(db, scope), readership)
    query = _query_as_read(query, readership)
    result = filter_projects(cards, query, today)

    window = sort_records(result.visible, query.sort)
    start = query.offset
    stop = None if query.limit is None else start + query.limit
    items = [
        card.model_copy(update={"derived": ShemaProjectDerived.of(derived)})
        for card, derived in window[start:stop]
    ]

    return ShemaProjectPage(
        items=items,
        counts=_facets_as_read(
            ShemaFacetCounts(
                groups={group: dict(options) for group, options in result.counts.groups.items()},
                presets=dict(result.counts.presets),
                group_all=dict(result.counts.group_all),
            ),
            readership,
        ),
        matched=result.matched,
        total=result.total,
        limit=query.limit,
        offset=query.offset,
        sort=query.sort,
        locations_withheld=withheld_note(items, readership.collection_reader),
    )

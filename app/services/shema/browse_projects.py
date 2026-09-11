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
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaMediaKind
from app.db.models.shema_media import ShemaMediaItem
from app.db.models.shema_need import ShemaNeed
from app.db.models.shema_progress import ShemaProgressEntry
from app.models.shema_projects import (
    ShemaFacetCounts,
    ShemaNeedCard,
    ShemaProjectCard,
    ShemaProjectDerived,
    ShemaProjectPage,
    ShemaProjectQuery,
)
from app.services.shema._redaction import searchable_text, withheld_note
from app.services.shema._scope import RegionScope
from app.services.shema.list_projects import list_projects
from app.utils.shema_facets import filter_projects, sort_records


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


async def _cards(db: AsyncSession, projects: list[ShemaProject]) -> list[ShemaProjectCard]:
    """One redacted card per project, with what a row cannot answer joined in.

    The card is validated **off the row**, which is what applies the sensitive-country rule
    without this file naming the flag: a shape that inherits ``LeavingShape`` is redacted by
    the act of being constructed. The four joined values are attached afterwards with
    ``model_copy``, which does not re-run the boundary — and must not, because a payload that
    already carries ``locationWithheld`` is taken at its word (``app/models/shema_privacy.py``
    names that seam).
    """
    ids = [project.id for project in projects]
    needs = await _needs_by_project(db, ids)
    with_media = await _projects_with_media(db, ids)
    newest = await _last_progress_dates(db, ids)

    return [
        ShemaProjectCard.model_validate(project).model_copy(
            update={
                "needs": needs.get(project.id, []),
                "has_media": project.id in with_media,
                "last_progress_date": newest.get(project.id),
                "search_text": searchable_text(project),
            }
        )
        for project in projects
    ]


async def browse_projects(
    db: AsyncSession,
    scope: RegionScope,
    query: ShemaProjectQuery,
    *,
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
    """
    cards = await _cards(db, await list_projects(db, scope))
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
        counts=ShemaFacetCounts(
            groups={group: dict(options) for group, options in result.counts.groups.items()},
            presets=dict(result.counts.presets),
            group_all=dict(result.counts.group_all),
        ),
        matched=result.matched,
        total=result.total,
        limit=query.limit,
        offset=query.offset,
        sort=query.sort,
        locations_withheld=withheld_note(items),
    )

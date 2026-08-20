"""What the facilitator narrowed the queue to, and the order the survivors come back in.

The restriction is answered here rather than by whoever draws the screen. A client filtering
what it was handed is correct only while it was handed everything: the day this route pages,
a screen filtering its page would read "3 teams" over forty that matched, with nothing on it
looking broken. A wrong order is seen; a wrong count is believed.

**It is applied in Python and not in SQL, and the reason is a fact about the data.** The
search covers the passage's human reference — "Ruth 1:1-5" — which is not a column anywhere:
it lives in the vendored canon, in files. One of the four searched fields is not in the
database, so a WHERE clause cannot see it without shipping the canon into every query.

The consequence is worth stating rather than discovering: **this route must not grow
pagination until that is resolved**, because a page restricted after the fact is exactly the
defect the served count was introduced to close, one layer down.
"""

import unicodedata

from app.models.team import FacilitatorTeamView, TeamFilter, TeamState

#: Every dash the canon or a person might write, read as the one a keyboard produces.
_DASHES = str.maketrans({"\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-"})


def folded(value: str) -> str:
    """Text with its case and its accents set aside, for comparing rather than for showing.

    Accents and case belong to how a word is written down, not to what it names. Somebody
    typing at speed does not stop for a tilde and the keyboard in front of them may not carry
    one, so ``kaiwa`` has to find ``Kaiwá``.

    Decomposing and dropping the combining marks does this for every Latin script rather than
    for a list of characters somebody remembered — a table would silently fail on the first
    name nobody thought of, and the names here are exactly the ones nobody thinks of.

    The dashes are folded for the same reason and it is not a flourish: the canon writes a
    passage's range with an en dash (U+2013), and no keyboard in the field types one. A search
    over the reference that can only be satisfied by a character nobody can enter is a search
    that does not work.
    """
    decomposed = unicodedata.normalize("NFD", value.translate(_DASHES))
    return "".join(mark for mark in decomposed if not unicodedata.combining(mark)).lower()


def _matches_search(team: FacilitatorTeamView, search: str) -> bool:
    """A passage is searched by both of its names because the card draws both, and which of
    the two a facilitator remembers is not something this can decide for them."""
    wanted = folded(search.strip())
    if not wanted:
        return True

    return any(
        wanted in folded(written)
        for written in (
            team.name,
            team.mother_tongue,
            team.active_passage.reference,
            team.active_passage.pericope,
        )
    )


def _matches_filter(team: FacilitatorTeamView, chosen: TeamFilter) -> bool:
    if chosen is TeamFilter.ALL:
        return True
    if chosen is TeamFilter.WITH_HANDS:
        return team.open_raised_hands > 0
    if chosen is TeamFilter.IN_PROGRESS:
        return team.state is TeamState.IN_PROGRESS
    if chosen is TeamFilter.STALLED:
        return team.state is TeamState.STALLED
    return team.state is TeamState.COMPLETE


def matching(
    teams: list[FacilitatorTeamView],
    *,
    search: str,
    chosen: TeamFilter,
) -> list[FacilitatorTeamView]:
    """The teams that survive the search **and** the filter.

    The two compose rather than being answered in turn, because the facilitator built one
    question out of them. Two answers left for a screen to intersect is the screen deciding
    again what this already decided.
    """
    return [
        team for team in teams if _matches_search(team, search) and _matches_filter(team, chosen)
    ]


def as_work_queue(teams: list[FacilitatorTeamView]) -> list[FacilitatorTeamView]:
    """Most open hands first, and among teams level on hands the one that spoke most recently.

    A team that has never acted sorts last rather than first. It is the least urgent thing on
    the screen and a null read as "the beginning of time" would put it at the top.
    """
    return sorted(
        teams,
        key=lambda team: (
            -team.open_raised_hands,
            -(team.last_activity_at.timestamp() if team.last_activity_at else float("-inf")),
        ),
    )

"""The Desk's entry screen, as it travels.

The Desk says "team" where this database says "project" (D-16). The word is not translated
here: these are the shapes the route answers with, and the field names are the ones the
Desk's HTTP client reads.

The listing carries three things and they are not the same kind of fact. ``teams`` is a
fact about the **query** — what survived the search and the filter. ``serves_any_team``
and ``open_hands_total`` are facts about the **facilitator**, and they do not narrow with
the restriction. Two empty lists mean opposite things, and nothing inside an empty array
can tell them apart.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class TeamState(StrEnum):
    """Where a team stands on the passage it is working on.

    Three values and no fourth. This is not a score and carries no ranking: a facilitator
    reads it to know who to help next, and the moment it can be ordered it becomes a
    measure of people (P-03).
    """

    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    STALLED = "stalled"


class TeamFilter(StrEnum):
    """The prototype's five pills.

    ``ALL`` is a value rather than the absence of one because the pill is a real choice in
    a single-select group. A filter that was absent on the wire and ``"all"`` on the screen
    would be one decision spelled two ways.
    """

    ALL = "all"
    WITH_HANDS = "with_hands"
    IN_PROGRESS = "in_progress"
    STALLED = "stalled"
    COMPLETE = "complete"


class ActivePassageView(BaseModel):
    """The passage the team is working on, by both the names it is known by.

    Two fields because the card draws both and either is what a facilitator remembers.
    ``pericope`` is the id the rest of the API is addressed by; ``reference`` is what the
    canon calls the passage in human words.
    """

    pericope: str
    reference: str


class FacilitatorTeamView(BaseModel):
    """One row of the work queue — everything the card renders, computed by nobody else.

    ``open_raised_hands`` and ``device_count`` are counts of things to do, never measures
    of a team. ``last_activity_at`` is null for a team that has never met, which is a
    normal state and not a missing value.
    """

    team_id: str
    name: str
    mother_tongue: str
    active_passage: ActivePassageView
    state: TeamState
    open_raised_hands: int
    device_count: int
    last_activity_at: datetime | None


class TeamListingResponse(BaseModel):
    """The restricted list, beside two facts the restriction never touches.

    ``serves_any_team`` is a boolean and ``open_hands_total`` a number because the form
    follows the reader: nothing draws the first, and the browser tab draws the second while
    the Desk is in the background. Deriving either from ``teams`` is the client producing
    what this route owes — and it cannot survive a search that empties the list, because
    then the fact is no longer in the answer at all.
    """

    teams: list[FacilitatorTeamView]
    serves_any_team: bool
    open_hands_total: int

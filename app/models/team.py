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
    #: Null for a team that has closed every passage of the book. That is the end of the walk
    #: and a defined state, not a missing value — ENG-469 draws such a team with its last
    #: passage closed rather than current, which is only expressible if there is no current.
    active_passage: ActivePassageView | None
    state: TeamState
    open_raised_hands: int
    device_count: int
    last_activity_at: datetime | None


class FacilitatorTeamDetail(FacilitatorTeamView):
    """One team at its own address, with the two facts only this route can answer.

    Everything the queue's row carries, because the screen draws all of it, plus two the row
    deliberately does not: they are facts about **one** team, and on a fourteen-row queue they
    would be fourteen answers to a question nobody asked.
    """

    #: Which scene of the active passage the team last actually moved a bead in — `scene:2`,
    #: not `2`, for the reason `ElementCoverage.scene` gives: a client that has to compose a
    #: key composes the wrong one the day the key's shape changes.
    #:
    #: Null in three cases and none of them is a missing value: a team that has moved nothing,
    #: a team at the end of the book that is on no passage at all, and a team whose most recent
    #: movement was on a preservation rule — those belong to the passage and to none of its
    #: scenes.
    #:
    #: "Last moved" and not "first still owed". The two readings disagree exactly when a team
    #: worked a later scene while an earlier one still has beads left, and the field names the
    #: first: it says where they **are**.
    scene_the_team_is_in: str | None = None

    #: How many of the book's passages have met the completion floor.
    #:
    #: **The one count this product allows, and the reason has to live beside it.** It is a
    #: position in the book, not a measure of the team — every other count on every other
    #: surface is forbidden, so without the reason written down this one gets deleted by
    #: somebody who is right about the rule and wrong about the case (ENG-469).
    #:
    #: Counts the floor, not the walk: a passage closed out of order counts, and the team
    #: still stands where the canon's order puts them.
    closed_total: int


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

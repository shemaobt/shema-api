"""The room's two closed vocabularies, kept where both layers can reach them.

``ElementKind`` names what a bead of a passage *is*; ``CoverageStatus`` names how far a team
has taken one. Both are canon vocabulary and both travel on the wire, so the service layer and
the DTO layer each need them — and that is exactly why neither may own them.

**They lived in `services/internalization_room/` and the DTO module imported them from there.**
Importing anything inside a package runs that package's ``__init__``, which imports
``sessions``, which imports ``progression``, which imports the DTO module — back into a module
half-built. The cycle sat there latently for as long as no service on that path needed a DTO,
and ENG-450 was the slice that needed one. `tests/test_app_boots.py` is what now says so out
loud rather than leaving it to import order.

``canon.elements`` and ``coverage`` re-export these names, so every existing caller keeps its
import. That is not tidiness deferred: those are the modules where each enum is *used*, and a
reader following `_RANK` or `elements_of` should not have to leave the file to see the values
they are built on. What moved is where the definition sits, so that nothing below the service
layer has to import the service layer to name a bead.
"""

import enum


class ElementKind(enum.StrEnum):
    SCENE = "scene"
    BEING = "being"
    PLACE = "place"
    OBJECT = "object"
    TIME = "time"
    ABSENCE = "absence"
    PRESERVED = "preserved"


class CoverageStatus(enum.StrEnum):
    NOT_ENCOUNTERED = "not_encountered"
    SURFACED = "surfaced"
    PARTIALLY_ENGAGED = "partially_engaged"
    ENGAGED = "engaged"


class HaltKind(enum.StrEnum):
    """Whether a halt stops the room or only calls somebody over.

    Both were written as ``NEEDS_PERSON`` and no reader could tell them apart. A hard stop
    means the room cannot go on — nothing further lands until a person comes. The retell
    budget running out (ENG-706) refuses nothing: the team may go on telling, and the room
    is asking for a witness. They are different walks for the facilitator, and the Desk had
    one word for both.

    A ``String(16)`` on the row and not a Postgres enum, for the reason ``bridge_mode`` is
    one: a database type is a second place the vocabulary lives and a migration on both
    sides every time it grows a value.
    """

    BLOCKING = "blocking"
    WARNING = "warning"

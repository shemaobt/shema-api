"""The Rhythm's meeting set - GATE-02's answer, as much of it as the server enforces.

GATE-02 ([OBT-388]) closed on 22 and 25/set/2026: **the set is the same in the seven regions**,
so ``shema_meeting_definitions`` is never built (``docs/shema.md`` §5.9, §9.2) and the set lives
here, in code. Of the five encounters the client named, three are meetings the log records:

- ``bimestral_pi_campo`` - International Projects x the field team, every two months;
- ``trimestral_pi_pontes`` - International Projects x the bridge people, every quarter;
- ``semestral_member_care`` - the Member Care debriefing, every six months.

**The other two are not here, and that is the decision rather than an omission.** The Pulso
Mensal is not a meeting: its record is the submission received (BE-12, ``shema_submissions``),
and a second record of *the Pulse arrived* in this log would be a second owner of that fact. The
Celebracao anual is a yearly report (FE-50), not a meeting. Both ids are therefore refused by the
request type, and the refusal names the three that exist.

**Only what the server enforces is kept: the cadence.** The server derives a log's ``period``
from the day and the cadence (``app/utils/shema_derivations.py``), so it has to know the cadence;
titles, icons, attendees, feeds and readiness are the console's ``RITMO_MEETINGS``, and FE-44
§9.0 forbids an endpoint that serves a vocabulary the frontend already has. That is also where
the open question GATE-02 left - who the bridge people are, and whether the health assessment
moves to the bimonthly meeting - lives: nothing here depends on the answer unless it changes a
cadence or the set, and then it is one edit in :data:`MEETING_CADENCES`.

**Two owners of one key, stated because they must agree.** The console compares a log's
``period`` against its own ``periodKey(cadence, today)`` as text, so a cadence written
differently here than in ``RITMO_MEETINGS`` would leave a card *pending* forever with no error.
``tests/test_shema/test_meetings.py`` pins the table below for that reason.

**Every meeting is held per region.** A log's ``scopeKey`` is a ``RegionKey`` or ``global``
(FE-44 §5.4), and ``global`` belonged to the prototype's annual celebration - the one encounter
GATE-02 turned into a report. It stays in :data:`MeetingScopeKey` so that a client sending it is
answered by the service with the reason, rather than by an enum error that does not say why.

[OBT-388]: https://linear.app/shema-obt/issue/OBT-388
"""

from __future__ import annotations

import enum
from typing import Final, Literal, TypeAlias

from app.db.models.shema_enums import ShemaRegionKey
from app.utils.shema_derivations import Cadence


class ShemaMeetingId(enum.StrEnum):
    """The three meetings the Rhythm's log records - the ids OBT-399 suggested to FE-49."""

    BIMESTRAL_PI_CAMPO = "bimestral_pi_campo"
    TRIMESTRAL_PI_PONTES = "trimestral_pi_pontes"
    SEMESTRAL_MEMBER_CARE = "semestral_member_care"


#: Each meeting's cadence - the one fact about a meeting the server needs, because it derives
#: the period from it. Read the module docstring before changing a row: the console holds the
#: same table in ``RITMO_MEETINGS``.
MEETING_CADENCES: Final[dict[ShemaMeetingId, Cadence]] = {
    ShemaMeetingId.BIMESTRAL_PI_CAMPO: Cadence.BIMONTHLY,
    ShemaMeetingId.TRIMESTRAL_PI_PONTES: Cadence.QUARTERLY,
    ShemaMeetingId.SEMESTRAL_MEMBER_CARE: Cadence.SEMIANNUAL,
}

#: The ``scopeKey`` that is not a region. No meeting of the set is held under it.
GLOBAL_SCOPE_KEY: Final = "global"

#: A log's ``scopeKey`` on the wire: one of the seven regions, or ``global``. Not an enum of
#: eight - that would be a second region vocabulary beside ``ShemaRegionKey`` to keep in step.
MeetingScopeKey: TypeAlias = ShemaRegionKey | Literal["global"]

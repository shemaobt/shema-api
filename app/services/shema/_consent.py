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
"""

from __future__ import annotations

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaPrayerVisibility

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

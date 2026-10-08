"""How the room says which **Part** of the rehearsal it is sending the team back to.

The room is wordless. The team is not looking at a label on a screen that says which part is
which — the spoken name is the only address they have, and *"gravem de novo a parte 3"* over a
rehearsal of five parts asks them to work out which one, at the cost of re-recording the wrong
scene.

An address is made of three things and nothing else: the **Frase number** the analyst gave and
the team heard, the part's position among the session's current parts, and the scene's own
title out of the element-label catalogue. Nothing here writes a name. A room that described a
scene in words the map does not use would be putting content about the passage in a team's ears
on our authority, which is the one thing the containment rule forbids.

It lives beside the findings block rather than inside it because it is the only thing in the
room that turns takes and a catalogue into words, and `back_translation.py` is long enough
without a second subject in it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.core.room_enums import ElementKind
from app.db.models.internalization_room import IRSegment, IRSession, IRTake
from app.services.internalization_room.canon.kept import reading_the_canon_of
from app.services.internalization_room.canon.labels import ElementLabelsBroken, labelled_elements
from app.services.internalization_room.languages import FLOOR, room_language

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AddressWords:
    """The fixed words an address is spoken in, in one language.

    Named fields rather than a dictionary of strings, so a mistyped key is a type error here
    and not a `KeyError` on the verdict path in front of a team.

    **The address follows the session's language, `frase` included.** The findings block is not
    an instruction to the Speaker, it is content in the language of the session — the analyst's
    note already arrives in it — and the Speaker echoes what is there. A Portuguese word inside
    a turn spoken in English invites exactly the echo her rule against a voiced line in two
    languages exists to prevent.
    """

    whole: str
    part: str


#: One entry per language of `ROOM_LANGUAGES`, and the two tables here are read together: a
#: language claimed with words but without a scene title would speak its address in one language
#: and name the scene in another, which is the crossing this module exists to prevent.
_WORDS: dict[str, AddressWords] = {
    "pt": AddressWords(whole="a gravação inteira", part="a parte {number}"),
    "en": AddressWords(whole="the whole recording", part="part {number}"),
}


def words_for(language_code: str) -> AddressWords:
    """What this session says an address in, falling back to the floor like every other table."""
    return _WORDS.get(language_code, _WORDS[FLOOR])


@dataclass(frozen=True)
class Addresses:
    """Where each told stretch sits, and the words this session names it in.

    One object because the two travel together or not at all: a map of parts with no words
    cannot be spoken, and words with no map have nothing to say. Handed to `findings_block`,
    which is what puts an address on a finding.
    """

    by_stretch: dict[str, str] = field(default_factory=dict)
    words: AddressWords = _WORDS[FLOOR]

    def part_of(self, segment_id: str | None) -> str:
        return self.by_stretch.get(segment_id or "", "")


def scene_titles(session: IRSession) -> list[str | None]:
    """The passage's scenes in scene order, each named in the language the room is speaking.

    `None` where the catalogue has no title in that language, which is ten of the fourteen
    passages in Portuguese. There is no fallback across languages and none is wanted: an
    English title in a Portuguese session is a sentence the team cannot read.

    **A holed catalogue costs the title, never the room.** `labelled_elements` raises on a
    catalogue of ours being wrong, and that is a 500 — which is the right answer on the screens
    that exist to show labels, and the wrong one here: before this the verdict never read the
    catalogue at all, and a team's session dying over a decoration is a worse failure than a
    verdict that names the part by its number. So the one exception is caught, around the one
    call, and it is logged with its traceback rather than swallowed: a data fault nobody is
    told about is how it stays there.
    """
    try:
        with reading_the_canon_of(session.canon_pin):
            elements = labelled_elements(session.pericope)
    except ElementLabelsBroken:
        logger.exception(
            "element labels are holed for %s; the address loses its titles", session.pericope
        )
        return []
    return [
        element.label_pt if room_language(session.language) == "pt" else element.label_en
        for element in elements
        if element.kind is ElementKind.SCENE
    ]


def addresses_for(
    told: list[IRSegment],
    parts: list[IRTake],
    titles: list[str | None],
    language_code: str,
) -> Addresses:
    """Each told stretch's part, named as the team will hear it, by the stretch's own address.

    **The position, not the stored number.** The tablet numbers its parts from one and the text
    seam declares them from zero, and both mean the same first part: the number the voice says
    is where the part sits among the numbered parts that are current, in the order they are
    handed in (`current_parts`, in `takes.py`). A rehearsal told whole is counted by none of
    it — the tablet sends no number for it, and a session holding one of those *and* numbered
    parts would otherwise hear its first part called the second.

    **The title only where the rehearsal's parts are the map's scenes.** The room directs the
    team to record whole or scene by scene and nothing enforces it: a team that merged two
    scenes and split a third has four parts over three scenes, and part 2 is not scene 2. The
    count is the only guard there is, so the title is said when the counts agree and the
    catalogue holds it in the session's language.
    """
    words = words_for(language_code)
    titled = len([part for part in parts if part.ordinal is not None]) == len(titles)

    told_parts = {stretch.take_id for stretch in told}

    said: dict[str, str] = {}
    position = 0
    for part in parts:
        if part.ordinal is not None:
            position += 1
        if part.id not in told_parts:
            continue
        if part.ordinal is None:
            said[part.id] = words.whole
            continue
        named = words.part.format(number=position)
        title = titles[position - 1] if titled else None
        said[part.id] = f"{named} — {title}" if title else named

    return Addresses(
        by_stretch={
            stretch.id: said[stretch.take_id] for stretch in told if stretch.take_id in said
        },
        words=words,
    )

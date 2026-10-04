"""The Speaker is told which part the team is being sent back to, and in what words.

The room is wordless: the spoken name is the only address the team has. A verdict that says
*record that part again* over a rehearsal of five parts asks a team to work out which one,
and the cost of getting it wrong is a re-recording of the wrong scene.

So every finding reaching the Speaker carries an address — the **Frase number** the analyst
gave and the team heard, and the **Part** that frase's stretch is a slice of, named the way
Marcia's room names it: the scene's own title when the rehearsal's parts are the map's
scenes and the title exists in the session's language, the bare number otherwise, and *a
gravação inteira* for a rehearsal told in one go.

The expected label is assembled here from the catalogue entry and the numbers the fixture
told, never from a literal title and never from the code: a case carrying the title in
quotes would go green on a catalogue that had drifted, which is the one thing it is for.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.internalization_room import IRSegment
from app.services.internalization_room import part_names
from app.services.internalization_room.back_translation import (
    Finding,
    FindingKind,
    closing_block,
    findings_block,
)
from app.services.internalization_room.canon.labels import (
    ElementLabelsBroken,
    labelled_elements,
)
from app.services.internalization_room.languages import ROOM_LANGUAGES
from app.services.internalization_room.part_names import (
    Addresses,
    addresses_for,
    words_for,
)
from app.services.internalization_room.segments import capture_segment, final_segments
from app.services.internalization_room.sessions import get_session
from tests.room_harness import (
    Room,
    ScriptedAnalyst,
    heard_every_part,
    press_terminei,
    rehearsed_in_parts_of,
    room_client,
    the_analyst_is_scripted,
    the_room_speaks,
)
from tests.text_seam_harness import RUNNER_KEY, Analyst, the_app
from tests.text_seam_harness import the_analyst_reads as the_seam_analyst_is_scripted

#: The three-scene passage the catalogue names in Portuguese. Written down because the seam
#: cases and the expected labels both need one passage to stand on, and three scenes is the
#: smallest rehearsal in which a part can be neither the first nor the last.
TITLED = "P02"

SEAM = "/api/internalization-room/text-seam/back-translation"


def _a_passage_with_no_portuguese_titles(scenes: int = 3) -> str:
    """A passage of `scenes` scenes the catalogue has not translated into Portuguese.

    Asked of the catalogue rather than written down. Ten of the fourteen are untranslated
    today and `P03` is one of them, but naming it here would make this case go red on the day
    somebody translates it — which is work being done, not a rule breaking.
    """
    for pericope in (f"P{number:02d}" for number in range(1, 15)):
        scene_labels = [
            element for element in labelled_elements(pericope) if element.key.startswith("scene:")
        ]
        if len(scene_labels) == scenes and all(one.label_pt is None for one in scene_labels):
            return pericope
    pytest.skip(f"every {scenes}-scene passage now has Portuguese scene titles: the rule is moot")


def _scene_title(pericope: str, scene: int, language: str) -> str | None:
    """What the catalogue calls that scene in that language, and nothing else.

    The cases assert against this rather than against the words, so the day a label is
    rewritten they go on holding the rule instead of the sentence it happened to produce.
    """
    for element in labelled_elements(pericope):
        if element.key == f"scene:{scene}":
            return element.label_pt if language == "pt" else element.label_en
    return None


#: Where each of the three prompts fed by `findings_block` puts it, so a case reads the block
#: and never the prompt around it. The meaning map travels in all three and carries the scene
#: titles too, and the templates' own instructions are dashed lines with colons in them: a case
#: reading a brief whole would count eighty-nine findings where there is one, and would pass on
#: a room that named no part at all.
_BLOCK_HEADINGS = (
    "## The findings for ",
    "## What the analyst found",
    "## The finding to verify",
)


def _block(brief: str) -> str:
    """The findings block alone, cut out of a Speaker's, Validator's or check's brief."""
    for heading in _BLOCK_HEADINGS:
        if heading in brief:
            return brief.split(heading, 1)[1].split("\n## ", 1)[0]
    raise AssertionError("neither template heads its findings block any more")


def _addresses(brief: str) -> list[str]:
    """Every address a model was handed this turn, in the order the findings are in."""
    return re.findall(r"^- \w+ \[([^\]]*)\]:", _block(brief), re.M)


def _findings_lines(brief: str) -> list[str]:
    return [line for line in _block(brief).splitlines() if line.startswith("- ")]


#: Neither of these is autouse. The seam cases below double the same two call sites, and a
#: seam case that inherited the room's doubles would be green by the order pytest happened to
#: build its fixtures in rather than by the rule.
@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch) -> ScriptedAnalyst:
    return the_analyst_is_scripted(monkeypatch)


@pytest.fixture()
def room(monkeypatch: pytest.MonkeyPatch) -> Room:
    return the_room_speaks(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _checked(client: httpx.AsyncClient, db: AsyncSession, session_id: str) -> httpx.Response:
    """Press `terminei` over everything the team has told, having played every part."""
    return await press_terminei(client, session_id, report=await heard_every_part(db, session_id))


def _missing(chunk: int, *, where: str | None = None, note: str = "Noemi") -> dict[str, Any]:
    finding: dict[str, Any] = {"kind": "missing", "note": note, "chunk": chunk}
    if where is not None:
        finding["where"] = where
    return finding


def _addition(chunk: int, note: str = "o pedido das noras") -> dict[str, Any]:
    return {"kind": "addition", "note": note, "chunk": chunk}


async def test_a_finding_on_part_two_of_a_three_scene_passage_names_the_scene(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    """The rule at its fullest: the number, the scene's own title, and the frases it carries.

    Three parts over a three-scene passage whose Portuguese titles exist, so the rehearsal's
    parts are the map's scenes by the room's own direction and the title may be said.
    """
    session, _ = await rehearsed_in_parts_of(db_session, [3, 4, 2], pericope=TITLED)
    analyst.readings = [{"findings": [_missing(5)]}]

    answered = await _checked(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    title = _scene_title(TITLED, 2, "pt")
    assert title, "the case needs a passage the catalogue names in Portuguese"
    assert _addresses(room.briefs[-1]) == [f"frase 5 — a parte 2 — {title}, das frases 4 a 7"]


async def test_a_four_part_rehearsal_names_the_part_by_number_alone(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    """The count guard: four parts over three scenes, so part two is not scene two.

    The team merged or split something, and a title read off the number would send them to
    the wrong scene with full confidence. The frases they heard are the address that survives.
    """
    session, _ = await rehearsed_in_parts_of(db_session, [3, 4, 1, 1], pericope=TITLED)
    analyst.readings = [{"findings": [_missing(5)]}]

    answered = await _checked(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    assert _addresses(room.briefs[-1]) == ["frase 5 — a parte 2, das frases 4 a 7"]
    title = _scene_title(TITLED, 2, "pt")
    assert title and title not in _block(room.briefs[-1])


async def test_a_passage_without_portuguese_titles_names_the_number_alone(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    """Ten of the fourteen passages have no Portuguese scene title, and none is borrowed.

    Her own fail-safe rule: a voiced line never mixes languages, so the English title of a
    passage nobody has translated is not a fallback — it is a sentence the team cannot read.
    """
    untitled = _a_passage_with_no_portuguese_titles()
    session, _ = await rehearsed_in_parts_of(db_session, [3, 4, 2], pericope=untitled)
    analyst.readings = [{"findings": [_missing(5)]}]

    answered = await _checked(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    assert _addresses(room.briefs[-1]) == ["frase 5 — a parte 2, das frases 4 a 7"]
    in_english = _scene_title(untitled, 2, "en")
    assert in_english and in_english not in _block(room.briefs[-1])


async def test_a_rehearsal_told_whole_is_the_whole_recording(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    """A rehearsal recorded in one go has no part number and must not be given one."""
    session, _ = await rehearsed_in_parts_of(db_session, [9], pericope=TITLED, told_whole=True)
    analyst.readings = [{"findings": [_missing(5)]}]

    answered = await _checked(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    assert _addresses(room.briefs[-1]) == ["frase 5 — a gravação inteira"]


@pytest.mark.parametrize("language", ROOM_LANGUAGES)
def test_every_language_the_room_speaks_has_its_own_address_words(language: str) -> None:
    """A language the room claims speaks the whole address in itself, or it is not claimed.

    The module says *one entry per language of `ROOM_LANGUAGES`* and nothing held it. A third
    language added to the room with no words of its own falls back to the floor: it would speak
    its address in English while the scene title came back in its own — the crossing this module
    exists to prevent, arriving in silence.

    Asked as *no language borrows another's words* rather than as *this one differs from the
    floor*, because English **is** the floor: the borrowed case and the right case agree there,
    and the borrowing language is the one that would go unmeasured.
    """
    words = words_for(language)

    for shape in (words.frase, words.whole, words.part, words.span, words.one):
        assert shape, f"{language} has no word for part of an address"
    for other in (one for one in ROOM_LANGUAGES if one != language):
        assert words != words_for(other), (
            f"{language} and {other} speak an address in the same words, so one of them is "
            f"borrowing: an unclaimed language falls back to the floor and says it in English"
        )


async def test_a_part_with_no_number_beside_the_scenes_does_not_cost_the_titles(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    """A take with no number is not a scene, so it is not counted against the map either.

    Three numbered parts over a three-scene passage are the map's scenes whatever else the
    session is holding — a rehearsal recorded whole before the team split it, or a mother
    tongue correction — and the title is still the team's own address for that part. Counting
    the unnumbered take against the scenes would drop every title for a reason the team would
    never hear.
    """
    session, _ = await rehearsed_in_parts_of(
        db_session, [2, 3, 4, 2], pericope=TITLED, unnumbered_first=True
    )
    analyst.readings = [{"findings": [_missing(7)]}]

    answered = await _checked(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    title = _scene_title(TITLED, 2, "pt")
    assert title, "the case needs a passage the catalogue names in Portuguese"
    assert _addresses(room.briefs[-1]) == [f"frase 7 — a parte 2 — {title}, das frases 6 a 9"]


async def test_a_whole_recording_beside_numbered_parts_does_not_shift_their_numbers(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    """A rehearsal told whole and then told in parts: part one is still part one.

    The tablet sends `chunk_index` only when it has one, so a session can hold a take with no
    number beside numbered ones, and `takes_of` reads the unnumbered one first. Counted with
    the rest, it would push every part up by one and the room would send the team to record
    the scene after the one it means — the exact defect this slice exists to remove, said with
    full confidence.
    """
    session, _ = await rehearsed_in_parts_of(
        db_session, [2, 3, 4], pericope=TITLED, unnumbered_first=True
    )
    analyst.readings = [{"findings": [_missing(4)]}]

    answered = await _checked(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    assert _addresses(room.briefs[-1]) == ["frase 4 — a parte 1, das frases 3 a 5"]


async def test_a_holed_catalogue_costs_the_title_and_not_the_verdict(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A catalogue of ours being wrong takes the scene's name away, and nothing else.

    Everywhere else a holed catalogue is a 500, and on the screens that exist to show labels
    that is right. Here it is not: before this rule the verdict never read the catalogue at
    all, and a team's session dying over a decoration is a worse failure than a verdict that
    names the part by its number, which the team can still act on.
    """

    def holed(*_: Any, **__: Any) -> list[Any]:
        raise ElementLabelsBroken("P02 scene:2 is labelled but the canon does not serve it")

    monkeypatch.setattr(part_names, "labelled_elements", holed)
    session, _ = await rehearsed_in_parts_of(db_session, [3, 4, 2], pericope=TITLED)
    analyst.readings = [{"findings": [_missing(5)]}]

    answered = await _checked(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    assert _addresses(room.briefs[-1]) == ["frase 5 — a parte 2, das frases 4 a 7"]
    assert room.said, "the room still spoke a verdict"


async def test_an_english_session_names_the_part_in_english(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    """The room speaks the session's language, and the whole bracket goes with it.

    The findings block is not an instruction to the Speaker, it is content in the language of
    the session — the analyst's note already arrives in it — and the Speaker echoes what is
    there. So `frase` is translated with everything else: a Portuguese word inside a turn
    spoken in English is the echo her rule against a voiced line in two languages forbids.
    """
    session, _ = await rehearsed_in_parts_of(db_session, [3, 4, 2], pericope=TITLED, language="en")
    analyst.readings = [{"findings": [_missing(5)]}]

    answered = await _checked(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    title = _scene_title(TITLED, 2, "en")
    assert _addresses(room.briefs[-1]) == [f"sentence 5 — part 2 — {title}, sentences 4 to 7"]
    in_portuguese = _scene_title(TITLED, 2, "pt")
    assert in_portuguese and in_portuguese not in _block(room.briefs[-1])
    assert "frase" not in _block(room.briefs[-1])


async def test_a_part_with_one_frase_says_the_frase(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    """One stretch is one frase, and a range from a number to itself names nothing."""
    session, _ = await rehearsed_in_parts_of(db_session, [3, 4, 1], pericope=TITLED)
    analyst.readings = [{"findings": [_missing(8)]}]

    answered = await _checked(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    title = _scene_title(TITLED, 3, "pt")
    assert _addresses(room.briefs[-1]) == [f"frase 8 — a parte 3 — {title}, da frase 8"]


async def test_a_missing_without_an_address_names_no_part(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    """Missing past everything told: the frase the analyst gave, and no part at all.

    There is no stretch to point at, and the closing already sends the team to the rehearsal
    to record what is still missing. A part named here would send them to record over
    something that is not wrong.
    """
    session, _ = await rehearsed_in_parts_of(db_session, [3, 4, 2], pericope=TITLED)
    analyst.readings = [{"findings": [_missing(9, where="after")]}]

    answered = await _checked(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    assert _addresses(room.briefs[-1]) == ["frase 9"]


async def test_a_missing_after_a_frase_names_the_next_stretches_part(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    """The part is the stretch's, never the frase's: they part company across a boundary.

    A thing missing after frase 3 is missing at the start of stretch 4 (ADR 0007), and
    stretch 4 is the first of part two. The frase stays the number the analyst gave and the
    team heard (ADR 0018), so the two halves of the address name two different parts of the
    rehearsal and both are right.
    """
    session, _ = await rehearsed_in_parts_of(db_session, [3, 4, 2], pericope=TITLED)
    analyst.readings = [{"findings": [_missing(3, where="after")]}]

    answered = await _checked(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    title = _scene_title(TITLED, 2, "pt")
    assert _addresses(room.briefs[-1]) == [f"frase 3 — a parte 2 — {title}, das frases 4 a 7"]


async def test_a_swap_carries_two_addresses_the_addition_first(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    """A swap is one thing for the team and two lines for the Speaker, each with its address."""
    session, _ = await rehearsed_in_parts_of(db_session, [3, 4, 2], pericope=TITLED)
    analyst.readings = [{"findings": [_missing(5), _addition(5)]}]

    answered = await _checked(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    title = _scene_title(TITLED, 2, "pt")
    lines = _findings_lines(room.briefs[-1])
    assert len(lines) == 2
    assert lines[0].startswith(f"- addition [frase 5 — a parte 2 — {title}, das frases 4 a 7]:")
    assert lines[1].startswith(f"- missing [frase 5 — a parte 2 — {title}, das frases 4 a 7]:")


async def test_the_validator_is_handed_the_same_address(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    """The Validator judges the draft against the finding, so it reads the address too.

    Shown a draft naming a part the Validator had never been told about, the gate would
    refuse a verdict for saying exactly what the room asked it to say.
    """
    session, _ = await rehearsed_in_parts_of(db_session, [3, 4, 2], pericope=TITLED)
    analyst.readings = [{"findings": [_missing(5)]}]

    answered = await _checked(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    assert room.judged, "the Validator ran"
    title = _scene_title(TITLED, 2, "pt")
    assert _addresses(room.briefs[-1]) == [f"frase 5 — a parte 2 — {title}, das frases 4 a 7"]
    assert _addresses(room.judged[-1]) == _addresses(room.briefs[-1])


def test_the_speakers_closings_call_it_the_final_draft_never_the_final_translation() -> None:
    """The Refine-stage boundary, at the Speaker's mouth rather than the Guide's.

    §4 of the doctrine holds that the first rehearsal is the first oral draft and never the
    final translation. The Guide's prompt was the only mouth a test watched, and the verdict's
    closing is the second: it is the one that tells a team their passage is done, and a team
    told they have a final translation has been told the check they are owed already happened.

    Asked of `closing_block` on each of the branches it decides between, not of the constants
    by name: what the boundary has to survive is every ending the room can order, and a sweep
    over module attributes would be a case reading our variable names. What each branch
    *returns* is not asserted — two closings converging is a product decision, not a
    regression — only that none of them promises the team a finished translation.
    """
    on_a_stretch = Finding(kind=FindingKind.MISSING, note="Noemi", segment_id="trecho-1", chunk=1)
    off_every_stretch = Finding(kind=FindingKind.MISSING, note="Noemi", chunk=9)
    unclear = Finding(kind=FindingKind.UNCLEAR, note="não deu para ouvir", segment_id="trecho-1")

    ordered = {
        "checked": closing_block(None, checked=True),
        "clean": closing_block(None, checked=False),
        "on a stretch": closing_block(on_a_stretch),
        "off every stretch": closing_block(off_every_stretch),
        "unclear": closing_block(unclear),
    }

    assert "final draft" in ordered["checked"]
    for named, closing in ordered.items():
        assert "final translation" not in closing.lower(), named
        assert "tradução final" not in closing.lower(), named


def test_a_finding_from_before_the_frase_number_existed_leaves_that_slot_out() -> None:
    """A stored finding with no frase number keeps its part and loses only the frase.

    `chunk` was added after rows were already being written, and a session resumed across the
    change revalidates its stored findings on every request. The number cannot be recovered —
    nothing says which position the analyst gave — so the slot is left out rather than filled
    with a guess, and the part, which the stretch still knows, is said anyway: half an address
    sends the team somewhere, and a frase number invented here sends them to the wrong frase.

    Both halves of the branch, because the row may also have lost its stretch: with neither,
    the line is the kind and the note exactly as it read before this rule.
    """
    on_a_stretch = Finding(kind=FindingKind.MISSING, note="Noemi", segment_id="trecho-5")
    off_every_stretch = Finding(kind=FindingKind.MISSING, note="Noemi")
    addresses = Addresses({"trecho-5": "a parte 2, das frases 4 a 7"}, words_for("pt"))

    assert on_a_stretch.chunk is None and off_every_stretch.chunk is None

    assert findings_block([on_a_stretch], addresses) == (
        "- missing [a parte 2, das frases 4 a 7]: Noemi"
    )
    assert findings_block([off_every_stretch], addresses) == "- missing: Noemi"


def test_a_finding_on_a_part_that_is_no_longer_one_names_the_frase_alone() -> None:
    """A stretch whose part is gone gets no name, and neither end falls over.

    The audio a retired take names is gone: nobody can be sent back to it, so the part slot is
    empty and the frase the team heard stands alone. ENG-864 clears the findings of a part
    recorded again, so this should not reach a team — which is exactly why it is written down
    rather than left to whatever a lookup happens to do on a key that is not there.

    Asked of both ends, because the emptiness has to survive twice: the stretch must go
    unnamed where the names are built, and the line must leave the slot out where it is
    written. A name minted for a part nobody has would travel straight through the second.
    """
    gone = IRSegment(
        id="trecho-sumido",
        session_id="sessao-1",
        take_id="parte-que-sumiu",
        ordinal=1,
        starts_ms=0,
        ends_ms=1000,
        transcript="a frase 5",
    )

    assert addresses_for([gone], [], [None, None, None], "pt", superseded=[]).by_stretch == {}

    finding = Finding(kind=FindingKind.MISSING, note="Noemi", segment_id=gone.id, chunk=5)
    elsewhere = Addresses({"outro": "a parte 1, das frases 1 a 3"}, words_for("pt"))

    assert findings_block([finding], elsewhere) == "- missing [frase 5]: Noemi"


@pytest.fixture()
def seam_analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    return the_seam_analyst_is_scripted(monkeypatch)


@pytest.fixture()
def seam_room(monkeypatch: pytest.MonkeyPatch) -> Room:
    """The room's own collector, over the seam: the Speaker's brief is the same brief."""
    return the_room_speaks(monkeypatch)


@pytest.fixture()
async def seam_client(
    db_session: AsyncSession,
    seam_analyst: Analyst,
    seam_room: Room,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    async with httpx.AsyncClient(
        transport=ASGITransport(app=the_app(db_session)),
        base_url="http://test",
        headers={"X-Access-Code": RUNNER_KEY},
    ) as door:
        yield door


async def _seam_session(client: httpx.AsyncClient, keys: list[str]) -> str:
    declared = await client.post(
        f"{SEAM}/session",
        json={
            "pericopeId": TITLED,
            "language": "Brazilian Portuguese",
            "clips": [{"key": key, "durationMs": 20000} for key in keys],
        },
    )
    assert declared.status_code == 200, declared.text
    return str(declared.json()["sessionId"])


def _frase(key: str, text: str, **extra: Any) -> dict[str, Any]:
    return {"clipKey": key, "coversFrom": 0, "coversTo": 10, "text": text, **extra}


async def test_the_seam_declares_parts_from_one(
    seam_client: httpx.AsyncClient,
    seam_analyst: Analyst,
    seam_room: Room,
) -> None:
    """The seam numbers its parts from zero and the team still hears *a parte 1*.

    A part's number in a voiced line is its position among the current parts, never the
    ordinal as stored: the tablet counts from one and the seam from zero, and both mean the
    same first part. The finding sits on the first clip on purpose — that is the part whose
    ordinal is `0`, which a room reading the number for truth would hand the team as the
    whole recording, and a room passing it through would hand them *a parte 0*.
    """
    session_id = await _seam_session(seam_client, ["S1", "S2", "S3"])
    seam_analyst.readings = [{"findings": [_missing(1)]}]

    played = await seam_client.post(
        f"{SEAM}/round",
        json={
            "sessionId": session_id,
            "frases": [
                _frase("S1", "a primeira frase"),
                _frase("S2", "a segunda frase"),
                _frase("S3", "a terceira frase"),
            ],
        },
    )

    assert played.status_code == 200, played.text
    title = _scene_title(TITLED, 1, "pt")
    assert _addresses(seam_room.briefs[-1]) == [f"frase 1 — a parte 1 — {title}, da frase 1"]


async def test_the_correction_check_reads_the_address(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    """The check that asks whether a retelling mended the finding sees the same address.

    It is shown the finding and the two tellings; shown a finding with no address while the
    Speaker had one, the two would be reading different sentences about the same stretch.
    """
    session, _ = await rehearsed_in_parts_of(db_session, [3, 4, 2], pericope=TITLED)
    analyst.readings = [{"findings": [_missing(5)]}]
    await _checked(client, db_session, session.id)

    told = await final_segments(db_session, session.id)
    fresh = await get_session(db_session, session.id)
    await capture_segment(
        db_session,
        fresh,
        take_id=told[4].take_id,
        starts_ms=told[4].starts_ms,
        ends_ms=told[4].ends_ms,
        bridge_take_id="retro-de-novo",
        transcript="a frase 5, contada outra vez, com Noemi",
        replaces=told[4],
    )

    answered = await _checked(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    assert analyst.verifications, "the correction check ran"
    title = _scene_title(TITLED, 2, "pt")
    assert _addresses(analyst.verifications[-1]) == [
        f"frase 5 — a parte 2 — {title}, das frases 4 a 7"
    ]

import asyncio
from types import SimpleNamespace

import pytest

from app.api.internalization_room import passages as route
from app.core.exceptions import ValidationError
from app.core.room_enums import ElementKind
from app.services.internalization_room import passage_lines
from app.services.internalization_room.canon.book_material import require_walkable
from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.canon.labels import labelled_elements
from app.services.internalization_room.canon.parse_map import (
    SURVEYED_STATUS,
    load_book,
    load_map,
)
from app.services.internalization_room.languages import FLOOR, ROOM_LANGUAGES
from app.services.internalization_room.passage_lines import (
    PANORAMA,
    _sections,
    line_for,
    panorama_line_for,
)

NAMED_IN_PORTUGUESE: dict[str, str] = {
    "P01": "Rute 1:1–5",
    "P02": "Rute 1:6–14",
    "P03": "Rute 1:15–18",
    "P04": "Rute 1:19–22",
    "P05": "Rute 2:1–7",
    "P06": "Rute 2:8-16",
    "P07": "Rute 2:17-23",
    "P08": "Rute 3:1-5",
    "P09": "Rute 3:6-13",
    "P10": "Rute 3:14-18",
    "P11": "Rute 4:1-8",
    "P12": "Rute 4:9-12",
    "P13": "Rute 4:13-17",
    "P14": "Rute 4:18-22",
}

NAMED_IN_ENGLISH: dict[str, str] = {
    "P01": "Ruth 1:1–5",
    "P02": "Ruth 1:6–14",
    "P03": "Ruth 1:15–18",
    "P04": "Ruth 1:19–22",
    "P05": "Ruth 2:1–7",
    "P06": "Ruth 2:8-16",
    "P07": "Ruth 2:17-23",
    "P08": "Ruth 3:1-5",
    "P09": "Ruth 3:6-13",
    "P10": "Ruth 3:14-18",
    "P11": "Ruth 4:1-8",
    "P12": "Ruth 4:9-12",
    "P13": "Ruth 4:13-17",
    "P14": "Ruth 4:18-22",
}


async def _instantly_voiced(text: str, **_: object) -> tuple[SimpleNamespace, bool]:
    return SimpleNamespace(key=f"tts/v/{abs(hash(text))}.mp3"), False


def test_every_ruth_passage_has_a_line_to_be_named_by() -> None:
    missing = [m.pericope_num for m in load_book("Ruth") if not line_for(m.pericope_num, "pt")]

    assert missing == [], (
        "a equipe escolhe de ouvido: uma passagem sem fala não pode ser oferecida, "
        f"e estas ficariam mudas: {missing}"
    )


def test_a_passage_nobody_has_written_a_line_for_stays_silent() -> None:
    """Uma passagem sem fala é retirada da roda; um idioma sem falas não retira o livro."""
    assert line_for("Z99", "pt") == ""
    assert line_for("Z99", "xx") == ""


@pytest.mark.parametrize(
    ("spoken", "written"), [("pt", NAMED_IN_PORTUGUESE), ("en", NAMED_IN_ENGLISH)]
)
def test_the_wheel_names_the_passage_and_says_nothing_else_about_it(
    spoken: str, written: dict[str, str]
) -> None:
    """The reference each map carries in its own H1, and the book in the language spoken.

    Transcribed from the fourteen maps rather than derived, including the verse dash the
    canon is not consistent about — an en dash through P05, a hyphen from P06 on.
    """
    said = {m.pericope_num: line_for(m.pericope_num, spoken) for m in load_book("Ruth")}

    assert said == written, (
        "a roda dizia uma frase autoral por passagem, e algumas contavam a passagem antes "
        f"de a equipe escolher — P07 entregava o nome do resgatador: {said}"
    )


def test_the_panorama_has_no_authored_line_yet() -> None:
    """The wording is Marcia's to rule on and has not shipped, so the wheel must not speak
    one — this locks today's silence rather than assuming tomorrow's line."""
    assert panorama_line_for("pt") == ""
    assert panorama_line_for("en") == ""


def test_the_panoramas_line_never_borrows_the_other_languages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A passage falls back to the floor when its own language is unwritten, but the panorama
    is authored in both languages at once or offered in neither — borrowing the other
    language's line would hand a Portuguese team an English answer instead of silence."""
    monkeypatch.setattr(passage_lines, "_sections", lambda: {(PANORAMA, "en"): "Ruth, the book"})

    assert panorama_line_for("en") == "Ruth, the book"
    assert panorama_line_for("pt") == ""


def _the_book_named_in(language: str) -> str:
    """What this book's own catalogue calls the person the book is named after."""
    named = next(element for element in labelled_elements("P01") if element.label_en == "Ruth")
    return str(getattr(named, f"label_{language}"))


def test_no_line_in_the_file_carries_a_word_its_map_does_not() -> None:
    """The reference, with the book renamed for the language, is the whole of what may be said.

    Read off the maps and the label catalogue, so a line rewritten to carry story again has
    nothing to agree with — in any language the file grows, not only the two it has today.
    """
    strayed = {
        (pericope_num, spoken): said
        for (pericope_num, spoken), said in _sections().items()
        if said
        != f"{_the_book_named_in(spoken)} {load_map(pericope_num).reference.split(' ', 1)[1]}"
    }

    assert strayed == {}, (
        "a frase de cada passagem era autoral e nenhum validador a via, então a roda contava "
        f"a passagem antes de a equipe escolher: {strayed}"
    )


def test_the_lines_are_one_breath_each() -> None:
    long_ones = {
        m.pericope_num: line_for(m.pericope_num, "pt")
        for m in load_book("Ruth")
        if len(line_for(m.pericope_num, "pt")) > 90
    }

    assert long_ones == {}, (
        "a fala é ouvida muitas vezes enquanto a equipe roda a lista procurando a "
        f"passagem que quer — não pode virar parágrafo: {long_ones}"
    )


@pytest.mark.parametrize("pericope", ["P01", "P09", "P14"])
def test_the_line_carries_the_passage_numbers_and_never_the_id_the_canon_files_it_under(
    pericope: str,
) -> None:
    said = line_for(pericope, "pt")

    assert said
    assert pericope not in said
    assert any(ch.isdigit() for ch in said)


@pytest.mark.parametrize("spoken", ROOM_LANGUAGES)
def test_every_language_the_room_claims_can_name_every_passage(spoken: str) -> None:
    silent = [m.pericope_num for m in load_book("Ruth") if not line_for(m.pericope_num, spoken)]

    assert silent == [], (
        f"a sala diz que fala {spoken!r} e as falas são escritas por idioma; um idioma "
        "reivindicado e não escrito esvazia o livro em silêncio, e uma roda vazia diz à "
        f"equipe que tudo já foi feito: {silent}"
    )


def test_a_language_nobody_has_written_is_named_in_the_floors_words_not_in_silence() -> None:
    """Uma roda vazia não é um idioma faltando — é um livro que acabou."""
    spoken = [line_for(m.pericope_num, "xx") for m in load_book("Ruth")]

    assert all(spoken)
    assert spoken == [line_for(m.pericope_num, FLOOR) for m in load_book("Ruth")]


@pytest.mark.parametrize("tag", ["pt", "pt-BR", "PT-br"])
def test_the_region_never_decides_whether_a_passage_can_be_named(tag: str) -> None:
    assert line_for("P01", tag)


async def test_every_passage_the_wheel_offers_says_its_own_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller reading the wheel needs to tell a passage from a panorama without guessing
    from its id — kind says which, plainly, for every passage entry the wheel returns.

    Stubs the panorama off explicitly rather than relying on today's file having no
    section for it — that fact belongs to test_the_panorama_has_no_authored_line_yet,
    not to this one, which is about the passages' own kind."""
    monkeypatch.setattr(route.room, "synthesize_facilitator_speech", _instantly_voiced)
    monkeypatch.setattr(route, "panorama_line_for", lambda language: "")

    answer = await route.passages("Ruth", language="pt")

    assert [view.kind for view in answer.passages] == ["passage"] * len(answer.passages)


async def test_the_panorama_opens_the_wheel_when_it_has_a_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Once Marcia's word lands and a line is authored, the panorama has to be the first
    thing the team hears turning the wheel — it is the front door to the whole book."""
    monkeypatch.setattr(route.room, "synthesize_facilitator_speech", _instantly_voiced)
    monkeypatch.setattr(route, "panorama_line_for", lambda language: "")
    without_panorama = [
        view.pericope for view in (await route.passages("Ruth", language="pt")).passages
    ]

    monkeypatch.setattr(route, "panorama_line_for", lambda language: "Rute, o livro")
    answer = await route.passages("Ruth", language="pt")

    first = answer.passages[0]
    assert (first.kind, first.pericope) == ("panorama", "panorama")
    assert first.audio_url
    assert (first.beads, first.absence_index) == (0, -1), (
        "o panorama não tem elementos próprios — beads e absence_index não podem vir de "
        "uma passagem por engano"
    )
    assert [view.pericope for view in answer.passages[1:]] == without_panorama


async def test_the_panorama_stays_off_the_wheel_with_no_line_to_say_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No line for this language means no spoke, exactly as an unwritten passage is left
    out — the room must never read the panorama's id aloud as a stand-in for its voice."""
    monkeypatch.setattr(route.room, "synthesize_facilitator_speech", _instantly_voiced)
    monkeypatch.setattr(route, "panorama_line_for", lambda language: "")

    answer = await route.passages("Ruth", language="pt")

    assert all(view.kind != "panorama" for view in answer.passages)


async def test_the_wheel_offers_no_passage_the_session_would_refuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A team choosing by ear must be able to enter every spoke it hears.

    The only filter was a spoken line existing, so the wheel advertised all fourteen while
    `require_walkable` refused eight of them the moment a finger landed. The refusal reached
    the team as a broken room, and a spoke that cannot be entered is worse than one that was
    never offered.
    """
    monkeypatch.setattr(route.room, "synthesize_facilitator_speech", _instantly_voiced)

    answer = await route.passages("Ruth", language="pt")

    refused = []
    for view in answer.passages:
        try:
            require_walkable(load_map(view.pericope))
        except ValidationError as error:
            refused.append(str(error))
    assert refused == [], (
        "a roda oferecia passagens que a própria sessão recusa, e tocar numa delas dizia "
        f"à equipe que a sala tinha quebrado: {refused}"
    )


async def test_the_wheel_still_offers_every_passage_that_does_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The counterweight, and the more expensive of the two failures.

    A filter that overshoots empties the wheel, and the app does not read an empty wheel as a
    canon that is not ready — it reads it as a book with nothing left in it, halts, and tells
    the team to fetch a person. Six passages walk today and all six have to survive.
    """
    monkeypatch.setattr(route.room, "synthesize_facilitator_speech", _instantly_voiced)

    answer = await route.passages("Ruth", language="pt")

    offered = [view.pericope for view in answer.passages]
    opens = [
        meaning_map.pericope_num
        for meaning_map in load_book("Ruth")
        if any(
            element.kind is ElementKind.PRESERVED
            for element in elements_for(meaning_map.pericope_num)
        )
        and meaning_map.sta_status == SURVEYED_STATUS
    ]
    assert offered == opens, (
        "a roda tem que trazer exatamente as passagens que abrem: de menos e a equipe "
        f"ouve que o livro acabou, de mais e ela toca numa que recusa — veio {offered}"
    )


async def test_every_passage_arrives_with_its_necklace_already_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The app strings the necklace the moment the conversa opens.

    Waiting for the session to be created left the team in front of a bare cord for the
    whole round trip, so the wheel itself says how many beads each passage holds.
    """
    from app.api.internalization_room import passages as route
    from app.services.internalization_room.canon.elements import element_keys

    async def _instant(text: str, **_: object):
        return SimpleNamespace(key=f"tts/v/{abs(hash(text))}.mp3"), False

    monkeypatch.setattr(route.room, "synthesize_facilitator_speech", _instant)

    answer = await route.passages("Ruth", language="pt")

    for view in answer.passages:
        assert view.beads == len(element_keys(view.pericope, book="Ruth"))
        assert view.beads > 0
    assert any(view.absence_index >= 0 for view in answer.passages)


async def test_the_catalogue_does_not_wait_for_one_line_before_asking_the_next(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fourteen round trips in a row did not fit the app's ninety-second budget.

    A cold cache — a new book, or a tuning change, which is part of the cache key — put the
    route over it, and the room told a team on a working network that the internet was gone
    while the server was still working. The bound stays because the voice on the other end
    has a quota, so this asserts the calls overlap and that they never exceed it, rather
    than timing anything.
    """
    live = 0
    peak = 0

    async def _slow(text: str, **_: object) -> tuple[SimpleNamespace, bool]:
        nonlocal live, peak
        live += 1
        peak = max(peak, live)
        await asyncio.sleep(0.05)
        live -= 1
        return SimpleNamespace(key=f"tts/v/{abs(hash(text))}.mp3"), False

    monkeypatch.setattr(route.room, "synthesize_facilitator_speech", _slow)

    answer = await route.passages("Ruth", language="pt")

    assert len(answer.passages) > 1
    assert peak > 1, "uma linha por vez é o que estourava o orçamento do cliente"
    assert peak <= route.MAX_LINES_IN_FLIGHT, "e sem limite a cota do sintetizador é o próximo muro"


async def test_the_wheel_names_the_passages_in_the_language_the_request_asks_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A roda vem antes de qualquer sessão, então é o único lugar da sala que negocia
    idioma por pedido — sem isso, uma equipe em inglês gira uma roda em português."""
    said: dict[str, list[str]] = {}

    async def _remembering(text: str, **_: object) -> tuple[SimpleNamespace, bool]:
        said.setdefault("spoken", []).append(text)
        return SimpleNamespace(key=f"tts/v/{abs(hash(text))}.mp3"), False

    monkeypatch.setattr(route.room, "synthesize_facilitator_speech", _remembering)

    await route.passages("Ruth", language="pt")
    in_portuguese = said.pop("spoken")
    await route.passages("Ruth", language="en")
    in_english = said.pop("spoken")

    assert len(in_portuguese) == len(in_english)
    assert set(in_portuguese).isdisjoint(in_english)


async def test_the_wheel_asked_for_nothing_speaks_the_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    said: list[str] = []

    async def _remembering(text: str, **_: object) -> tuple[SimpleNamespace, bool]:
        said.append(text)
        return SimpleNamespace(key=f"tts/v/{abs(hash(text))}.mp3"), False

    monkeypatch.setattr(route.room, "synthesize_facilitator_speech", _remembering)

    await route.passages("Ruth")

    assert line_for("P01", FLOOR) in said
    assert line_for("P01", "pt") not in said


def test_the_line_for_ruth_2_17_23_names_the_passage_and_not_the_redeemer() -> None:
    """The one line the wheel speaks about a passage this branch is the reason it can offer.

    Nothing about a passage may be said that is not in its map, and the map withholds the
    redeemer's name until 4:10 — but the authored line for 2:17-23 says it outright, and the
    wheel speaks it before the team has chosen where to work. Until now the gate hid the
    problem: the passage never reached the wheel, so the line was never spoken.
    """
    filed_under = {
        meaning_map.reference: meaning_map.pericope_num for meaning_map in load_book("Ruth")
    }
    spoken = [line_for(filed_under["Ruth 2:17-23"], language) for language in ("pt", "en")]

    named = [line for line in spoken if "resgatador" in line.lower() or "redeemer" in line.lower()]
    assert not named, (
        f"a roda dizia o nome do resgatador antes de a equipe abrir a passagem: {named}"
    )

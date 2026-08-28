import asyncio
from types import SimpleNamespace

import pytest

from app.api.internalization_room import passages as route
from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.core.room_enums import ElementKind
from app.services.internalization_room.canon.book_material import require_walkable
from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.canon.parse_map import (
    SURVEYED_STATUS,
    load_book,
    load_map,
)
from app.services.internalization_room.passage_lines import line_for


async def _instantly_voiced(text: str, **_: object) -> tuple[SimpleNamespace, bool]:
    return SimpleNamespace(key=f"tts/v/{abs(hash(text))}.mp3"), False


def test_every_ruth_passage_has_a_line_to_be_named_by() -> None:
    missing = [m.pericope_num for m in load_book("Ruth") if not line_for(m.pericope_num, "pt")]

    assert missing == [], (
        "a equipe escolhe de ouvido: uma passagem sem fala não pode ser oferecida, "
        f"e estas ficariam mudas: {missing}"
    )


def test_a_book_nobody_has_written_lines_for_stays_silent() -> None:
    assert line_for("P01", "xx") == ""
    assert line_for("Z99", "pt") == ""


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
def test_the_line_names_the_passage_without_a_number(pericope: str) -> None:
    said = line_for(pericope, "pt")

    assert said
    assert pericope not in said
    assert not any(ch.isdigit() for ch in said)


def test_the_room_finds_its_lines_with_the_tag_it_is_actually_configured_with() -> None:
    spoken = get_settings().internalization_room_language_code
    silent = [m.pericope_num for m in load_book("Ruth") if not line_for(m.pericope_num, spoken)]

    assert silent == [], (
        f"a sala fala {spoken!r} e as falas são escritas por idioma; procurar a tag "
        "inteira esvaziava o livro em silêncio, e uma roda vazia diz à equipe que "
        f"tudo já foi feito: {silent}"
    )


@pytest.mark.parametrize("tag", ["pt", "pt-BR", "PT-br"])
def test_the_region_never_decides_whether_a_passage_can_be_named(tag: str) -> None:
    assert line_for("P01", tag)


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

    answer = await route.passages("Ruth")

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

    answer = await route.passages("Ruth")

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

    answer = await route.passages("Ruth")

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

    answer = await route.passages("Ruth")

    assert len(answer.passages) > 1
    assert peak > 1, "uma linha por vez é o que estourava o orçamento do cliente"
    assert peak <= route.MAX_LINES_IN_FLIGHT, "e sem limite a cota do sintetizador é o próximo muro"

import pytest

from app.core.config import get_settings
from app.services.internalization_room.canon.parse_map import load_book
from app.services.internalization_room.passage_lines import line_for


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

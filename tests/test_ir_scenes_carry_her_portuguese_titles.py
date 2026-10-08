import json
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.canon import titles
from app.services.internalization_room.canon.labels import LABELS_DIR, labelled_elements
from app.services.internalization_room.part_names import scene_titles
from app.services.internalization_room.sessions import create_session


async def test_a_portuguese_session_on_p01_names_each_scene_by_her_title_not_ours(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope="P01", language="pt")

    assert scene_titles(session) == [
        "Fome e exílio para Moabe",
        "Morte de Elimeleque",
        "Casamentos e o passar do tempo",
        "Mortes dos filhos",
    ], "a cena 1 se chamava «Fome e ida para Moabe», o título que nós escrevemos"


async def test_a_scene_missing_from_her_list_is_named_by_its_english_heading_not_by_nothing(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    listed = json.loads(titles.PORTUGUESE_TITLES.read_text(encoding="utf-8"))
    del listed["scenes"]["P01"]["S2"]
    without_it = tmp_path / "ui-labels.pt.json"
    without_it.write_text(json.dumps(listed, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(titles, "PORTUGUESE_TITLES", without_it)
    session = await create_session(db_session, pericope="P01", language="pt")

    assert scene_titles(session) == [
        "Fome e exílio para Moabe",
        "Death of Elimelech",
        "Casamentos e o passar do tempo",
        "Mortes dos filhos",
    ], "uma cena sem título em português ficava sem nome nenhum"


async def test_with_no_list_of_hers_every_scene_is_named_by_its_english_heading(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(titles, "PORTUGUESE_TITLES", tmp_path / "ui-labels.pt.json")
    session = await create_session(db_session, pericope="P01", language="pt")

    assert scene_titles(session) == [
        "Famine and exile to Moab",
        "Death of Elimelech",
        "Marriages and time passing",
        "Deaths of the sons",
    ], "sem a lista dela o veredito caía num erro em vez de dizer o título do mapa"


async def test_a_portuguese_session_on_a_passage_we_never_titled_names_every_scene_by_hers(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope="P03", language="pt")

    assert scene_titles(session) == [
        "O último apelo de Noemi",
        "O voto de Rute",
        "O silêncio de Noemi",
    ], "a P03 não tinha título em português e a parte era dita só pelo número"


async def test_an_english_session_names_each_scene_by_the_maps_heading_not_our_rewrite(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope="P01", language="en")

    assert scene_titles(session) == [
        "Famine and exile to Moab",
        "Death of Elimelech",
        "Marriages and time passing",
        "Deaths of the sons",
    ], "a sessão em inglês dizia «The death of Elimelech», o nosso catálogo, não o mapa"


@pytest.mark.parametrize(
    ("pericope", "number", "hers"),
    [
        ("P10", 2, 'Com a sogra: a pergunta, o relato e "fique quieta"'),
        ("P13", 1, "O casamento, a gravidez, o nascimento"),
        ("P13", 2, "As palavras das mulheres a Noemi"),
    ],
    ids=["P10-scene-2", "P13-scene-1", "P13-scene-2"],
)
async def test_her_three_hand_set_titles_are_said_character_for_character(
    db_session: AsyncSession, pericope: str, number: int, hers: str
) -> None:
    session = await create_session(db_session, pericope=pericope, language="pt")

    assert scene_titles(session)[number - 1] == hers, (
        "o título que ela aprovou à mão não chegava à sessão em português"
    )


@pytest.mark.parametrize(
    ("pericope", "key", "pt", "en"),
    [
        ("P01", "scene:2", "Morte de Elimeleque", "Death of Elimelech"),
        ("P03", "scene:1", "O último apelo de Noemi", "Naomi's last appeal"),
    ],
    ids=["a-passage-we-titled", "a-passage-we-never-titled"],
)
def test_a_scene_bead_on_the_desk_carries_her_title_and_the_maps_heading(
    pericope: str, key: str, pt: str, en: str
) -> None:
    (bead,) = [one for one in labelled_elements(pericope) if one.key == key]

    assert (bead.label_pt, bead.label_en) == (pt, en), (
        "a conta da cena no painel vinha do nosso catálogo, não da lista dela e do mapa"
    )


def test_a_scene_bead_of_a_passage_our_catalogue_lacks_still_carries_her_title(
    tmp_path: Path,
) -> None:
    catalogue = json.loads((LABELS_DIR / "ruth.json").read_text(encoding="utf-8"))
    del catalogue["P03"]
    (tmp_path / "ruth.json").write_text(json.dumps(catalogue, ensure_ascii=False), encoding="utf-8")

    (bead,) = [
        one for one in labelled_elements("P03", catalogue_dir=tmp_path) if one.key == "scene:1"
    ]

    assert (bead.label_pt, bead.label_en) == ("O último apelo de Noemi", "Naomi's last appeal"), (
        "uma passagem fora do nosso catálogo servia a cena sem o título dela"
    )

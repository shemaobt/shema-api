"""ENG-1588 — a session whose canon pin has no tree is refused by name, the same way everywhere.

The canon sync drops the kept trees, so a session opened before a re-pin can find no tree for
its pin once the next deploy lands. Each reader used to fail its own way: a 400 that blamed
the caller for a passage the canon has, a 500, or a silent read of nothing.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CanonNotKept
from app.services.internalization_room.canon import kept
from app.services.internalization_room.canon.book_material import significant_absences
from app.services.internalization_room.canon.labels import labelled_elements
from app.services.internalization_room.canon.names import registry_entry, verse_ranges
from app.services.internalization_room.canon.parse_map import load_book, load_map
from tests.baker import open_ir_session
from tests.canon_harness import forget_the_canon, the_canon_moves_on
from tests.device_harness import TABLET_TEAM
from tests.release_harness import PREFIX
from tests.room_harness import room_client

NEW_PIN = "a" * 40
GONE_PIN = "b" * 40
P = "P01"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


@pytest.fixture()
def a_pin_with_no_tree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> str:
    monkeypatch.setattr(kept, "KEPT_DIR", tmp_path / "kept")
    forget_the_canon()
    return GONE_PIN


async def test_a_session_whose_pin_lost_its_tree_is_refused_by_its_pin_not_as_a_bad_request(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session = await open_ir_session(db_session, pericope=P, project_id=TABLET_TEAM)
    tree = the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN)
    shutil.rmtree(tree)

    read = await client.get(f"{PREFIX}/sessions/{session.id}")

    assert read.status_code == 409, read.text[:300]
    assert read.json()["code"] == "CANON_NOT_KEPT", (
        "a sessão sem árvore respondia 400 «no vendored Meaning Map», culpando o pedido"
    )
    assert session.canon_pin in read.json()["detail"]


@pytest.mark.parametrize(
    "read",
    [
        lambda: load_map(P),
        lambda: load_book("Ruth"),
        lambda: registry_entry("Ruth", "B1"),
        lambda: verse_ranges(P),
        lambda: significant_absences(P),
        lambda: labelled_elements(P),
    ],
    ids=["map", "book", "names", "coordinates", "absences", "labels"],
)
def test_every_reader_of_a_pin_with_no_tree_refuses_by_naming_that_pin(
    read: Callable[[], Any], a_pin_with_no_tree: str
) -> None:
    with kept.reading_the_canon_of(a_pin_with_no_tree), pytest.raises(CanonNotKept) as refused:
        read()

    assert a_pin_with_no_tree in str(refused.value), (
        "cada leitor falhava do seu jeito: 400, FileNotFoundError ou StopIteration, sem o pin"
    )

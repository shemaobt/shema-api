from __future__ import annotations

import scripts.sync_internalization_canon as canon
from app.services.internalization_room.canon import book_material


def test_the_books_the_sync_vendors_are_the_books_the_room_serves() -> None:
    assert canon.SERVED_BOOKS is book_material.SERVED_BOOKS
    assert frozenset({"Ruth"}) == canon.SERVED_BOOKS

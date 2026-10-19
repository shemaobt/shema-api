"""OBT-600 — the Pulse inbox says when the name it prints is not the language's own.

The E2E pass of 14/oct/2026 (API-PRIV-041) found the inbox and *Quem ainda não reportou* naming a
sensitive project with no public name **africa**: the server printed the region key in the name's
place, as OBT-560 decided, and said nothing about it, so the screen could not turn the key into
*Projeto sensível — África* the way the cards, the prayer wall and the notices do. Every leaving
shape carries ``languageNameWithheld`` beside the name (OBT-560/562); the inbox is not a shape, and
the bit has to be put on it by hand, by the same predicate.

Each route is asked by the three readers of the region — the coordinator, who reads the name; the
Resource Circle, which reads the truth since OBT-571; and the OBT Lab, which does not — with no
public name registered (the key stands in), with one (the public name stands in) and on a cleared
project (everybody reads the name). No account here is an installation admin: they pass every
guard, and a refusal asserted with one would pass for the wrong reason.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaRegionKey
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user

LINKS = f"{PREFIX}/intake-links"
SUBMISSIONS = f"{PREFIX}/forms/submissions"

HERE = ShemaRegionKey.AFRICA
PROJECT_ID = "6f0c1d2e-3a4b-4c5d-8e6f-7a8b9c0d1e60"

#: The real record in Egypt is called this, which is the whole reason the name is withheld.
REAL = "Sa'di of High Egypt"
PUBLIC = "Sa'di"

#: Who reads the region's inbox, and whether they read the language's own name (OBT-571 made the
#: Resource Circle a ``trusted`` reader; Daniel, 7/oct/2026, kept the OBT Lab redacted).
READERS = [("coordinator", True), ("resourceCircle", True), ("obtLab", False)]


async def _seed(db_session, *, sensitive: bool, public: str | None) -> ShemaProject:
    row = ShemaProject(
        id=PROJECT_ID,
        language_name=REAL,
        public_language_name=public,
        bridge_language="Arabic",
        location="Cairo, Egypt",
        team="JOCUM Cairo",
        sensitive_country=sensitive,
        region_key=HERE,
    )
    db_session.add(row)
    await db_session.commit()
    return row


async def _headers(db_session, shema_app, role: str) -> dict[str, str]:
    user = await make_scoped_user(
        db_session, shema_app, email=f"{role.lower()}@caixa.test", role_key=role, regions=[HERE]
    )
    return await auth_header(db_session, user)


async def _pulse(client, coordinator: dict[str, str]) -> str:
    """A Pulse the team sent through its link, as API-PRIV-041 sent it."""
    link = await client.post(LINKS, json={"projectId": PROJECT_ID}, headers=coordinator)
    assert link.status_code == 201, link.text
    sent = await client.post(
        f"{PREFIX}/intake/{link.json()['token']}",
        json={
            "definitionVersion": link.json()["definitionVersion"],
            "answers": {"submittedBy": "Líder S", "period": "2026-10"},
        },
    )
    assert sent.status_code == 202, sent.text
    (row,) = (await client.get(SUBMISSIONS, headers=coordinator)).json()
    return str(row["id"])


async def _read(client, db_session, shema_app, role: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """The inbox row and the opened Pulse, as ``role`` reads them."""
    coordinator = await _headers(db_session, shema_app, "coordinator")
    submission = await _pulse(client, coordinator)
    headers = coordinator if role == "coordinator" else await _headers(db_session, shema_app, role)

    listing = await client.get(SUBMISSIONS, headers=headers)
    detail = await client.get(f"{SUBMISSIONS}/{submission}", headers=headers)

    assert listing.status_code == 200, listing.text
    assert detail.status_code == 200, detail.text
    (row,) = listing.json()
    return row, detail.json()


def _named(payload: dict[str, Any]) -> tuple[str, bool]:
    return payload["languageName"], payload["languageNameWithheld"]


@pytest.mark.parametrize(("role", "reads_the_name"), READERS)
async def test_with_no_public_name_the_inbox_says_the_region_key_is_not_a_name(
    client, db_session, shema_app, role, reads_the_name
) -> None:
    """API-PRIV-041 itself: the key stands in for the name, and the bit says so."""
    await _seed(db_session, sensitive=True, public=None)

    row, detail = await _read(client, db_session, shema_app, role)

    expected = (REAL, False) if reads_the_name else (HERE.value, True)
    assert _named(row) == expected
    assert _named(detail) == expected
    if not reads_the_name:
        assert "Egypt" not in f"{row}{detail}"


@pytest.mark.parametrize(("role", "reads_the_name"), READERS)
async def test_a_registered_public_name_is_read_withheld_like_the_key(
    client, db_session, shema_app, role, reads_the_name
) -> None:
    """The bit means *not the language's own*, as on every shape — the public name included."""
    await _seed(db_session, sensitive=True, public=PUBLIC)

    row, detail = await _read(client, db_session, shema_app, role)

    expected = (REAL, False) if reads_the_name else (PUBLIC, True)
    assert _named(row) == expected
    assert _named(detail) == expected
    if not reads_the_name:
        assert "Egypt" not in f"{row}{detail}"


@pytest.mark.parametrize(("role", "_reads_the_name"), READERS)
async def test_a_cleared_project_is_named_for_everybody(
    client, db_session, shema_app, role, _reads_the_name
) -> None:
    await _seed(db_session, sensitive=False, public=PUBLIC)

    row, detail = await _read(client, db_session, shema_app, role)

    assert _named(row) == (REAL, False)
    assert _named(detail) == (REAL, False)

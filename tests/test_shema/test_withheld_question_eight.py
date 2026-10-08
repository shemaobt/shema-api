"""The seven more texts a sensitive project keeps from the OBT Lab (OBT-573).

Karina, via Daniel, 6/out/2026, question 8: on a sensitive project the coordination keeps
*"Observações do objetivo; Observações do financeiro; Observações das necessidades; Legendas de
fotos e vídeos; Local da gravação; Organização parceira; Meta do status"*. Since OBT-571 the
Resource Circle reads the truth, so the reader left without them is the OBT Lab (Daniel,
7/out/2026).

One test per field, as the issue asks, for the reader who is handed the reduction — against the
coordination and the Resource Circle, who read all seven, and against a project that is not
sensitive, which everybody reads whole. The recording place is also a write: the progress tab
sends the story table whole, so a place handed as ``""`` and sent back must keep the stored one.
No account here is an installation admin, who passes every guard.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaMediaKind, ShemaRegionKey
from app.db.models.shema_media import ShemaMediaItem
from app.db.models.shema_progress import ShemaProgressEntry
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user

PROJECTS = f"{PREFIX}/projects"
HERE = ShemaRegionKey.OTHER
SENSITIVE_ID = "7a3e1c9b-2d44-4f0a-8b61-5c0e9d2f7a01"
CLEARED_ID = "7a3e1c9b-2d44-4f0a-8b61-5c0e9d2f7a02"

OBJECTIVE = "OBJETIVO-SIGILOSO traduzir para o vale"
FINANCIAL = "FINANCEIRO-SIGILOSO a igreja do vale apoia"
NEEDS = "NECESSIDADES-SIGILOSAS a estrada do vale"
PARTNER = "PARCEIRA-SIGILOSA Missao do Vale"
GOAL = "META-SIGILOSA terminar antes da fronteira fechar"
PHOTO = "FOTO-SIGILOSA a equipe na ponte do vale"
VIDEO = "VIDEO-SIGILOSO gravacao na aldeia"
PLACE = "LOCAL-SIGILOSO casa do lider no vale"
STORY = "Criacao"


def _first(record: dict, key: str) -> dict:
    return (record.get(key) or [{}])[0]


#: Each of the seven, as a read of the record body — the history's copy of the place included.
FIELDS = {
    "objectiveNotes": (OBJECTIVE, lambda r: r["objectiveNotes"]),
    "financialNotes": (FINANCIAL, lambda r: r["financialNotes"]),
    "needsNotes": (NEEDS, lambda r: r["needsNotes"]),
    "partnerOrg": (PARTNER, lambda r: r["partnerOrg"]),
    "statusGoal": (GOAL, lambda r: r["statusGoal"]),
    "mediaPhotos.caption": (PHOTO, lambda r: _first(r, "mediaPhotos").get("caption")),
    "mediaVideos.caption": (VIDEO, lambda r: _first(r, "mediaVideos").get("caption")),
    "storyProgress.recordLocation": (
        PLACE,
        lambda r: _first(r, "storyProgress").get("recordLocation"),
    ),
    "progressHistory.storyProgress.recordLocation": (
        PLACE,
        lambda r: _first(_first(r, "progressHistory"), "storyProgress").get("recordLocation"),
    ),
}


async def _seed(db_session, project_id: str, *, sensitive: bool) -> ShemaProject:
    story = [{"name": STORY, "recordLocation": PLACE, "recordStatus": "gravada"}]
    row = ShemaProject(
        id=project_id,
        language_name="Lingua Oito",
        location="Terra Sigilosa, Vale" if sensitive else "Campo Aberto",
        sensitive_country=sensitive,
        region_key=HERE,
        objective_notes=OBJECTIVE,
        financial_notes=FINANCIAL,
        needs_notes=NEEDS,
        partner_org=PARTNER,
        status_goal=GOAL,
        story_progress=story,
    )
    db_session.add(row)
    db_session.add(ShemaMediaItem(project_id=project_id, kind=ShemaMediaKind.PHOTO, caption=PHOTO))
    db_session.add(
        ShemaMediaItem(
            project_id=project_id,
            kind=ShemaMediaKind.VIDEO,
            url="https://youtu.be/oito",
            caption=VIDEO,
        )
    )
    db_session.add(
        ShemaProgressEntry(project_id=project_id, entry_date=date(2026, 9, 1), story_progress=story)
    )
    await db_session.commit()
    return row


@pytest.fixture()
async def sensitive(db_session) -> ShemaProject:
    return await _seed(db_session, SENSITIVE_ID, sensitive=True)


async def _headers(db_session, shema_app, role: str) -> dict[str, str]:
    user = await make_scoped_user(
        db_session, shema_app, email=f"{role.lower()}@oito.test", role_key=role, regions=[HERE]
    )
    return await auth_header(db_session, user)


async def _record(client, headers, project_id: str = SENSITIVE_ID) -> tuple[dict, str]:
    res = await client.get(f"{PROJECTS}/{project_id}", headers=headers)
    assert res.status_code == 200, res.text
    return res.json(), res.text


# --- the read, one field at a time --------------------------------------------------------


@pytest.mark.parametrize("field", list(FIELDS))
async def test_the_obt_lab_reads_each_of_the_seven_blank_on_a_sensitive_project(
    client, db_session, shema_app, sensitive, field
) -> None:
    """**DoD 1.** The field reaches the OBT Lab as ``""``, and its text is nowhere in the body."""
    secret, read = FIELDS[field]
    record, body = await _record(client, await _headers(db_session, shema_app, "obtLab"))

    assert read(record) == ""
    assert secret not in body


@pytest.mark.parametrize("role", ["coordinator", "resourceCircle"])
@pytest.mark.parametrize("field", list(FIELDS))
async def test_coordination_and_the_resource_circle_still_read_the_seven(
    client, db_session, shema_app, sensitive, role, field
) -> None:
    """**DoD 2.** The coordination and, since OBT-571, the Resource Circle read the truth."""
    secret, read = FIELDS[field]
    record, _body = await _record(client, await _headers(db_session, shema_app, role))

    assert read(record) == secret


@pytest.mark.parametrize("field", list(FIELDS))
async def test_a_project_that_is_not_sensitive_is_read_whole_by_the_obt_lab(
    client, db_session, shema_app, field
) -> None:
    """The rule is about a sensitive place; anywhere else there is nothing to keep back."""
    await _seed(db_session, CLEARED_ID, sensitive=False)
    secret, read = FIELDS[field]
    record, _body = await _record(
        client, await _headers(db_session, shema_app, "obtLab"), CLEARED_ID
    )

    assert read(record) == secret


async def test_the_card_carries_none_of_the_three_it_holds(
    client, db_session, shema_app, sensitive
) -> None:
    """``partnerOrg``, ``statusGoal`` and ``needsNotes`` are on the card too, which the list
    serves to the same reader."""
    res = await client.get(PROJECTS, headers=await _headers(db_session, shema_app, "obtLab"))

    assert res.status_code == 200, res.text
    for secret in (PARTNER, GOAL, NEEDS):
        assert secret not in res.text


# --- the write ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field", ["objectiveNotes", "financialNotes", "needsNotes", "partnerOrg", "statusGoal"]
)
async def test_the_obt_lab_may_not_write_a_text_it_reads_blank(
    client, db_session, shema_app, sensitive, field
) -> None:
    """*Não dá para editar o que não se vê*: the five are refused by name, before anything."""
    res = await client.patch(
        f"{PROJECTS}/{SENSITIVE_ID}",
        json={field: "outro texto"},
        headers={**await _headers(db_session, shema_app, "obtLab"), "If-Match": '"1"'},
    )

    assert res.status_code == 403, res.text
    assert field in res.json()["detail"]


async def _save_stories(client, headers, rows: list[dict]):
    return await client.patch(
        f"{PROJECTS}/{SENSITIVE_ID}",
        json={"storyProgress": rows},
        headers={**headers, "If-Match": '"1"'},
    )


async def test_a_story_table_sent_back_as_read_keeps_the_stored_place(
    client, db_session, shema_app, sensitive
) -> None:
    """The progress tab sends the table whole: the place handed as ``""`` comes back as ``""``,
    and the save keeps the stored one while it writes what the reader did change."""
    headers = await _headers(db_session, shema_app, "obtLab")
    record, _body = await _record(client, headers)
    rows = [{**row, "audioHours": "2 a 3"} for row in record["storyProgress"]]

    res = await _save_stories(client, headers, rows)

    assert res.status_code == 200, res.text
    await db_session.refresh(sensitive)
    assert sensitive.story_progress[0]["recordLocation"] == PLACE
    assert sensitive.story_progress[0]["audioHours"] == "2 a 3"


async def test_a_place_typed_over_one_the_reader_cannot_see_is_refused(
    client, db_session, shema_app, sensitive
) -> None:
    """Whatever the stored place was: comparing with the ``""`` the reader was given, and never
    with the truth, is what keeps the answer from being an oracle."""
    headers = await _headers(db_session, shema_app, "obtLab")

    res = await _save_stories(client, headers, [{"name": STORY, "recordLocation": "outro"}])

    assert res.status_code == 403, res.text
    assert "storyProgress.recordLocation" in res.json()["detail"]
    await db_session.refresh(sensitive)
    assert sensitive.story_progress[0]["recordLocation"] == PLACE


async def test_a_new_story_is_written_with_the_place_its_author_typed(
    client, db_session, shema_app, sensitive
) -> None:
    """A story with no stored row is the reader's own, and they see what they type."""
    headers = await _headers(db_session, shema_app, "obtLab")
    rows = [{"name": STORY, "recordLocation": ""}, {"name": "Abraao", "recordLocation": "aqui"}]

    res = await _save_stories(client, headers, rows)

    assert res.status_code == 200, res.text
    await db_session.refresh(sensitive)
    assert [row["recordLocation"] for row in sensitive.story_progress] == [PLACE, "aqui"]


async def test_coordination_writes_the_place(client, db_session, shema_app, sensitive) -> None:
    headers = await _headers(db_session, shema_app, "coordinator")

    res = await _save_stories(client, headers, [{"name": STORY, "recordLocation": "novo lugar"}])

    assert res.status_code == 200, res.text
    await db_session.refresh(sensitive)
    assert sensitive.story_progress[0]["recordLocation"] == "novo lugar"

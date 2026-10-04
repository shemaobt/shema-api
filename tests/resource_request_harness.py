"""What a resource-request case needs before it can ask: the accounts, the draft, the decision.

A team signs in and writes the draft, submits it, the base endorses it, and the mesa assigns
the fund, scores it and decides — and the board, the trail, the attachment and the Admin's
link each start from some point on that road. The cases in ``tests/test_resource_requests``
and the PME's cases about the project an approval files (``test_shema/test_pending_projects.py``)
differ in what they ask once they get there, so the road is built here once: a second copy of
the 26-row payload would drift exactly the way second serializers do.

Builders and constants only. A fixture cannot travel by import, so each module keeps its own
fixtures and calls what is here. The accounts sign in through the package's own ``conftest``
(``auth_header``, ``grant``), which is where a team's account became a project's member
(BE-19, OBT-520).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource_request import (
    RRDecision,
    RREvaluation,
    RRFund,
    RRRequest,
    RRRequestFieldHistory,
    RRSnapshot,
    RRStage,
)
from app.utils import resource_request_vocabularies as v
from app.utils.jwt import decode_token
from tests.baker import make_user
from tests.test_resource_requests.conftest import auth_header, grant

REQUESTS = "/api/resource-requests/requests"


# ——— the draft and the accounts that write it ————————————————————————————————————


def answers(request_type: str = "traducao") -> dict[str, str]:
    """Every required answer filled, with the three that are columns given real values."""
    filled = dict.fromkeys(v.REQUIRED_TEXT_FIELDS[request_type], "preenchido")
    filled["tpp_date"] = "2026-08-25"
    filled["leader_date"] = "2026-08-25"
    filled["amount_requested"] = "1200.00"
    for key in filled:
        allowed = v.VOCABULARY_VALUES.get(key)
        if allowed:
            filled[key] = allowed[0]
    return filled


#: The base leader every test draft names (BE-23, OBT-535): required to submit, and nobody's
#: own address among the accounts these tests sign in with.
LEADER_EMAIL = "lider@base.org"


def draft(request_type: str = "traducao", **over: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "request_type": request_type,
        "currency": "BRL",
        "leader_email": LEADER_EMAIL,
        "declaration": True,
        "fields": answers(request_type),
        "langs": [],
        "team": [{"name": "Ana", "role": "coordenação"}] if request_type == "traducao" else [],
        "chrono": [],
        "budget": [
            {"category_key": key, "description": "", "quantity": None, "amount": None}
            for key in v.BUDGET_CATEGORY_KEYS
        ],
    }
    payload.update(over)
    return payload


async def as_team(db_session, rrf_app, email: str = "equipe@rr.test") -> dict[str, str]:
    user = await make_user(db_session, email=email)
    await grant(db_session, user, rrf_app, "equipe")
    return await auth_header(db_session, user)


async def as_mesa(db_session, rrf_app, email: str = "mesa@rr.test") -> dict[str, str]:
    user = await make_user(db_session, email=email)
    await grant(db_session, user, rrf_app, "mesa")
    return await auth_header(db_session, user)


async def create(client, headers, **over: object) -> dict:
    res = await client.post(REQUESTS, json=draft(**over), headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


# ——— the mesa's decision, the Gestor and the board's column ——————————————————————


async def decide(
    db_session,
    request_id: str,
    decision: RRDecision | None,
    evaluated_at: datetime | None = None,
) -> None:
    """Write the mesa's decision straight to the table — BE-06 is what will write it for real.

    ``evaluated_at`` is stamped from the session by BE-06, and it is what orders two
    decisions on one snapshot, so a test about ordering has to set it.
    """
    snapshot = (
        await db_session.execute(select(RRSnapshot).where(RRSnapshot.request_id == request_id))
    ).scalar_one()
    db_session.add(
        RREvaluation(snapshot_id=snapshot.id, decision=decision, evaluated_at=evaluated_at)
    )
    await db_session.commit()


async def a_gestor(db_session, rrf_app):
    """A Gestor and its headers: the cases about who holds the pen read the account's id back."""
    user = await make_user(db_session, email="gestor@rr.test")
    await grant(db_session, user, rrf_app, "gestor")
    return user, await auth_header(db_session, user)


async def to_column(db_session, request_id: str, stage: RRStage) -> None:
    """The board's move, as its result: the money half is BE-08's and tested there."""
    request = (
        await db_session.execute(select(RRRequest).where(RRRequest.id == request_id))
    ).scalar_one()
    request.stage = stage
    await db_session.commit()


# ——— Parte C —————————————————————————————————————————————————————————————————————


def evaluation(request_type: str = "traducao", **over: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "request_type": request_type,
        "scores": [{"criterion_key": key, "score": 4} for key in v.CRITERION_KEYS[request_type]],
        "comments": "avaliado",
    }
    payload.update(over)
    return payload


async def as_gestor(db_session, rrf_app, email: str = "gestor@rr.test") -> dict[str, str]:
    user = await make_user(db_session, email=email)
    await grant(db_session, user, rrf_app, "gestor")
    return await auth_header(db_session, user)


async def submitted_request(client, headers) -> dict:
    created = await create(client, headers)
    res = await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


async def give_fund(db_session, request_id: str, fund_id: str = "linguas") -> None:
    """The mesa assigns the fund at triage (GATE-01 D4). The route for it exists since
    BE-11 (OBT-470) — ``PUT /requests/{id}/fund`` — and this shortcut stays for the tests
    that are not about the assignment: it sets up a precondition in one statement instead
    of driving a second endpoint, and ``test_fund_assignment.py`` pins that the two write
    the same column."""
    if (
        await db_session.execute(select(RRFund).where(RRFund.id == fund_id))
    ).scalar_one_or_none() is None:
        db_session.add(RRFund(id=fund_id, name="Shema Línguas"))
    request = (
        await db_session.execute(select(RRRequest).where(RRRequest.id == request_id))
    ).scalar_one()
    request.fund_id = fund_id
    await db_session.commit()


async def endorse(db_session, request_id: str) -> None:
    """The base leader's endorsement, as the precondition it is for anything past
    ``triagem`` (BE-16, OBT-476). The act is the link's since BE-23 (OBT-535) — a code, a
    page, a name — and this shortcut is ``give_fund``'s twin for the same reason: these
    tests are about what happens *after* a card may be analysed, not about who signs it.
    ``test_endorsement.py`` is what pins the real act, and ``endorsed_at`` is the column the
    rule reads."""
    request = (
        await db_session.execute(select(RRRequest).where(RRRequest.id == request_id))
    ).scalar_one()
    request.endorsed_email = request.leader_email
    request.endorsed_at = datetime.now(UTC)
    await db_session.commit()


async def decidable(db_session, client, headers) -> dict:
    """A submitted request the mesa may actually decide. Since BE-16's rule is enforced,
    all four decisions move the card past ``triagem`` and that exit waits for the base's
    signature (``guard_endorsement``) — so the endorsement is a precondition of deciding,
    exactly as it is of the board's ``board_card``. Tests that only score, and the ones
    about who may touch the evaluation at all, keep ``submitted_request``: they never move
    the card, so the rule never fires on them."""
    request = await submitted_request(client, headers)
    await endorse(db_session, request["id"])
    return request


async def put_evaluation(client, headers, request_id: str, **over: object):
    """A save as the mesa sends it. A decision travels with who was present (FE-50,
    OBT-518), so a save carrying one and naming nobody marks the caller — the member
    pressing the button was in the room. A test about the ata names its own attendees."""
    if over.get("decision") is not None and "attendees" not in over:
        token = headers["Authorization"].removeprefix("Bearer ")
        over["attendees"] = [decode_token(token)["sub"]]
    return await client.put(
        f"{REQUESTS}/{request_id}/evaluation", json=evaluation(**over), headers=headers
    )


# ——— the board ———————————————————————————————————————————————————————————————————


async def move(client, headers, request_id: str, to: str):
    return await client.post(f"{REQUESTS}/{request_id}/move", json={"to": to}, headers=headers)


# ——— the trail ———————————————————————————————————————————————————————————————————


async def trail_rows(db_session: AsyncSession, request_id: str) -> list[RRRequestFieldHistory]:
    rows = await db_session.execute(
        select(RRRequestFieldHistory)
        .where(RRRequestFieldHistory.request_id == request_id)
        .order_by(RRRequestFieldHistory.changed_at, RRRequestFieldHistory.field_key)
    )
    return list(rows.scalars().all())


# ——— the attachment ——————————————————————————————————————————————————————————————


def attachment_url(request_id: str) -> str:
    return f"{REQUESTS}/{request_id}/attachment"


#: One of the ten minimal real files ``test_attachments.py`` uploads: the validation reads
#: the bytes, not the filename, so what a case sends as a PDF has to be one.
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


class FakeStore:
    """Records every object and every signature request; deletes nothing, has no delete."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, str]] = {}
        self.signed: list[tuple[str, str, int]] = []

    async def upload(
        self, bucket: str, key: str, data: bytes, content_type: str, **_: object
    ) -> str:
        self.objects[(bucket, key)] = (data, content_type)
        return f"gs://{bucket}/{key}"

    async def sign(
        self,
        bucket: str,
        key: str,
        *,
        expiry_minutes: int = 15,
        response_content_type: str | None = None,
    ) -> str:
        self.signed.append((bucket, key, expiry_minutes))
        return f"https://storage.example/signed/{key}?x-goog-expires={expiry_minutes * 60}"


async def put_file(
    client, request_id: str, headers: dict[str, str], data: bytes, content_type: str, **params
):
    return await client.put(
        attachment_url(request_id),
        content=data,
        headers={**headers, "Content-Type": content_type},
        params=params,
    )


# ——— the Admin's link ————————————————————————————————————————————————————————————

#: Where an Admin issues a link, and where its holder opens it — the holder has no account.
LINKS = "/api/resource-requests/links"
LINK = "/api/resource-requests/link"


async def holder(db_session, client, email: str = "equipe@fora.org"):
    """An Admin, a link they issued to ``email``, and the holder's link session."""
    admin = await make_user(db_session, email=f"admin-{email}", is_platform_admin=True)
    body = (
        await client.post(
            LINKS, json={"email": email}, headers=await auth_header(db_session, admin)
        )
    ).json()
    verified = await client.post(f"{LINK}/{body['token']}/verify", json={"code": body["code"]})
    return admin, body, {"Authorization": f"Bearer {verified.json()['session']}"}

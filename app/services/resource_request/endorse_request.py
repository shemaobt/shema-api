from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.auth import User
from app.db.models.resource_request import RRRequest
from app.services.resource_request.get_request import get_request


async def endorse_request(db: AsyncSession, request_id: str, user: User, app_key: str) -> RRRequest:
    """The Líder de Base's act: vouch, in the system, that this project is his base's.

    GATE-02 D2 described the whole of it — *"tipo uma caixinha pra ele assinalar e
    confirmar que o projeto realmente pertence à base dele"* — and GATE-03 D2 made it an
    act in the system rather than a line typed on paper. **It takes no payload**, for the
    reason ``submit_request`` above it takes none: the act is the signature, ``endorsed_by``
    says who and ``endorsed_at`` says when, both stamped by the server and neither typable
    through a body that could lie about who vouched.

    **This is where ``leader_name`` and ``leader_date`` are born.** The paper form's
    second signature block stopped being demanded of the client with OBT-483 — submitting
    became the Ponto focal's acceptance — and its Líder half was left to this issue: the
    display pair is written here from the endorser's account and day, so the mesa keeps
    reading the line the paper always had, now with a writer behind it. The two keys stay
    askable in a draft (the emission still lists them, and refusing them would reshape the
    contract's 45), but nothing reads a typed leader line as an endorsement — the rule
    reads ``endorsed_at``, which only this function writes.

    **Only a submitted request is endorsable.** A draft is the team's work still moving,
    and an endorsement of a moving document would vouch for whatever it becomes — the same
    reasoning that makes the snapshot freeze at submission. The Líder cannot even reach
    another team's draft (``_scope.py`` starts his reach at submission); this check is what
    answers the caller who *can* reach one — the author who is also a Líder, or a platform
    admin — with the real reason instead of a 404.

    **Endorsing twice is refused**, not overwritten: the second act would silently replace
    who vouched, and a signature is not a value to update. Un-endorsing does not exist —
    a wrong endorsement is a conversation with the mesa, not a DELETE.

    Two absences are decisions. **Self-endorsement is not forbidden**: the paper form
    never demanded the two signature lines be different people — a small base's leader may
    well be its Ponto focal — and inventing that rule would be the client's call, not
    ours; ``endorsed_by`` records the fact either way, so nothing is hidden. And **the
    platform admin passes**, as they pass every guard in ``_deps.py`` by the
    installation's standing rule: unlike ``submit_request``'s author check — which binds
    admins because submitting signs in *another* name, ``created_by``'s — endorsing signs
    in the caller's own name, so whoever comes through the guard signs truthfully as
    themselves.

    Where an unendorsed request stops — ``triagem``, with ``recusado`` as its only exit —
    is written on ``RRRequest`` and enforced by BE-08's transition service; nothing here
    moves the card, exactly as submitting does not.
    """
    loaded = await get_request(db, request_id, user, app_key)
    request = loaded.request

    if request.submitted_at is None:
        raise ConflictError(
            "Only a submitted request can be endorsed: a draft is still moving, and an "
            "endorsement would vouch for whatever it becomes. Submission freezes the "
            "document; the endorsement signs the frozen one."
        )
    if request.endorsed_at is not None:
        raise ConflictError("This request was already endorsed.")

    now = datetime.now(UTC)
    request.endorsed_by = user.id
    request.endorsed_at = now
    request.leader_name = user.display_name or user.email
    request.leader_date = now.date()

    await db.commit()
    await db.refresh(request)
    return request

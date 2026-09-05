from sqlalchemy.ext.asyncio import AsyncSession

from app.services import authorization_service
from app.services.resource_request.capabilities import CAPABILITY_ROLES


async def holds_capability(db: AsyncSession, user_id: str, app_key: str, capability: str) -> bool:
    """Whether ``user_id`` holds a role that carries ``capability`` in ``app_key``.

    The query half of the capability model: it reads the user's roles through
    ``authorization_service.list_roles`` — the same call both platform guards make — and
    answers against the module's own map. The wiring half is
    ``require_capability`` in ``app/api/resource_requests/_deps.py``; the split is the
    house rule applied literally, and it is the shape ``app/core/access_control.py``
    already has.

    ``app_key`` is a parameter rather than a module constant so that the key stays named
    once, in ``_deps.py``, which is where every other application in this repository keeps
    its own and where ``test_the_app_key_is_named_once_in_the_module`` looks for it.

    **The answer is taken over the UNION of the roles the account holds**, which is what
    ``held & CAPABILITY_ROLES[capability]`` says and what the shape of the data requires: an
    account carries a row per grant, ``user_app_roles`` has no constraint on ``(user_id,
    app_id)``, and since ``20260828_rr02`` turned ``auto_approve`` on every account that
    registers is already ``equipe``. So a mesa member is ``equipe`` **plus** ``mesa`` — the
    floor accumulates instead of being replaced, and one role read alone would be the wrong
    answer for the ordinary account rather than for an exotic one.

    Two rules stand beside that and neither belongs in here. **``mesa`` and ``gestor`` are
    never granted to the same account, and nobody grants themselves** — ours (28/aug/2026)
    and not the client's words, applied where a grant is written; this function has to answer
    correctly whether it exists or not, which is why
    ``test_the_union_answers_where_one_role_alone_would_refuse`` writes the pair it forbids.
    And the only hand-run grant path today, ``scripts/grant_app_role.py``, cannot produce a
    second role at all: it matches on ``(user_id, app_id)`` and overwrites ``role_id``, so
    granting ``mesa`` to somebody who is ``equipe`` **replaces** it. That is a live bug for
    the eight applications the script serves and it has its own issue, **OBT-484** —
    ``app/services/authorization/grant_app_role.py`` is the path that already matches on all
    four columns, ``revoked_at`` included, which is why approval-time grants accumulate
    correctly and only the script does not.

    An unknown ``capability`` raises rather than returning ``False``. A typo in a guard
    would otherwise refuse every user of a route forever, which reads in production as a
    permission decision and not as the mistake it is.

    Two platform behaviours this deliberately does not paper over, both from the module
    design §5.5. A **platform admin never reaches here** — but not because the guard above
    stops them: ``require_app_access`` returns early on ``is_platform_admin`` to *admit*
    them, so the chain does run. What keeps an admin out of this function is the explicit
    ``if user.is_platform_admin: return user`` inside ``require_capability`` itself, and
    that line is load-bearing rather than redundant (PR #266, review). The consequence is
    the same either way: no negative test may use an admin account.

    And ``list_roles`` is read through ``access_control``'s cache elsewhere but **not
    here**: this reads the database on every call, so a grant made mid-request is visible
    immediately rather than after
    ``AUTH_CACHE_TTL_SECONDS``.
    """
    if capability not in CAPABILITY_ROLES:
        raise ValueError(f"Unknown capability: {capability!r}")

    granted = await authorization_service.list_roles(db, user_id, app_key)
    held = {role_key for _app_key, role_key in granted}
    return bool(held & CAPABILITY_ROLES[capability])

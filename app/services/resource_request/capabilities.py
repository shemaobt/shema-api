"""The capability table this module guards on, mirroring the frontend's source of it.

**Why the module carries a map at all.** ``require_app_access(app_key)`` and
``require_role(app_key, role_key)`` answer exactly one question each — *does this user
hold any role in this app*, and *does this user hold this one role*. The product's model
is neither: four of the nine capabilities belong to **more than one role** —
``edit_requests``, ``view_evaluation``, ``manage_funds``, and ``move_board`` since GATE-02
moved it — and ``require_role`` cannot express an OR. Guarding ``view_evaluation`` as
``MesaUser`` would refuse the Gestor, which is the very asymmetry that gives that role its
point — it sees the evaluation and the money and changes neither the evaluation nor the
board.
``permissions`` and ``role_permissions`` exist as tables but are **not wired into**
``app/core/access_control.py``, so there is no finer platform primitive to reach for.

Module-local and not in ``app/core/``: ``access_control.py`` is shared surface for eight
applications, and this is one application's model until a second one needs it.

**One table is written, the other is derived.** ``ROLE_CAPABILITIES`` is the frontend's
own shape, role by role, and is the only thing here typed by hand; ``CAPABILITY_ROLES``
is its inversion, which is the direction a guard asks in. Writing both by hand would be
two statements of one fact, and on the day they disagreed every test would still be
green.

**``capabilities.json`` beside this file is the vendored emission** — byte for byte
``docs/capabilities.json`` of ``shemaobt/resource-request-form``, carrying the frontend
commit it was emitted from. It is data, never edited here: a hand-fixed value would be
exactly the second source the contract-sync check exists to prevent. Re-vendor by running
``npm run emit:capabilities`` over there and copying the file across — with a clean tree,
or the commit field comes back marked ``-dirty``, naming a commit that does not contain
what was just emitted.

Same mechanism as ``resource_request_vocabularies.json``, whose emitter reserved this half
by name; that one has no guard in the frontend's CI and this one does, so a stale
``capabilities.json`` fails a pull request there as well as here.

The map is deliberately **not read** from that file at runtime, and this is the one place
that choice matters: a vendored file that arrived truncated or reordered would change who
may approve money, in silence. ``tests/test_resource_requests/test_capabilities.py``
compares the two instead, so a drift is a red test rather than a quiet grant.

**Where each cell came from**, because four of them were decided rather than derived:

* ``move_board`` includes the **Gestor** — GATE-02 D3 (OBT-448, 27/aug/2026). The
  pre-gate reading was that moving a card is deciding on a request rather than managing a
  resource; the client said the Gestor *"tem acesso a quase tudo em relação aos projetos,
  só não aprova"*. The confirmation below does **not** move it back: moving a card is still
  not deciding (GATE-02 D6 — a decision writes a column, a column never implies a decision).
* ``edit_evaluation`` stays **denied** to the Gestor, and since 28/aug/2026 the confirmation
  exists in writing: *"ele nem pontua nem decide, essa função é exclusiva da mesa"*. That is
  what settles the two sentences of 27/aug against each other — *"o Gestor pode alterar"*
  and *"só não aprova"* — in favour of the second. Until that date this paragraph claimed a
  confirmation that FE-22's contract §5.3 still listed as **pending**: the text was ahead
  of its own proof, which is the failure worth naming, because a restrictive default that
  merely stands and one the client chose are different facts and only one of them survives
  somebody asking *why*.
* ``assign_fund`` is **mesa-only** — GATE-01 D4 (OBT-447, 26/aug/2026), asked directly and
  answered *a mesa*, and **confirmed by the re-ask on 28/aug/2026**: *"somente a mesa"*. The
  client's aside in D1, that the Gestor would define which fund a project draws from, does
  not survive its own re-asking. The cell is no longer provisional and BE-11 (OBT-470) no
  longer carries the question — it carries the invariant that a request does not reach
  ``aprovado`` with ``fund_id IS NULL``.
* ``allocate_funds`` is **gestor-only** — GATE-01 D6, which offered *"só o Gestor, ou
  qualquer membro da mesa"*. It is the first capability the mesa does not hold, and that
  asymmetry is what the answer says.

**``administer_funds`` is in the table since FE-29** (OBT-481, 30/aug/2026), ahead of the
endpoints BE-10 (OBT-471) will guard with it. Asked what the fund area does the client
answered *"os 3"* — create, rename, retire — that the one who creates is *"o Gestor"*, and
that renaming and retiring have no permission of their own (*"seguem a de criar"*). That is
**one** capability over three verbs, held by the Gestor alone. That it is a **control**
capability and not a screen one is ours to decide — Daniel, 28/aug/2026 — and not a
sentence of the client's: the answer says who may, not how this table is assembled. The
choice has a mechanical consequence rather than an aesthetic one. Classified as a screen
capability it would be held by no role that also holds every other screen capability, so
``SCREEN_CAPABILITIES.every(holds)`` in the frontend's ``src/services/fixtures/accounts.ts``
would match nobody and the mesa's fixture account would disappear — the same trap the ``?``
cell of GATE-02 D3 sprang once already. The frontend now pins both halves by test: the
classification (the mesa's fixture account still resolves) and the reach (whoever
administers funds also opens the Painel, because the fund area lives inside it, FE-26).

⚠️ **The catastrophic misreading available here is narrowing ``manage_funds`` to the
Gestor**, on the theory that it is the money capability. It is the Painel's entry gate,
which mesa and Gestor hold alike; taking it from the mesa would remove the Painel from the
mesa entirely.

**The fourth role came with BE-16 and left with FE-49** (OBT-476 → OBT-517). The Líder de
Base held ``endorse_request`` and nothing else; the 22/set meeting took his account away
(OBT-522), and since BE-23 (OBT-535) he endorses through a link with a code mailed at
submission (``endorse_by_link``), which no role and no capability guards. The frontend retired
the role and the capability and re-emitted ``capabilities.json``, vendored here; the map below
follows it. **The role row stays seeded** (``RETIRED_ROLES``): existing installations have it,
``20260930_rr12`` revoked every grant on it, and deleting a row other tables point at is not a
side effect of retiring a capability.

Reading is not a row of this table and must not become one (``_scope.py`` §5.3 reasoning):
it rides on ``edit_requests``, and which rows it reaches is decided in ``_scope.py``.
"""

#: The nine ids of the frontend's ``CAPABILITIES``, in its order.
CAPABILITIES: tuple[str, ...] = (
    "edit_requests",
    "view_evaluation",
    "edit_evaluation",
    "manage_funds",
    "move_board",
    "assign_fund",
    "allocate_funds",
    "administer_funds",
    "grant_access",
)

#: The roles of the frontend's table — the ones ``scripts/seed_apps_roles.py`` writes for this
#: app, minus the retired one below.
ROLES: tuple[str, ...] = ("equipe", "mesa", "gestor")

#: Seeded and holding nothing: the Líder de Base's row, kept because installations have it and
#: its grants were revoked by ``20260930_rr12`` rather than deleted (FE-49, OBT-517).
RETIRED_ROLES: tuple[str, ...] = ("lider",)

#: The hand-written half. Field for field, the frontend's ``ROLES[].can``.
ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    "equipe": frozenset({"edit_requests"}),
    "mesa": frozenset(
        {
            "edit_requests",
            "view_evaluation",
            "edit_evaluation",
            "manage_funds",
            "move_board",
            "assign_fund",
        }
    ),
    "gestor": frozenset(
        {
            "edit_requests",
            "view_evaluation",
            "manage_funds",
            "move_board",
            "allocate_funds",
            "administer_funds",
            "grant_access",
        }
    ),
}

#: The inversion, derived: the roles that hold each capability. Every capability appears,
#: so a guard on one nobody holds refuses everyone instead of raising a KeyError.
CAPABILITY_ROLES: dict[str, frozenset[str]] = {
    capability: frozenset(role for role, held in ROLE_CAPABILITIES.items() if capability in held)
    for capability in CAPABILITIES
}

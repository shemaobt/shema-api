"""The capability table this module guards on, mirroring the frontend's source of it.

**Why the module carries a map at all.** ``require_app_access(app_key)`` and
``require_role(app_key, role_key)`` answer exactly one question each — *does this user
hold any role in this app*, and *does this user hold this one role*. The product's model
is neither: four of the eight capabilities belong to **more than one role** —
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

**The Admin holds exactly the Gestor's set, and the row is derived rather than written**
(OBT-568, Daniel, 6/oct/2026: *"o admin deve ter o mesmo nível de permissão que o gestor no
formulário"* — his decision, not the client's). The Admin of OBT-522 is one ``admin`` role
seeded in both apps (``scripts/seed_apps_roles.py``), and until this issue it carried no
capability here at all: the pen over any instance (``_editing.is_admin``, BE-25), the request
links (``_links.require_link_admin``, BE-26) and the board-wide reach (``_scope.reach``, which
counts any grant beyond ``equipe``) all read the role directly, and none of them went through
this table — so an account holding ``admin`` alone entered the form and reached no screen.
``ADMIN_CAPABILITIES`` **is** ``ROLE_CAPABILITIES["gestor"]``, the same object: the decision
says *the same level*, and a copied set would be a second place for the Gestor's row to move
without the Admin's following. What the Admin therefore does **not** hold is what the Gestor
does not — ``edit_evaluation`` (GATE-02 D3) and ``assign_fund`` (GATE-01 D4) — and that is the
whole of the issue's *out of scope*. And since the Admin's row is the Gestor's, ``admin`` and
``mesa`` exclude each other at grant time as ``gestor`` and ``mesa`` do (Daniel, 6/oct/2026;
``resource_request_access/_rules.py``). The row stays out of ``ROLE_CAPABILITIES`` because that
map is the hand-written mirror of the frontend's rows, and this one is not hand-written: the
emission carries the Admin's row too (its ``capabilities.ts`` lists him as a fourth role, with
the Gestor's array), and ``tests/test_resource_requests/test_capabilities.py`` compares the
emitted row to the derived one directly. The platform admin
(``users.is_platform_admin``) is a different thing and is unchanged: it never reaches this
table (``_deps.require_capability``).

Reading is not a row of this table and must not become one (``_scope.py`` §5.3 reasoning):
it rides on ``edit_requests``, and which rows it reaches is decided in ``_scope.py``.
"""

from app.services.shema._scope import ADMIN_ROLE

#: The eight ids of the frontend's ``CAPABILITIES``, in its order. ``grant_access`` left with
#: the form's access screen (FE-56, OBT-549): roles are granted in the PME now.
CAPABILITIES: tuple[str, ...] = (
    "edit_requests",
    "view_evaluation",
    "edit_evaluation",
    "manage_funds",
    "move_board",
    "assign_fund",
    "allocate_funds",
    "administer_funds",
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
        }
    ),
}

#: The Admin's row (OBT-568): the Gestor's set, the same object — never a copy.
ADMIN_CAPABILITIES: frozenset[str] = ROLE_CAPABILITIES["gestor"]

#: Every row the guard reads: the frontend's three plus the Admin's derived one.
HELD_CAPABILITIES: dict[str, frozenset[str]] = {**ROLE_CAPABILITIES, ADMIN_ROLE: ADMIN_CAPABILITIES}

#: The inversion, derived: the roles that hold each capability. Every capability appears,
#: so a guard on one nobody holds refuses everyone instead of raising a KeyError.
CAPABILITY_ROLES: dict[str, frozenset[str]] = {
    capability: frozenset(role for role, held in HELD_CAPABILITIES.items() if capability in held)
    for capability in CAPABILITIES
}

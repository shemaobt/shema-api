# `resource_requests` — module design

**Status:** written by BE-01 (OBT-450) on 24/aug/2026, against `main` at `28e0ff6`.
**Audience:** whoever implements BE-02…BE-08 and INT-01…INT-06. It is written so you do
**not** have to read the frontend.
**Inputs:** [`CLAUDE.md`](../CLAUDE.md), FE-22's frozen contract
(`shemaobt/resource-request-form`, `docs/contract.md`), and what BE-00 (OBT-464) merged
in PR #238.

---

## 0. How to read this

Every statement below carries one of three markers. They are the frontend contract's
markers, deliberately, so the two documents read the same way.

| Marker | Meaning |
|---|---|
| **Decided** | Settled here. A later issue that departs says so in its PR and edits this section. |
| **Provisional** | Implemented or proposed for convenience, not because anyone decided it. Named so wave 2 does not inherit it by accident. |
| **Open · GATE-0n** | Not decided. The gate issue is where the answer comes from — do not guess, and do not freeze a schema around a guess. |

Two tie-breakers, because this document is the junior of three:

- Where this document and [`CLAUDE.md`](../CLAUDE.md) disagree about **how this repository
  is written**, `CLAUDE.md` wins and this document has rotted. Say so rather than working
  around it.
- Where this document and FE-22's contract disagree about **what the product's data is**,
  the contract wins. It was frozen against a built and client-reviewed product; this one
  was not.

This is a **delta**, not an audit. It does not restate the house rules — it records the
places where building this module needs a decision the house rules do not already make.

---

## 1. What this is a delta against

### 1.1 The audit this issue expected to inherit does not exist

OBT-450 says: *"The ecosystem project's BE-01 already audited the repo's conventions —
read its output and write the delta; do not re-audit."*

**It did not.** OBT-390 — the ecosystem project's BE-01, *"Auditar o tripod-api e desenhar
o módulo Shemá"* — is still `Backlog`, `startedAt: null`, no attachments, no documents,
unchanged since 29/jul/2026. Its own DoD line *"Output a short design document"* was never
met. And no design or audit document has ever existed in this repository: outside the
internalization room's prompts and corpus, the only markdown `git log --all
--diff-filter=A '*.md'` has ever added is `AGENTS.md` (renamed to `CLAUDE.md`),
`README.md`, `RUNNING-LOCALLY.md`, `LICENSE.md` and `http/README.md`.

So the instruction had no artifact behind it, and the delta is written against the three
things that do exist: `CLAUDE.md`, FE-22's contract, and BE-00. That is a finding, not a
workaround — the frontend's `CLAUDE.md` §3.2 repeats the same false premise and wants its
own correction, in that repository.

### 1.2 What BE-00 already landed

Merged in PR #238, and this module does not touch any of it:

| Where | What |
|---|---|
| `app/api/resource_requests/_deps.py` | `APP_KEY`, `Db`, `CurrentUser`, and the three role aliases `EquipeUser` / `MesaUser` / `GestorUser`. The app key is named here and nowhere else in the module — an existing test keeps it that way. |
| `scripts/seed_apps_roles.py` | The app row (`app_url` = `https://resourceform.shemaywam.com`, which is what `request_password_reset` builds the reset link from) and the three role keys. |
| `app/services/access_request/_default_roles.py` | An approved self-service request grants `equipe`. |
| `http/resource_requests_auth.http` | The auth calls, against the shared `/api/auth`. |
| `tests/test_resource_requests/` | The probe-router conftest and sixteen access tests. |

The module therefore starts with **authentication already answered** and no data of its
own. Everything below is about the second half.

### 1.3 What is inherited unchanged, and is not repeated here

`CLAUDE.md` §2–§5 in force, verbatim: `app/api/` is HTTP access only with **zero database
access**; every query lives in `app/services/`; services never import
`fastapi.HTTPException` and raise from `app/core/exceptions.py`; `AsyncSession` comes from
`get_db` and I/O is async end-to-end; every schema change ships as an Alembic migration;
public functions carry full annotations (`disallow_untyped_defs = true`) and concise
docstrings, never `#` comments; line length 100.

This document adds nothing to those and assumes them everywhere.

---

## 2. Module naming and boundaries

### 2.1 The name and the prefix — **Decided**

The module is **`resource_requests`** and its routes live under
**`/api/resource-requests`**. Neither is new: `_deps.py`, `tests/test_resource_requests/`,
`http/resource_requests_auth.http` and the seed script already carry the name, and
`tests/test_resource_requests/conftest.py` already hard-codes the prefix for its probe
router. BE-01 only made the prefix real by mounting the router in `app/main.py`.

The router is **empty on purpose**. It exists so that the first endpoint of BE-04 needs no
change to `app/main.py` and no second conversation about the prefix. Mounting a router with
no routes registers nothing — no path, no OpenAPI entry — which is why
`tests/test_resource_requests/test_mount.py` proves the wiring by hanging a route off the
router and rebuilding the app, rather than by asking for a response.

When the module grows past one file, the aggregation is
`app/api/annotation_studio/__init__.py`'s loop verbatim: append each sub-router's *routes*
to the module router rather than `include_router`, so a prefix declared here is not applied
twice.

### 2.2 What it shares — **Decided**

The whole authentication spine, and only through `app/core/access_control.py`:
`users`, `apps`, `roles`, `user_app_roles`, `access_requests`, `refresh_tokens`,
`password_reset_tokens`.

**This module's services never query those tables directly.** The guards are the interface;
a service that reaches for `user_app_roles` has reimplemented `require_role` badly. The one
thing the module owns about identity is the *capability* mapping in §5.4, which is a pure
function of role keys and touches no table.

### 2.3 What it deliberately does not share — **Decided**

The ecosystem's own warning applies here and this is the answer to it: *"`tripod-api` has
projects; Shemá has projects; they are probably not the same projects. Getting this wrong is
a migration, not a refactor."*

| Existing table | Verdict | Why |
|---|---|---|
| `projects` | **Not shared. No FK.** | A `tripod-api` project is a translation project with a `language_id` FK and a location. A *solicitação* is a funding request that can precede any project, and Tipo 3 (equipment) may never produce one. A request references a project the day the product asks it to, as a nullable FK added then. |
| `languages` | **Not shared. No FK.** | The form's A1 stores language name, ISO code, family, dialects, speaker count and literacy rate as **free text typed by the team**, next to vocabulary answers for vitality and writing system (contract §1.2). `languages` is `name` plus a unique three-character `code`. A FK would reject exactly the population this product serves — the contract's own vocabulary has *língua ágrafa* as a first-class answer. Text fields. |
| `organizations`, `organization_members` | **Not applicable.** | Nothing in the PRD or the contract scopes a request by organization. If GATE-02 answers team access with an org, it becomes a nullable FK then. |
| `phases`, `project_phases` | **Not applicable.** | The board's six columns are this product's own key space (contract §4.1) and are not workflow phases of a translation project. |
| `notifications` | **Not applicable in wave 2 as scoped.** | Telling a team its decision is PRD §10's *notificações à equipe após a decisão*, which **no issue owns** — see §10. If it gets an owner, this table is the first thing to read, not a new one to build. |
| `permissions`, `role_permissions` | **Not usable.** | They exist as tables and are **not wired into `access_control.py`** — the guards check roles only. See §5.4. |

### 2.4 There is no Shemá module to coexist with — **finding**

OBT-450 asks what this module shares with the Shemá module. `git ls-tree origin/main`
finds **no `shema` directory** under `app/api/` or under `app/services/`. The ecosystem's
`CLAUDE.md` claims a commit scaffolded them; that ref is not on `main`.

So the boundary question has an answer nobody expected: there is nothing to draw a boundary
against. When the Shemá module does land, the two share the auth spine of §2.2 and nothing
else — they are different products with different aggregates, and the first person to reach
for the other's tables should be asked why.

---

## 3. Module layout

| Path | Owner | Holds |
|---|---|---|
| `app/api/resource_requests/__init__.py` | BE-01 | The module router. Aggregates the sub-routers once they exist. |
| `app/api/resource_requests/_deps.py` | BE-00, extended by BE-03 | `APP_KEY`, `Db`, `CurrentUser`, role aliases; §5.4's `require_capability`. |
| `app/api/resource_requests/requests.py` | BE-04 | Draft, submission, revision routes. |
| `app/api/resource_requests/evaluations.py` | BE-06 | Evaluation routes. Mesa-gated at the door. |
| `app/api/resource_requests/funds.py` | BE-07 | Fund and balance reads, movement history. |
| `app/api/resource_requests/board.py` | BE-08 | Stage transitions. |
| `app/services/resource_request/` | BE-04…BE-08 | **All** logic and **all** queries. One operation per file with an `__init__.py` re-export — the newer house style (`app/services/access_request/`, `app/services/project/`, `app/services/auth/`), not the grouped `*_service.py` of `annotation_studio/`. |
| `app/services/resource_request/access.py` | BE-03 | Row-level scoping — the `app/services/annotation_studio/access.py` precedent. Anything past "does this user hold role X" is a service concern, never a router one. |
| `app/services/resource_request/capabilities.py` | BE-03 | The capability→roles map of §5.4 — a pure table — and the `holds_capability` service function that reads a user's roles against it. |
| `app/services/resource_request/vocabularies.json` | BE-05 | The vendored emission of §9 — the frontend's own lists, with the commit they came from. Data, not logic; the only non-Python file in the package. |
| `app/models/resource_request.py` | BE-04…BE-08 | **Pydantic** request/response models. `ConfigDict(from_attributes=True)` on read models, separate `Create` / `Update` / `Response`. |
| `app/db/models/resource_request.py` | BE-02 | **SQLAlchemy** tables. Must be re-exported from `app/db/models/__init__.py` — see §8.1. |
| `alembic/versions/20260NNN_rrNN_*.py` | BE-02 | Migrations. Single head, clean `downgrade -1`. |
| `tests/test_resource_requests/` | all | Extend; do not replace. |

⚠️ `app/models/` is Pydantic and `app/db/models/` is SQLAlchemy. There is no
`app/schemas/`. The naming trips every newcomer once.

**The plural is not free, and it is not uniform — the repo already decided it, per
directory.** Two rules, both read off the siblings rather than chosen here:

- **`app/api/` is plural, `app/services/` is singular**, and the existing pairs say so
  without exception worth following: `access_requests.py`/`access_request/`,
  `projects/`/`project/`, `meaning_maps/`/`meaning_map/`, `languages.py`/`language/`,
  `phases.py`/`phase/`, `users.py`/`user/`. Of the 24 packages in `app/services/`, **23 are
  singular** and the one plural (`notifications/`) is plural on the API side too. So this
  module is `app/api/resource_requests/` — which is BE-00's, already merged — and
  `app/services/resource_request/`.
- **Both model files are singular and carry the same name.** The 16 names that exist in both
  `app/models/` and `app/db/models/` mirror each other exactly — `project.py`,
  `sound_necklace.py`, `book_context.py`, `notification.py`, `auth.py`, … — and
  `oc_stats.py` is the only file on either side whose name ends in an `s`.

---

## 4. Aggregate ownership

Four aggregates, from FE-22's contract §1–§4, plus the capability table. Each row names the
issue that builds it and the invariant that must survive it.

The table names below are **Provisional** — an `rr_` prefix and a plural, chosen only so the
rest of this document has something to point at. BE-02 renames them freely; what it may not
change without saying so is the ownership and the invariants in the last two columns.

**Every table in this document is created by BE-02**, which §3 gives `app/db/models/` and
every `alembic/versions/` file. The owner column therefore names two issues wherever there
is a table: BE-02 authors the schema, and the second issue builds the behaviour on it. The
capability table is the one row with a single owner, because it is a map in Python and not a
table at all.

| Aggregate | Tables (working names) | Owner | The invariant |
|---|---|---|---|
| Request document | `rr_requests`, `rr_request_sections`, `rr_budget_lines`, `rr_snapshots` | BE-02 (schema), BE-04 (lifecycle) | Submission freezes an immutable snapshot; a revision is a **new draft linked to the evaluated snapshot**. What the mesa scored stays exactly as scored. |
| Evaluation | `rr_evaluations`, `rr_evaluation_scores` | BE-02 (schema), BE-06 (authorship) | Its own aggregate — see §4.1. Six scores 0–5 per type; the /30 total is **derived, never stored**; evaluator and date come from the session, never the payload. |
| Fund and ledger | `rr_funds`, `rr_fund_movements` | BE-02 (schema), BE-07 (movements) | The ledger is append-only. Balances are sums over movements; `disponível = alocado − comprometido` is derived, never a third column. |
| Board | `rr_board_transitions` (+ the request's current stage) | BE-02 (schema), BE-08 (transitions) | Stage change and ledger movement commit or roll back **together**. Only `aprovado` commits funds; moving out of it restores them. |
| Capability table | none — a pure map | BE-03 | Mirrors the contract's §5.3 field for field, checked in CI against it. |

### 4.1 The evaluation is its own aggregate — **Decided**, and it is the one shape not to copy

In wave 1 the evaluation lives *inside* the request draft: `scores[6]`, `board_decision`,
`board_comments`, `board_evaluator`, `board_evaldate` are fields of the same object in the
same browser. That is a one-user convenience.

**It is wrong as a persistence model.** Part C is gated by the `view_evaluation` capability
and a team does not hold it. If the evaluation stays nested, serving a team its own request
serves it the mesa's scores — and a capability that hides a screen is not a capability if
the data ships inside another response.

So: **BE-04 serves the request document without the evaluation, and BE-06 owns the
evaluation with its own identity, its own authorship and its own read permission.** This is
the single most expensive thing to get wrong here, because fixing it later is a migration
plus an audit of who saw what.

### 4.2 Request shape: a queried spine, and sections that are not columns — **Decided**

The asymmetry decides it, and the issue already states it: the spine (id, type, project
name, stage, totals, signatures, timestamps) is **queried** — by the board, by lists, by the
cycle indicators — while the per-type A/B sections are **read whole**, always, by exactly
one screen. So the spine is columns, and the sections are not.

The contract's own numbers say why the second half is not negotiable: 45 text keys, of which
A1-full (12), A2 (7) and A3 (6) belong to `traducao` alone while A1-slim (4) and A5's two
checkbox sets belong to the other two. Flattening that is 45 nullable columns of which
roughly half are structurally null for any given row, and every new question on the form
becomes a migration.

Two things are decided and two are BE-02's:

- **Decided:** the spine is columns; the sections are not; and the contract's distinction
  survives whichever medium is chosen — **empty means "not answered", absent means "not
  asked"**. A section a type never renders writes no keys at all, and the mesa reads that
  difference.
- **BE-02's:** whether the sections are `rr_request_sections` rows keyed
  `(request_id, section_id, field_key)` or one JSONB document per request. Rows make a
  single answer queryable and a JSONB document makes the whole read one hop; nothing in the
  product asks to query a single answer today, so either is defensible and the choice
  belongs with the migration.

Three things are **not** free-form and stay relational:

- **Budget lines are rows**, 26 of them, `(request_id, category_key, description, quantity,
  amount)` — never 78 columns.
- **Scores are rows**, six of them, `(evaluation_id, criterion_key, score)`.
- **The decision is an enum** of exactly four strings.

### 4.3 Keys, not positions — **Decided**, and it needs a list that does not exist yet

Wave 1 keys the 26 budget categories and the 6 criteria **by array index**. The contract
says so and flags the hazard in the same breath: reordering `budgetCategories.ts` silently
rewrites every stored draft, because the index is the only key.

**The server stores a key, never an index.** A row that says `chips_sim` survives a
reordering; a row that says `16` does not.

The keys themselves are the gap: the contract mints stable slugs for the seven unkeyed
*vocabularies*, but **not** for the 26 budget categories and **not** for the 3 × 6 criteria.
Those two lists still have to be minted, from the frontend's own arrays, and frozen. §9 is
where that lands.

---

## 5. Seam A — authentication and access (GATE-02)

GATE-02 has not closed. This section designs both variants shallowly so neither answer
forces a redesign, and marks the large part that is common to both — which is where BE-02
and BE-04 can safely build today.

### 5.1 Variant 1 — shared `shema-api` principals · **Decided**, and already built

Every actor is a `users` row holding a role in this app. This is GATE-02's own stated
default (*"`shema-api`'s existing auth is the default answer; deviating needs a reason"*),
and BE-00 built it: `_deps.py` is the entire seam, and a request's author is a
`users.id` FK.

### 5.2 Variant 2 — separate principals · **Open · GATE-02**

If the client answers *leader-link* or *anonymous fill + submit*, a team is not a `users`
row. What changes:

- A table of claims — a token, what it grants, when it expires, which request it is bound
  to — and a resolver that turns one into the same object `CurrentUser` produces.
- `_deps.py` gains a second dependency that accepts either, **behind the same
  `Annotated` aliases**.

What **does not** change, and this is the point of stating the variant at all: no router
signature, no service signature, and no row in the capability table. Every route already
takes `user: CurrentUser`; a resolver that answers the same shape is a swap inside one file.

The cost that must be named rather than discovered: an anonymous author has **no stable
identity**, so `rr_requests.created_by` becomes nullable and the audit trail of §10 loses
its subject. That is a product consequence, not a technical one, and it belongs in the gate.

### 5.3 What both variants share — safe to build now

The request's author column exists either way; only what it points at moves. The evaluation
is always authored by a mesa principal, which exists in both variants. Every capability
check, every row-scoping rule, and the whole of §4 are untouched by the gate. **BE-02 is
not blocked by GATE-02** for anything but the nullability of one FK.

### 5.4 Capabilities are not roles — the delta the platform does not cover · **Decided**

`require_app_access(app_key)` and `require_role(app_key, role_key)` answer exactly one
question each: *does this user hold any role in this app*, and *does this user hold this
one role*. The frontend's model is five capabilities across three roles:

| Capability | `equipe` | `mesa` | `gestor` |
|---|---|---|---|
| `edit_requests` | ✅ | ✅ | ✅ |
| `view_evaluation` | — | ✅ | ✅ |
| `edit_evaluation` | — | ✅ | — |
| `manage_funds` | — | ✅ | ✅ |
| `move_board` | — | ✅ | — |

Three of the five are held by **more than one role**, and `require_role` cannot express an
OR. Guarding `view_evaluation` as `MesaUser` would refuse the Gestor, whose whole point is
that asymmetry — it sees the evaluation and the money and changes neither the evaluation nor
the board.

Two more reasons not to guard on roles directly: `permissions` and `role_permissions` exist
as tables but **are not wired into `access_control.py`**, so there is no finer platform
primitive to reach for; and GATE-02 may still move a cell in that table, which must cost one
line and not a sweep through the routers.

**Decision.** The map is data, in `app/services/resource_request/capabilities.py`, mirroring
the table above field for field. Beside it, a service function `holds_capability(db, user_id,
capability)` reads the user's roles through `authorization_service` and answers against the
map; `_deps.py` gains only the `require_capability(capability)` factory that wraps it in
`Depends`. That split is the house rule applied literally — the query lives in a service and
the api layer does dependency wiring — and it is the same shape `app/core/access_control.py`
already has with `authorization_service`.

**Module-local, not `app/core/`** — `access_control.py` is shared surface for eight
applications and this is one application's model until a second one needs it. BE-03 builds
both, and BE-03's CI check compares the map against FE-22's contract so the two cannot drift.

### 5.5 Two platform behaviours to design around

- **A platform admin bypasses both guards unconditionally.** `require_app_access` and
  `require_role` each return early on `user.is_platform_admin` before consulting a grant.
  Negative tests written per role must not use an admin account, and no capability check
  in this module can be assumed to have run for one.
- **The two guards disagree for up to five minutes.** `require_app_access` memoises roles in
  `app/core/auth_cache.py` (`TTLCache(maxsize=512, ttl=300)`); `require_role` reads the
  database every time. So a call made *before* a grant caches an empty list, and the freshly
  granted mesa member then passes `MesaUser` while `CurrentUser` still refuses.
  `invalidate_roles(user_id)` is the exit, and BE-00's conftest already clears the cache
  around every test for exactly this reason.

---

## 6. Seam B — how a request travels (GATE-03)

GATE-03 has not closed either. Three options are on the table; each is drawn shallowly here,
and the common part is marked.

| | (a) mesa-entered | (b) team submits online | (c) both |
|---|---|---|---|
| Who writes the draft | a mesa principal | the team | either |
| Routes | `POST/PATCH /requests` under `edit_requests`, whose holders GATE-02 decides; no submit route at all | `POST/PATCH /requests` for the author, `POST /requests/{id}/submit` | both, and submit accepts either author |
| Where the snapshot is taken | on creation — the record *is* the received document | on `submit` | on `submit`, and on creation for a mesa-entered one |
| The attachment | a note (`attachment_note`), the file arrives by another channel | an upload endpoint, or the note | the note is the floor; the upload is additive |
| What the team sees afterwards | nothing — it is outside the system | **Open · GATE-03** | **Open · GATE-03** |

### 6.1 What is common to all three — safe to build now

- A request has an author and a creation time.
- **Submission freezes a snapshot**, and evaluation points at the snapshot rather than at a
  mutable document. Only *who* triggers the freeze moves between the options.
- A revision is a new draft linked to the evaluated snapshot, opened by the `revise`
  decision. This is BE-04's, and it is the case that hurts most if the team is never told —
  the whole flow assumes they come back.
- `attachment_note` is already one of the contract's 45 keys, so **the note field exists in
  every option**. An upload endpoint is additive to it and never replaces it: a team on a
  field connection that cannot upload still has to be able to say what it sent.

### 6.2 What the gate actually changes

The route surface and the attachment's shape, and nothing else. If the answer is (a),
BE-04's DoD items about team submission become mesa-entry endpoints and the issue shrinks —
it says so itself. Nothing in §4 moves, and the nullable author column is GATE-02's cost
(§5.2), not this gate's. That is the whole reason for drawing the seam before the answer
arrives.

---

## 7. The fund ledger, and the financial tables that do not exist

### 7.1 There are none — **verified**

OBT-450 asks for this explicitly, expecting *"almost certainly none"*. Confirmed, in every
direction checked:

- `Numeric`, `Decimal` and `from decimal` appear **nowhere** in `app/` or `alembic/`.
- `fund`, `balance`, `invoice`, `payment`, `currency`, `price` appear in **no** column, model
  or migration.
- The only `ledger` in the repository is the internalization room's in-memory comprehension
  evidence list, held inside a JSON column. The only `budget` is a word ceiling on
  synthesized speech. Neither is financial.
- Of the 64 tables in `app/db/models/`, none is financial. The nearest numeric columns are
  latitude/longitude, audio durations and a file size.

**So the ledger is greenfield and sets the convention rather than following one.** Nothing
in this repository has to be reconciled with it, and nothing in this repository will teach
BE-07 how money is stored here — that decision is made below, first.

### 7.2 Money at the boundary — **Decided; BE-02 implements**

The contract leaves this unfrozen on purpose and names BE-02 as the decider: money crosses
the frontend as *strings as typed*, while the board card's `valor` is a `number`, and the
conversion happens implicitly at the projection.

**Store `Numeric(14, 2)`, mapped to `Decimal`.** Reasons, in order of weight: a balance is a
**sum over an append-only ledger**, and float error accumulates over exactly that operation;
PostgreSQL `numeric` is exact, and SQLAlchemy's `Numeric` returns `Decimal` on both dialects
this repository runs — measured, summing `0.10` and `0.20` gives `Decimal('0.30')` where the
float path gives `0.30000000000000004`; and minor units force every read through a division
by a scale that depends on the currency, which is a second thing to get right for no gain
here.

Two consequences that are the decision's own cost, and are accepted rather than hidden:

- The frontend accepts amounts with more than two decimals — it renders whatever
  `toLocaleString` gives, up to three. **BE-05 rejects sub-cent input rather than rounding
  it**, which is the same rule it already applies to a total that disagrees with its rows:
  silent correction hides client bugs.
- The frontend also accepts **negative** amounts, by recorded decision. Whether a negative
  budget line is valid is BE-05's call, and it is a validation rule, not a column type.

**Currency is stored as ISO-4217** — `BRL` | `USD` | `EUR` — not as the symbol the frontend
persists. `€` is not an identity (several currencies share a glyph, and `$` is worse), and a
database enum should not be a typographic choice. The mapping is total in both directions
(`R$`↔`BRL`, `US$`↔`USD`, `€`↔`EUR`) and belongs in INT-02's client. This departs from the
contract's §5.1 as written, so §10 carries it as a contract update rather than a silent
divergence.

### 7.3 Concurrency: what gets locked — **Decided; BE-07 implements**

Balances are sums, so there is **no balance column to lock**. The row that exists and can be
locked is the fund itself:

```
SELECT … FROM rr_funds WHERE id = :fund FOR UPDATE
```

taken inside the same transaction that appends the movement and writes the stage change.
Two mesa members approving against one fund then serialize on that row: the first commits,
the second recomputes the sum *after* the first is visible and gets a decidable answer.

**What that answer is — refuse, or allow negative with a warning — is Open · GATE-01.**
Do not choose it in code. Wave 1 already renders a negative *disponível*, so allowing it is
not absurd; refusing it is not either. It is the mesa's practice, and it is one branch.

⚠️ **The test for this cannot run where the other tests run, and it fails silently.**
`pytest` runs on SQLite (`tests/conftest.py` sets `sqlite+aiosqlite`), and SQLAlchemy
**drops the clause without a word** on that dialect — the same `with_for_update()` compiles
to `… WHERE rr_funds.id = %(id_1)s FOR UPDATE` on PostgreSQL and to `… WHERE rr_funds.id =
?` on SQLite. So a concurrency test written against the default suite would lock nothing and
pass anyway, which is worse than not having one. BE-07's double-approve test needs
PostgreSQL, and the only workflow with a postgres service today is `migrations.yml`. Either
that job grows a step or `test.yml` gains a service. Recorded here so BE-07 does not
discover it by writing a test that passes for the wrong reason.

---

## 8. Traps in this repository, each with its reason

The short list of things an implementer will otherwise trip over. Every one was measured
against `main` at `28e0ff6`.

### 8.1 Alembic autogenerate sees zero tables

`alembic/env.py` sets `target_metadata = Base.metadata` and imports `Base` from
`app.core.database`. **Nothing on that import path imports `app.db.models`** — grepping the
repository, nothing imports the package at all. Measured:

```
tables visible importing only app.core.database: 0
tables visible after importing app.db.models:   64
```

So `alembic revision --autogenerate` today compares an **empty** metadata against the
database and would emit a migration dropping all 64 tables. That is not hypothetical for
BE-02, which is the next issue and authors the first migration of this module.

The repository has been living with it: only 2 of the 68 revisions carry alembic's
autogenerate marker, and both are the legacy hash-named ones. **The 66 others were written
by hand, and BE-02 writes its own by hand too.** Re-exporting the new model file from
`app/db/models/__init__.py` is still required — the app itself needs it — but it does not
make autogenerate safe on its own. Fixing `env.py` is a repository-wide change touching
seven other applications' migration workflow, and belongs to an issue of its own (§10).

### 8.2 Native enums cost a migration to extend, and pytest is SQLite

The house idiom for a real PostgreSQL enum (`app/db/models/internalization_room.py`,
`sound_necklace.py`):

```python
_DECISION_TYPE = Enum(
    RRDecision,
    name="rr_decision_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)
```

`values_callable` is not optional — without it PostgreSQL stores the member *names*, not the
lowercase values the contract froze. Adding a value later is
`ALTER TYPE … ADD VALUE IF NOT EXISTS` inside `op.get_context().autocommit_block()`, guarded
by `if op.get_bind().dialect.name == "postgresql"`, because the same migration has to run
under SQLite in CI.

The four decision strings are frozen by the contract and will not grow, which is what makes
a native enum the right call for them. The six board columns are frozen too. Anything the
client might extend — the fund list, while GATE-01 is open — should be a **table**, not an
enum.

### 8.3 Migrations: naming, one head, and a clean downgrade

Files are `YYYYMMDD_NNNN_snake_description.py` with `revision` equal to the prefix
(`20260819_room08`); the internalization-room series swapped the counter for a semantic tag,
so `20260NNN_rr01_…` with `revision = "20260NNN_rr01"` follows the precedent. There is
exactly one head today, `20260819_room08`, and `migrations.yml` enforces it against a real
PostgreSQL — it runs `upgrade head`, `downgrade -1`, `upgrade head`, with
`PYTHONWARNINGS=error::UserWarning` because a duplicate revision id is only a warning.
**`downgrade()` is not decorative here; a migration that cannot come back down fails CI.**

### 8.4 The error envelope carries no field, and BE-05 needs one

`app/core/exceptions.py` renders every business exception as `{"detail": <string>,
"code": <string>}`. `ValidationError` → 400, `AuthorizationError` → 403,
`UnknownReferenceError` → 422, and so on. **None of them can name a field**, and BE-05's DoD
asks for field-level errors on drift and on invalid vocabulary values. `UnknownReferenceError`'s
own docstring records why unifying the shapes is not on the table: it would rewrite the body
of every validation error the API returns and break existing clients.

**Decision: BE-05's field-level errors ride on Pydantic, not on a new exception.** A
`field_validator` that reads previously-validated fields through `ValidationInfo.data`
produces an error located on the field, which FastAPI already renders as a 422 with the
standard `detail` list. Measured:

```json
{"type": "value_error", "loc": ["stated_total"],
 "msg": "Value error, does not match the rows: they sum to 15.0"}
```

That covers the whole of BE-05: vocabulary membership, score range, the 26 rows, and the
recomputed-total drift — the last one being the only check that needs a *cross-field*
validator, which is exactly what `ValidationInfo.data` gives. No new error envelope is
invented, and no existing client sees a new shape.

### 8.5 The app key is named once, and a test says so

`tests/test_resource_requests/test_access.py::test_the_app_key_is_named_once_in_the_module`
globs `app/api/resource_requests/*.py` and fails if any file but `_deps.py` contains the
literal app key. Keep it that way: it is what makes GATE-02's answer a one-file change.

---

## 9. The vocabulary mirror — how a Python check reads a TypeScript source

BE-05's DoD requires the constants to be **checked in CI against FE-22's contract** so the
two stacks cannot diverge. The contract raises the obstacle and hands it to this issue by
name: BE-05 runs in Python and cannot read `src/contract.ts`, and hand-copying 26 budget
categories into a second source is precisely the drift the check exists to prevent.

**Decision.** The frontend **emits** its vocabularies as JSON from the same
`src/constants/` modules the product renders, and this repository **vendors** that file —
committed, under `app/services/resource_request/`, carrying the frontend commit it was
emitted from. Not a build-time fetch and not a generated Python module.

The two-repository split is why it is a vendored file and not a shared source: neither CI job
needs the other repository checked out, and a vocabulary change shows up as a reviewable diff
on both sides instead of as a silent drift.

**The enforcement lives on this side, and that is not a preference.** `test.yml` runs
`pytest tests/ -v` on every pull request here, so an assertion written against the vendored
copy — the counts listed below, the key spaces of §4.3 — actually runs before a merge. The
frontend's equivalent does not: its `src/__tests__/contract.test.ts` already parses
`docs/contract.md` for exactly this kind of checksum, but its CI workflow runs ESLint,
`tsc -b`, `check:tokens` and `check:i18n` and **does not run its test suite at all**. So the
emission can go stale over there without failing a pull request, and this repository must not
build a guarantee on top of that.

Two consequences, both named rather than assumed. The vendored file carries the frontend
commit it was emitted from, so a copy older than the contract is a visible fact in review
rather than an invisible one. And **the frontend's CI running its own suite is a gap with an
owner to find** — §10 carries it; until it closes, the emission is re-run and re-checked by
hand whenever a vocabulary moves.

Three properties it must have, and they are why the decision is worth writing down:

1. **Emitted, never hand-written.** A JSON file typed by a human is the second source again.
2. **It carries keys, not only labels.** The four vocabularies that already carry keys, the
   seven the contract specifies but the frontend has not implemented yet, and the two lists
   nobody has keyed at all — the **26 budget categories** and the **3 × 6 criteria** (§4.3).
   Minting those last slugs is part of this work, not a separate afterthought: without them
   BE-02 has nothing to put in `category_key` and `criterion_key`.
3. **The counts are asserted**, the way the contract's own checksums are: 45 text keys, 9
   project categories, 10 supported goals, 26 budget categories, 6 criteria per type, 5
   funds, 6 board columns, 4 decisions, 3 types, 30 max score. A list that comes back a
   different length fails the check rather than misleading a reader.

**This is not implemented here.** The emission is a build step in the frontend repository
and the check is BE-05's, and OBT-450 ships a design plus a skeleton. It needs an issue —
§10 carries it, with the note that it must land **before INT-02**, because that is the first
moment a request document crosses the wire.

---

## 10. Open questions

Nothing in this document is guessed. Everything that is not decided is here, with the gate
that owns it and what it blocks.

| Question | Gate | Blocks |
|---|---|---|
| What each of the five funds covers, and the old↔new mapping; Ready Vessels' fate | **GATE-01** (OBT-447) | BE-02's seed, BE-07 |
| **Which fund a request asks from** — no field for it exists anywhere in the form; `funds_support` is an essay, not a reference. Team chooses / derived from type / mesa assigns at triage are three different columns in three different tables | **GATE-01** (OBT-447) | BE-02, BE-07 — **BE-07 cannot debit a fund it was never told about** |
| Insufficient funds on a concurrent approve: refuse, or allow negative with a warning (§7.3) | **GATE-01** (OBT-447) | BE-07 |
| How teams get access — accounts, leader-link, or anonymous + submit (§5.2). Decides whether `created_by` is a FK or nullable | **GATE-02** (OBT-448) | BE-03, BE-04 |
| Whether the Gestor authors evaluations; whether `move_board` is the mesa's alone; whether the mesa may edit a team's request | **GATE-02** (OBT-448) | BE-03 — one cell each in §5.4's map |
| One evaluation per mesa, or one per member | **GATE-02** (OBT-448) | BE-02, BE-06 — it is the primary key of `rr_evaluations`, so the gate blocks the schema and not only the behaviour |
| Whether recording a decision moves the card, or only suggests the column | **GATE-02** (OBT-448) | BE-06, BE-08 |
| Audit trail for edits to the solicitação and the avaliação — who changed which field, who raised a score from 2 to 5, when. BE-07 covers money and BE-08 covers board moves; **nothing covers edits** | **GATE-02** (OBT-448) | BE-02 — history tables are cheap to add before there is data and expensive after |
| Online submission vs print/file vs both; where the attachment lives; what the team sees after submitting (§6) | **GATE-03** (OBT-449) | BE-04, INT-02 |
| **How a team learns its decision.** PRD §10 lists it and **no issue in either wave owns it.** *Revisar e reenviar* is the case that breaks silently — BE-04's revision flow assumes the team comes back | **GATE-03** (OBT-449) | unowned |

And five items with **no gate**, which need issues rather than answers:

1. **The vocabulary JSON emission and the two unminted key lists** (§9, §4.3) — must land
   before INT-02.
2. **The frontend's CI does not run its test suite** (§9), so the checksum test that guards
   its constants never runs on a pull request there. Its own repository's issue, and the
   reason this side's assertion is the one load-bearing check.
3. **Stable vocabulary keys in the frontend.** The contract specifies them; implementing
   them plus migrating stored drafts is unowned, and until it happens a draft stores
   Portuguese prose where BE-02 expects an enum.
4. **`alembic/env.py` sees no tables** (§8.1) — repository-wide, affects seven other
   applications, not this module's to fix unilaterally.
5. **A PostgreSQL path for the test suite** (§7.3), without which BE-07's concurrency test
   cannot exist.

Two things this document changes elsewhere, and neither should be silent:

- **FE-22's contract §5.1** gains the money decision of §7.2 — `Numeric(14, 2)` and
  ISO-4217 on the server. The contract asked to be updated with that answer.
- **The frontend's `CLAUDE.md` §3.2** tells a reader that the ecosystem's BE-01 audited this
  repository and that its output should be read. It did not, and there is none (§1.1).

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
| **Answered · GATE-0n** | The client decided it, in that gate. The record of the answer lives in the gate document; what sits here is what the answer costs this module. A section carrying it is not open and is not ours to revisit. |

The fourth marker is new, and it is what the three gates closing turned this document into.
**Open · GATE-0n** was written expecting to be deleted; deleting it would have thrown away the
part that is worth keeping — which shape was *not* chosen, and why the alternative cost
nothing to carry. Each one became **Answered**, with the discarded variant kept beside it.

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
| `organizations`, `organization_members` | **Not applicable.** | Nothing in the PRD or the contract scopes a request by organization. This row carried a condition — *if GATE-02 answers team access with an org* — and **the gate answered with individual accounts** (D1), so the condition never fires. The one shape that could still reach for it is BE-16's Líder de Base, who endorses *"que o projeto pertence à base dele"*: a base is not an `organizations` row today, and whoever builds it decides whether it becomes one. |
| `phases`, `project_phases` | **Not applicable.** | The board's six columns are this product's own key space (contract §4.1) and are not workflow phases of a translation project. |
| `notifications` | **BE-13's first read.** | Telling a team its decision is PRD §10's *notificações à equipe após a decisão*, which **BE-13** (OBT-480) owns since GATE-03 D5/D6 — see §10. It got its owner, and this table is the first thing that owner reads, not a new one to build. |
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
| `app/api/resource_requests/fund_assignment.py` | BE-11 | The mesa's triage decision — which fund a request draws from — and the selector for it. Gated on `assign_fund`, the one capability the Gestor does not hold on the money side. |
| `app/services/resource_request/` | BE-04…BE-08 | **All** logic and **all** queries. One operation per file with an `__init__.py` re-export — the newer house style (`app/services/access_request/`, `app/services/project/`, `app/services/auth/`), not the grouped `*_service.py` of `annotation_studio/`. |
| `app/services/resource_request/access.py` | BE-03 | Row-level scoping — the `app/services/annotation_studio/access.py` precedent. Anything past "does this user hold role X" is a service concern, never a router one. |
| `app/services/resource_request/capabilities.py` | BE-03 | The capability→roles map of §5.4 — a pure table — and the `holds_capability` service function that reads a user's roles against it. |
| ~~`app/services/resource_request/vocabularies.json`~~ `app/utils/resource_request_vocabularies.{py,json}` and `app/utils/resource_request_totals.py` | BE-05 | The vendored emission of §9 and the two derived sums. **Moved out of the service package** — see the note under this table. |
| `app/models/resource_request.py` | BE-04…BE-08 | **Pydantic** request/response models. `ConfigDict(from_attributes=True)` on read models, separate `Create` / `Update` / `Response`. |
| `app/db/models/resource_request.py` | BE-02 | **SQLAlchemy** tables. Must be re-exported from `app/db/models/__init__.py` — see §8.1. |
| `alembic/versions/20260NNN_rrNN_*.py` | BE-02 | Migrations. Single head, clean `downgrade -1`. |
| `tests/test_resource_requests/` | all | Extend; do not replace. |

⚠️ `app/models/` is Pydantic and `app/db/models/` is SQLAlchemy. There is no
`app/schemas/`. The naming trips every newcomer once.

⚠️ **The vendored emission is in `app/utils/`, not in the service package, and this row is
where the design rotted** (BE-05, OBT-454, 25/aug/2026). `tests/test_app_boots.py`
forbids any module in `app/models/` from importing `app/services/` — that inversion is what
closed an import cycle once — and §8.5 puts BE-05's field-level errors on Pydantic, in
`app/models/`. So the models must be able to read the vocabularies, and the service package
is the one place they may not read them from. §0's own tie-breaker applies: where this
document and the repository's rules disagree about **how this repository is written**, the
repository wins. `app/utils/description_rule.py` is the precedent and the same shape — a
domain rule that runs on two sides and must agree, imported by a DTO module
(`app/models/oc_recording.py`) and by services alike — and `app/utils/` is flat, so the
files carry a `resource_request_` prefix rather than forming a package its siblings do not
have. Neither file holds logic or touches the database, so nothing about them wanted the
service layer to begin with. `app/services/resource_request/` will be created by BE-04,
with the first operation that is one.

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

The table names below were **Provisional** — an `rr_` prefix and a plural, chosen only so the
rest of this document had something to point at. **BE-02 (OBT-451, 25/aug/2026) kept all nine
verbatim**, so they are Decided now; `20260825_rr01` is the migration that created them and
`app/db/models/resource_request.py` the models. The ownership and the invariants in the last
two columns did not move.

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

**Its uniqueness was the floor both gate answers share, and GATE-02 spent the line**
(BE-02, 25/aug/2026, tightened 28/aug/2026). §10 listed "one evaluation per mesa, or one per
member" as blocking the *schema*. It did not, because the two answers were not two shapes but
the same constraint at two tightnesses: `uq_rr_evaluations_snapshot_evaluator` was the looser
one and held under both, and tightening it on an empty table is one line where loosening it
after the mesa has used it costs data. **D5 answered *"a mesa quem decide"*** (OBT-448,
27/aug/2026), so the constraint is now `uq_rr_evaluations_snapshot` — one evaluation per
snapshot, and the table is still empty.

What the tightening takes away is worth naming, because it is the reason the looser form was
not simply *wrong*: two NULLs are never equal in SQL, so the old constraint allowed a snapshot
any number of **unauthored** evaluations — which is every row the seed writes. It now allows
one, the seed writes one, and a test is written against exactly the row the old form let
through.

**And the answer arrived with two records, not one.** The client asked for *"uma tag ou
assinatura de qual dos membros da mesa estava representando a mesa"* — that is
`evaluator_id`, and the person signs **on behalf of** the mesa, which is what lets the
evaluation be the mesa's and the signature be a person's. He also asked for *"registro de
quem eram as pessoas da mesa presentes na tomada de decisão"*, which is neither that column
nor derivable from it: it is `rr_evaluation_attendees`, cardinality N, **BE-02's shape and
BE-06's to fill**. It has the form of **minutes, not of an audit trail** — it says who was in
the room, so it carries no timestamp and no append-only trigger, and a room list written down
wrong is corrected rather than compensated. Confusing it with §4.4's trail would build a
table that answers the wrong question.

A refusal it makes on purpose: `user_id` is a real FK, so a mesa member with no account
cannot be recorded. That is the right failure rather than a gap, and BE-17 (OBT-477) — the
half of D1 the client separated himself — is what closes it.

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
- ~~**BE-02's:** whether the sections are `rr_request_sections` rows keyed
  `(request_id, section_id, field_key)` or one JSONB document per request.~~ **Answered: one
  document** (BE-02, 25/aug/2026). `rr_request_sections` is one row per request carrying a
  `content` JSON, and the deciding argument is the one this section already makes one level
  up — the sections are read whole by exactly one screen, and nothing in the product queries
  a single answer. The second argument is the one only the implementation could see:
  `rr_snapshots.document` freezes the same shape, so submission is a **copy** and not a
  projection, and BE-04 never grows a second serializer that can drift from the read path.
  It is its own table rather than a column on `rr_requests` so the board and the lists never
  drag the document they do not read.

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

**Half of it landed early, and only because the seed needed it** (BE-02, 25/aug/2026). The
sample board cards carry a `/30` total and `rr_evaluation_scores` stores rows, so the seed
could not be written without criterion keys. The eighteen slugs were minted in
`scripts/seed_resource_requests.py` — **prefixed by request type**, because *Vínculo com um
projeto de tradução ativo* is criterion 2 of both `treinamento` and `equipamentos` and an
unprefixed slug would collide — and lived there and nowhere else on purpose, since writing
them into `app/services/resource_request/` would have been the hand-copied second source §9
exists to prevent.

**Both lists are minted and the seed's copy is gone** (BE-05, OBT-454, 25/aug/2026). The
frontend now carries a `key` on each of the 26 budget categories and each of the 18 criteria,
in `budgetCategories.ts` and `criteria.ts`, and the emission of §9 brings both across; the
seed imports `CRITERION_KEYS` from `app.utils.resource_request_vocabularies` and the eighteen
literals left the file, which is exactly what the paragraph above promised would happen.

The two lists were minted differently and the difference is worth carrying: the **26 are
mechanical** slugs of the Portuguese label (`Chips (SIM)` → `chips_sim`, asserted by a test
over there that derives the slug and compares all 26), while the **18 are shortened** —
`Necessidade e urgência da tradução` is `traducao_necessidade_urgencia`, not the whole
sentence — because they are letter for letter the ones this repository had already minted,
and copying them was the point.

**Neither cost a `schemaVersion` bump over there**, because wave 1 still writes 26 budget
rows and 6 scores by index; the key is additive. That is also why the frontend's **seven
unkeyed vocabularies stayed unkeyed** — those *are* what a draft persists, so keying them
costs a migration of stored drafts, and the emission carries their Portuguese label as the
value instead. §10's item 3 stays open, and BE-05 validates what a client sends today.

### 4.4 The edit trail — **Answered · GATE-02**, tables here and behaviour in BE-15

D7 answered *"sim, sempre mantenha os históricos das mudanças, alterações etc."* (OBT-448,
27/aug/2026), over **both** the solicitação and the avaliação, field by field. The feature is
**BE-15**'s (OBT-475). **The tables are BE-02's**, and §10 is where that was written down
before the answer existed: a history table is cheap before there is data and expensive after.
Here that is literal — two `create_table` calls in a migration nobody has run, against a
second migration plus the admission that everything edited in between went unrecorded. BE-15
names this PR in its own text for the same reason.

`rr_request_field_history` and `rr_evaluation_field_history` carry the same five columns:

| Column | Why it is that and not something else |
|---|---|
| `field_key` | A string, not a column name. A request's fields live in **three** homes — six promoted columns on the spine, the 45 answers inside `rr_request_sections.content`, the 26 rows of `rr_budget_lines` — and one key space reaches all three where a design keyed on the catalogue reaches only the first. On the evaluation it is a criterion key, or `decision` / `comments`. |
| `old_value`, `new_value` | Nullable text. **Both sides**, because D7's own example is *quem subiu uma nota de 2 para 5*; nullable because a field that had no value has no old side; text because the three homes hold strings, decimals, dates and integers, and a trail that records only some of them is not a trail. |
| `changed_by` | `NOT NULL`, restricting on delete — the ledger's rule. A record of who changed something is worth nothing if the who can be forgotten, and D1 is what gives it a subject. |
| `changed_at` | Server-defaulted, like every other stamp here. |

**Both are append-only**, through the same trigger `rr_fund_movements` and `rr_snapshots`
already use — one line in `APPEND_ONLY_TABLES`, not a service rule the second caller will not
have. A history whose rows can be edited answers nothing.

The trail follows the **request**, not the snapshot: the thing being audited is the editing,
and a snapshot is by definition the version that stopped moving.

**One column deliberately not added here.** D6 says recording a decision moves the card, and
`rr_board_transitions` cannot today distinguish a move that came from a decision from a mesa
member dragging a card — which is precisely the asymmetry D6 insists on. An
`evaluation_id` there would tell them apart. It is **BE-08**'s (OBT-457) to add or to refuse,
because it is the issue that writes both sides of that transaction; naming it is this
document's job and building it is not. **Added** (BE-08, 30/aug/2026, `20260830_rr04`): once
the decision's move and the hand's drag converge on the same transition path
(`app/services/resource_request/_transition.py`), they land in the same table —
indistinguishable whenever no money moved — and only the column keeps D6's asymmetry legible
in the trail. A decision-driven transition names its evaluation; a drag carries `NULL`. No
`ON DELETE` action, like `movement_id` beside it: an evaluation that moved a card is not
unwound by disappearing.

### 4.5 The decision's write path — **Decided** (BE-06, OBT-455), and the order BE-08 follows

GATE-02 D6 made recording a decision an execution path: the Parte C save moves the card,
and in `approved` the same write appends to the ledger. BE-06 built that path in
`app/services/resource_request/save_evaluation.py`, and this section is the written order
BE-08 inherited. **Followed** (BE-08, 30/aug/2026): steps 2-4 are now `transition_stage`
in `_transition.py`, the one path a hand's drag also takes, so the order below is executed
once rather than stated twice — and a decision landing on a card already dragged into its
column deducts nothing and writes no second event.

**The order, inside one transaction with one commit under all of it:**

1. **The decision on the evaluation row** — with `evaluator_id` and `evaluated_at` stamped
   from the session and the server clock, never from the payload.
2. **The ledger movement, when the decision is `approved`** — `append_movement`, which
   takes the fund row's `FOR UPDATE` and flushes, never commits. The amount is the spine's
   `amount_requested` (item 9 — what a fund commits on approval, per BE-02's own docstring);
   the currency stays the column's default, which §7.2's open question about mixed-currency
   sums left deliberately unfrozen.
3. **The stage event** — the `rr_board_transitions` row, carrying `from_stage`, `to_stage`
   from the decision↔column mapping (`_decision_stage.py`), `moved_by`, and `movement_id`
   naming the movement of step 2.
4. **The request's `stage`.**

The issue's own prose said *decisão → evento de etapa → apêndice no razão*; the built order
swaps its last two steps because the schema decides it —
`rr_board_transitions.movement_id` is an FK to the movement, so the event **names** the
movement and cannot be written before it. Same transaction either way, which is the half
that was the requirement.

Three rules that travel with the order:

- **The implication runs one way.** A decision implies a column; a column never implies a
  decision. `_decision_stage.py` is a map over `RRDecision`, total in the direction that
  executes, with no entry to invent in the direction that must not — the mesa may still
  drag a card it never evaluated, and BE-08's hand-moves write no decision.
- **A recorded decision is not rewritten through the evaluation.** Scores, comments, the
  ata and the `team_note` stay editable afterwards — D7 audits exactly those edits — and a
  save carrying the same decision again re-fires nothing. Nor do those later edits
  re-sign: `evaluator_id` freezes with the decision, because D5's *tag* names who
  represented the mesa when it decided — who edited afterwards is BE-15's fact. A save
  carrying a *different* decision is refused (409): undoing an `approved` is a compensating movement plus a board
  move, which is BE-08's transaction, and building half of it inside the evaluation would
  either lose money or build BE-08 without its issue.
- **Approving with `fund_id IS NULL` fails, decidably** (409), before anything is written.
  The invariant is GATE-01 D4's and its owner is BE-11 (OBT-470); this path is where it
  bites first, so BE-06 enforces and tests it here, and BE-11 owns the rule wherever else
  a request can reach `aprovado`.

**Criteria versioning is decided: the key is the identity, and the text is presentation.**
The DoD asked for one of two shapes in writing — freeze the labels the mesa read, or
declare the key the identity — and it is the second, for three reasons that agree. The
labels are bilingual pairs, so freezing "the label the mesa read" would have to pick a
language the mesa did not pick — it reads both. The eighteen keys are already the stable
axis everything shares: `rr_evaluation_scores.criterion_key`,
`rr_evaluation_field_history.field_key` and the vendored emission name a criterion the
same way, so a reworded label changes what every evaluation *displays* — old and new alike,
which is what a clarification wants — and changes what none of them *is*. And the type
prefix on the slug (`traducao_necessidade_urgencia`) keeps a key honest in review: a label
edit that changes the criterion's meaning under an unmoved key shows up as a slug that no
longer says what its label says. The consequences, stated so nobody re-derives them: a
**rewording** costs a frontend label edit and a re-vendored emission, and touches no stored
row; a **change of meaning** mints a new key, and evaluations scored under the old one keep
it — a key never leaves the vendored history while a score row names it, the same
superseded-not-deleted rule the fund table set in contract §3.1. `load_evaluation` already
reads it that way: a stored key the current list does not carry sorts last and displays,
because it is history, not an error.

**D7's trail is not instrumented here, and that is written rather than left to be noticed.**
The evaluation write updates rows and creates none in `rr_evaluation_field_history`; the
field-by-field diffing — old value, new value, who, when — is BE-15's (OBT-475), and it
**wraps this write** when it arrives rather than this issue planting half of it. Two
reasons: a trail written by one caller and not by the next is worse than none, and BE-15
owns the diffing rule (which of the three homes a key lives in, how a replaced score row
reads as a change and not as a delete-plus-insert) — planting an ad-hoc version here would
stand a second design where §4.4 already names one owner. Until BE-15 lands, edits to an
evaluation are visible only as its `updated_at` moving, and that gap is BE-15's issue by
name.

---

## 5. Seam A — authentication and access (GATE-02)

**GATE-02 closed on 27/aug/2026** (OBT-448), and it chose **variant 1**: every actor is a
`users` row, and `apps.auto_approve = true` — *"quem tiver uma conta"* (D1). Both variants stay
drawn below, because the point of having pre-drawn them is exactly this moment: the answer
costs this section a marker and no design.

The gate's own reading of what still blocks BE-03 is **nothing**. What came out of it as
separate work — granting access to the three privileged roles — is **BE-17** (OBT-477), and it
is not a prerequisite: `scripts/grant_app_role.py` covers the interval, as the first accounts
were always going to be born.

**BE-03 (OBT-452) built what §5.4 designed**, and the parts of it that moved say so in place.

### 5.1 Variant 1 — shared `shema-api` principals · **Decided**, and already built

Every actor is a `users` row holding a role in this app. This is GATE-02's own stated
default (*"`shema-api`'s existing auth is the default answer; deviating needs a reason"*),
and BE-00 built it: `_deps.py` is the entire seam, and a request's author is a
`users.id` FK.

### 5.2 Variant 2 — separate principals · **Answered · GATE-02**, and not the shape chosen

**Ruled out by D1.** Kept because a variant that was ruled out is the cheapest possible
record of why the column below is what it is — and because it is the design that would have
to be rebuilt if the client ever reopens *leader-link*.

Had the client answered *leader-link* or *anonymous fill + submit*, a team would not be a
`users` row. What would have changed:

- A table of claims — a token, what it grants, when it expires, which request it is bound
  to — and a resolver that turns one into the same object `CurrentUser` produces.
- `_deps.py` gains a second dependency that accepts either, **behind the same
  `Annotated` aliases**.

What **does not** change, and this is the point of stating the variant at all: no router
signature, no service signature, and no row in the capability table. Every route already
takes `user: CurrentUser`; a resolver that answers the same shape is a swap inside one file.

The cost this section named rather than let anyone discover — an anonymous author has **no
stable identity**, so `rr_requests.created_by` would be nullable and the audit trail would
lose its subject — is **not paid**. With `auto_approve` every person who fills the form is
authenticated, so `created_by` is a **`NOT NULL` FK** to `users.id` on both request and
movement. **BE-02 is where that stops being a sentence and becomes a column**, and it is the
same answer that gave D7's audit trail its subject: the document has an owner, and the trail
is written about that owner.

### 5.3 What both variants share — safe to build now

The request's author column exists either way; only what it points at moves. The evaluation
is always authored by a mesa principal, which exists in both variants. Every capability
check, every row-scoping rule, and the whole of §4 are untouched by the gate. **BE-02 was
not blocked by GATE-02** for anything but the nullability of one FK — and the answer settled
that one too, in the direction that removes the nullability rather than keeping it.

### 5.4 Capabilities are not roles — the delta the platform does not cover · **Built** (BE-03)

`require_app_access(app_key)` and `require_role(app_key, role_key)` answer exactly one
question each: *does this user hold any role in this app*, and *does this user hold this
one role*. The frontend's model is **seven** capabilities across three roles — five when this
section was written, and GATE-01 and GATE-02 moved it to seven:

| Capability | `equipe` | `mesa` | `gestor` | Settled by |
|---|---|---|---|---|
| `edit_requests` | ✅ | ✅ | ✅ | **GATE-02 D4** — *"a mesa pode alterar também"* |
| `view_evaluation` | — | ✅ | ✅ | already decided |
| `edit_evaluation` | — | ✅ | — | **GATE-02 D3**, confirmed 28/aug — *"nem pontua nem decide"* |
| `manage_funds` | — | ✅ | ✅ | already decided |
| `move_board` | — | ✅ | **✅** | **GATE-02 D3** — the cell that moved |
| `assign_fund` | — | ✅ | — | **GATE-01 D4**, re-ask closed 28/aug — *"somente a mesa"* |
| `allocate_funds` | — | — | ✅ | **GATE-01 D6** — the first capability the mesa does not hold |

Mirror it from `src/auth/capabilities.ts` field for field; that file is the owner and this is
the copy. Two things about it are easy to get wrong from the table alone. **`manage_funds` is
the Painel's entry gate**, not a money permission — narrowing it to make room for
`allocate_funds` would take the whole panel away from the mesa. And **`assign_fund` and
`allocate_funds` are control capabilities, not screen ones**: they live inside a surface some
other capability already opened, which is why neither adds a route of its own.

**Two of those cells were re-asked on 28/aug/2026, and both came back where they were.**
`edit_evaluation` had been recorded as *confirmed rather than merely left standing* while the
FE-22's contract still listed the confirmation as pending — the text was ahead of its proof. The
proof arrived: *"ele nem pontua nem decide, essa função é exclusiva da mesa"*, which settles
27/aug's *"o Gestor pode alterar"* against its own *"só não aprova"* in favour of the second.
And `assign_fund` was carrying GATE-01 D1's aside — that the Gestor would define which fund a
project draws from — as a live re-ask; asked again, the answer was *"somente a mesa"*. Neither
cell moves, `move_board` least of all: moving a card is still not deciding (D6).

**An eighth cell is decided and arrives with BE-10** (OBT-471). The fund area does *"os 3"* —
create, rename, retire — *"o Gestor"* creates, and renaming and retiring *"seguem a de criar"*:
**one** capability over three verbs, the Gestor's alone. That it is a **control** capability and
not a screen one is ours to decide (Daniel, 28/aug/2026) and not the client's sentence, and the
consequence is mechanical: as a screen capability it would match no role in the frontend's
`SCREEN_CAPABILITIES.every(holds)` and the mesa's fixture account would vanish — the trap the
`?` cell of D3 sprang once already.

**A fourth role is coming and is not here yet.** GATE-02 D2 answered that the **Líder de
Base** enters the system — the narrowest of the four, holding one endorsement capability and
the reading it needs, with neither `edit_requests` nor `view_evaluation`. It is a new
`role_key` in this repository (BE-00 seeded three), a fourth column in `capabilities.ts`, the
screen where the endorsement happens, and the rule that an unendorsed request does not
proceed. **BE-16** (OBT-476) owns all of it, and it is the only issue that touches both
repositories.

Four of the seven are held by **more than one role**, and `require_role` cannot express an
OR. Guarding `view_evaluation` as `MesaUser` would refuse the Gestor, whose whole point is
that asymmetry — it sees the evaluation and the money and changes neither the evaluation nor
the board.

Two more reasons not to guard on roles directly: `permissions` and `role_permissions` exist
as tables but **are not wired into `access_control.py`**, so there is no finer platform
primitive to reach for; and GATE-02 was expected to move a cell in that table, which had to
cost one line and not a sweep through the routers. **It moved one** — `move_board` gained the
Gestor — and BE-16 will add a whole column. The prediction held, and it is the reason the map
is data.

**Decision, and what BE-03 built.** The map is data, in
`app/services/resource_request/capabilities.py`, mirroring the table above field for field.
Beside it, `holds_capability(db, user_id, app_key, capability)` reads the user's roles
through `authorization_service` and answers against the map; `_deps.py` gained the
`require_capability(capability)` factory that wraps it in `Depends`, plus one `Annotated`
alias per capability so a later route annotates rather than assembles. That split is the
house rule applied literally — the query lives in a service and the api layer does
dependency wiring — and it is the same shape `app/core/access_control.py` already has.

`app_key` is a **parameter** of the service rather than a constant beside it, so the literal
stays named once in `_deps.py`, which is where all eight applications in this repository
keep theirs and where `test_the_app_key_is_named_once_in_the_module` looks.

**One table is written and the other is derived.** `ROLE_CAPABILITIES` is the frontend's own
shape and the only thing typed by hand; `CAPABILITY_ROLES` is its inversion, which is the
direction a guard asks in. Two hand-written tables would be two statements of one fact, and
the day they disagreed every test would still be green.

**Module-local, not `app/core/`** — `access_control.py` is shared surface for eight
applications and this is one application's model until a second one needs it.

**How the two stacks are held together** is §9's mechanism, applied to a second artefact:
the frontend emits `docs/capabilities.json` from `src/auth/capabilities.ts` through the same
`ssrLoadModule` load `emit-vocabularies.mjs` uses — that emitter reserved this half by name
— this repository vendors the file beside the map carrying the frontend commit it came from,
and `test_capabilities.py` compares the two in both directions.

The map is deliberately **not read** from that file at runtime, and this is the one place
that choice earns its keep: a vendored copy that arrived truncated would change who may
approve money, silently, and the point of a mirror is to fail loudly.

**One thing this artefact has that the vocabularies do not**: `npm run check:capabilities`
runs in the frontend's own lint workflow, so a table changed without re-emitting fails a
pull request *there* too. It does not close §10's item 2 — that CI still does not run the
vitest suite — but it means this emission cannot go stale at the source, which is the
weakness §9 had to design around. The two checks fail for different reasons and both are
needed: one says the emission is old, the other says the vendored copy and the map disagree.

### 5.5 Two platform behaviours to design around

- **A platform admin bypasses both guards unconditionally.** `require_app_access` and
  `require_role` each return early on `user.is_platform_admin` before consulting a grant.
  Negative tests written per role must not use an admin account, and no capability check
  in this module can be assumed to have run for one.
- **A grant written outside this process is not seen until the entry ages out.** Both guards
  now read one cached list per user and app (`app/core/auth_cache.py`), so they agree with
  each other — the five-minute disagreement this section was written about is gone, and the
  window itself is **thirty seconds**, not five minutes: `AUTH_CACHE_TTL_SECONDS`, cut by
  ENG-551 as a measured trade rather than a library default. `grant_app_role` and
  `revoke_role` call `invalidate_roles(user_id)`, which closes the door on the next request
  for a change written here; one written in the Tripod Console or by hand waits out the
  window. BE-00's conftest clears the cache around every test so a test can check both sides
  of one user.

  **`holds_capability` does not cache at all**, and that is the difference between *may this
  account use the app* — asked on every request, worth caching — and *may it do this one
  thing*, asked on the writes that matter.

---

## 6. Seam B — how a request travels (GATE-03)

**GATE-03 closed on 27/aug/2026** (OBT-449), and it chose **(b)**: *"equipe envia pelo
sistema"* (D1). The other two columns stay drawn for the same reason §5.2 does — a discarded
option is the cheapest record of why the chosen one looks the way it does.

**BE-04 (OBT-453) built the middle column.**

| | (a) mesa-entered | **(b) team submits online · chosen** | (c) both |
|---|---|---|---|
| Who writes the draft | a mesa principal | **the team** | either |
| Routes | `POST/PATCH /requests` under `edit_requests`; no submit route at all | **`POST/PATCH /requests` for the author, `POST /requests/{id}/submit`** | both, and submit accepts either author |
| Where the snapshot is taken | on creation — the record *is* the received document | **on `submit`** | on `submit`, and on creation for a mesa-entered one |
| The attachment | a note (`attachment_note`), the file arrives by another channel | **an upload endpoint** — D3, *"anexa o arquivo no sistema"* | the note is the floor; the upload is additive |
| What the team sees afterwards | nothing — it is outside the system | **the status, through its own account** — D4, and nothing else | — |

Three answers ride on the chosen column, and each is somebody's issue rather than a line here:

- **The attachment becomes a file** (D3). Not the existing `POST /api/uploads/image`, which
  accepts images only, caps at 5 MB and returns a **public URL** — pointing a team's budget at
  a public bucket. The pattern to copy is the Sound Necklace artifacts: content-addressed key,
  private bucket, signed URL. **BE-14** (OBT-474). Formats and the size ceiling went back to
  the client; the bucket, the key and the signed URL did not depend on that answer.
- **The team sees status and nothing else** (D4) — *em análise*, *aprovado*, *aprovado com
  condições*, *revisar e reenviar*, *não aprovado*. **Notes and mesa comments: never.** The
  capability table does not move because of this, which was the declared risk of the question:
  the team still holds no `view_evaluation`, and BE-04 still serves the document without the
  evaluation nested inside it.
- **The team is told, on both channels** (D5) — e-mail to the account address *and* in-app,
  fired on the **saving of Parte C**, never on a column transition. **BE-12** (OBT-473) builds
  the e-mail infrastructure and **BE-13** (OBT-480) the notification, in that order and not the
  other: the existing `request_password_reset` sends synchronously, before the commit, with
  `raise_for_status` — copied as it stands, a provider outage would make the mesa's decision
  fail and roll back.

### 6.1 What is common to all three — and what the answer made true

- A request has an author and a creation time.
- **Submission freezes a snapshot**, and evaluation points at the snapshot rather than at a
  mutable document. Only *who* triggers the freeze moves between the options.
- A revision is a new draft linked to the evaluated snapshot, opened by the `revise`
  decision. This is BE-04's, and it is the case that hurts most if the team is never told —
  the whole flow assumes they come back.
- `attachment_note` is already one of the contract's 45 keys, so **the note field exists in
  every option**. An upload endpoint is additive to it and never replaces it: a team on a
  field connection that cannot upload still has to be able to say what it sent. Whether the
  note survives beside the file is BE-14's call, and it is not a tidy-up: `attachment_note`
  is one of the 45, so removing it **moves the contract's checksum**.

**What the answer made true, and it is the least obvious consequence of (b):** the immutable
snapshot now freezes **what the team wrote, at the instant the team sent it**. Under (a) it
would have frozen a transcription, and every revision chain would have been anchored to one.

### 6.2 What the gate actually changed

The route surface and the attachment's shape, and nothing else — **and the gate says so in
its own words**: *"nenhuma resposta força redesenho de backend"*. Nothing in §4 moved. BE-04
keeps its full shape rather than shrinking, `POST /requests/{id}/submit` exists, and the
author column is **`NOT NULL`** by GATE-02's answer (§5.2) rather than nullable by this
gate's. That is the whole reason for drawing the seam before the answer arrived: the answer
cost this section a column heading.

One thing it made false in the product, and it is worth naming here because it is the only
one of its kind: the item-10 sentence — *"envie junto ao salvar/imprimir"* — is
**client-approved copy that the client's own answer invalidated**. Rewriting it is bilingual
and needs the client's approval again. It is a frontend issue, not this module's, and it is
not polish.

**What BE-04 added to the list above, and it is the one thing this seam had not predicted.**
Submission takes **no payload**. The draft is already on the server — that is what (b)
means — so freezing what is stored, rather than what a last request carries, is what makes
*the mesa evaluated what the team submitted* true without the two having to agree. It is
free because `document()` **is** the payload shape: what comes out of the read path goes
straight into `RequestSubmissionIn`, and the same bytes go into `rr_snapshots.document`.

`scripts/seed_resource_requests.py` used to build that shape itself. It was the second
serializer §4.2 forbids by name, and it had already drifted — five of the spine's values
where the real one carries all of them. It calls `document()` now.

**Reconciliation is *latest save wins*, and the loser is told.** A draft filled offline and
a server row that moved since are two saves, not two halves of one document: merging them
would invent a paragraph neither side wrote. The `PATCH` carries the client's own
`saved_at`; when the server's row is newer the incoming copy is **discarded** and the answer
names which side won and when each was saved. Discarding is the harsh half — the alternative
loses the newer work silently, and this loses the older work loudly, to a caller that still
holds the payload it tried to send.

**Row scope is not a capability, and this is where that was decided.** `edit_requests`
belongs to all three roles (GATE-02 D4), so it says *may act on requests* and says nothing
about which ones. `app/services/resource_request/_scope.py` is the one place in the module
that reads a role rather than a capability, and it reads it for a **scope**: a caller who is
only `equipe` reaches what it authored, anyone else reaches all of it. Written as *only
equipe* rather than *is mesa or gestor* so the Líder de Base of BE-16 does not silently
inherit the team's narrow view before anyone decides what he should see. The alternative —
a `read_all_requests` row in contract §5.3 — would put a capability the client never saw
into a client artefact.

Two consequences worth stating because they are easy to get backwards. Out of scope answers
**404 and not 403**, since a 403 confirms the id exists and that is the one thing a team must
not learn about another team's request. And a request that has been submitted answers **409**
to an edit: the way back in is a revision, which is a new row pointing at the snapshot the
mesa read.

### 6.2 What the gate actually changed — and the prediction it settled

The route surface and the attachment's shape, and nothing else. **That held.** Nothing in §4
moved, no aggregate was redesigned, and the (a) branch — which would have shrunk BE-04 to
mesa-entry endpoints — was simply not taken. The nullable author column was GATE-02's cost
(§5.2) and its answer left it filled in practice.

Two open client questions land on this issue and neither blocked it, which is the same thing
the gate's own closing comment said: *"nenhum muda a forma do agregado"*.

- **Whether submitting returns a receipt, and whether it carries a number** (contract §7,
  marked as blocking *the submission issue* — this one). `SubmissionOut` answers with the
  request, the server's `submitted_at` and the snapshot id, and **invents no number**.
  Adding one later is additive; removing one after teams have seen it, after BE-13 has
  quoted it in an e-mail and after it has become how people refer to a request, is not.
- **Whether the Ponto focal's signature becomes an electronic acceptance.** The Líder's half
  is answered (BE-16); this one is not. `tpp_name` and `tpp_date` are a typed name and a
  typed date today, which is what `RequestSubmissionIn` already demands. An answer changes
  what those two columns *mean*, not their shape.

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

### 7.3 Concurrency: what gets locked — **Decided; implemented by BE-07**

Balances are sums, so there is **no balance column to lock**. The row that exists and can be
locked is the fund itself:

```
SELECT … FROM rr_funds WHERE id = :fund FOR UPDATE
```

taken inside the same transaction that appends the movement and writes the stage change.
Two mesa members approving against one fund then serialize on that row: the first commits,
the second recomputes the sum *after* the first is visible and gets a decidable answer.

**GATE-01 answered it — allow, with a warning, never refuse** (OBT-447 D5, 26/aug/2026).
Both approvals succeed, the fund goes negative and the screen says so; the control is human.
Wave 1 already rendered a negative *disponível* by inheritance, and the gate made that the
behaviour rather than a bug to fix — a decision instead of an accident. **No
`insufficient_funds` response shape is frozen anywhere in this module, none exists anywhere
in the product, and none is to be invented here.** It is still one branch, and BE-07 writes
the warning one.

**What the answer does not relax is the paragraph above it.** The two approvals still have to
serialize on the fund row, or one deduction is lost and the sum lies about money. The answer
removes the refusal *after* the lock, not the lock — *both succeed* and *both succeed and the
total is right* are different guarantees, and the client decided only the first.

⚠️ **The test for this cannot run where the other tests run, and it fails silently.**
`pytest` runs on SQLite (`tests/conftest.py` sets `sqlite+aiosqlite`), and SQLAlchemy
**drops the clause without a word** on that dialect — the same `with_for_update()` compiles
to `… WHERE rr_funds.id = %(id_1)s FOR UPDATE` on PostgreSQL and to `… WHERE rr_funds.id =
?` on SQLite. So a concurrency test written against the default suite would lock nothing and
pass anyway, which is worse than not having one. BE-07's double-approve test needs
PostgreSQL, and the only workflow with a postgres service today is `migrations.yml`.
Either that job grows a step or `test.yml` gains a service. **The test exists and is
gated** (BE-07, OBT-456): `test_ledger_concurrency.py` runs only when
`RR_POSTGRES_TEST_URL` names a disposable PostgreSQL database and skips with that reason
declared — verified green against PostgreSQL 14. It holds the lock open on one session
while a second attempts the same fund row, and asserts the second acquires only after the
first commits — both succeed, the balance ends at **−300.00**, negative and correct.
**The `test.yml` wiring is written and could not ride BE-07's own branch**: no credential
on the machine that built it carries the `workflow` scope, so the service block and the
variable travel in the pull request's description for someone with the scope to land.
Until that lands, the test runs wherever the variable is set, and CI shows the declared
skip rather than a false green.

**How BE-07 implemented the rest, in one paragraph.** The ledger has exactly two writers —
`append_movement` for allocation, commitment and approval deduction, and
`reverse_movement` for the compensating entry, which copies fund, request, amount and
currency from the movement it reverses (a caller that could state the amount could
mis-state it; a partial correction is a full reversal plus a new entry). Both take the
`FOR UPDATE` above, both **flush and never commit** — the caller owns the transaction,
which is the contract BE-08's stage-change-plus-movement atomicity is built on. A reversal
is not reversed, and a movement is not reversed twice. Balances are `fund_balances`, a
grouped sum where a reversal counts against the bucket of the movement it names (read off
`reverses_id`, not off a sign convention); the read surface is `GET /funds`,
`GET /funds/{id}/movements` and `GET /requests/{id}/movements`, all gated on
`manage_funds` — a team follows its status and never the ledger (GATE-03 D4). The seed
now writes the fund **empty**: GATE-01 D6 has funds born at zero with the Gestores
allocating, so the prototype's 480.000 stayed a frontend dev fixture and the seeded panel
opens at −159.000 — D5's warning state, telling the truth about money nobody put in.

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
tables visible after importing app.db.models:   75
```

So `alembic revision --autogenerate` today compares an **empty** metadata against the
database and would emit a migration dropping all 75 tables. That is not hypothetical for
BE-02, which is the next issue and authors the first migration of this module. (Both counts
were 0 and 64 when this was written; the second is re-measured at BE-02, after `main` and
this module's own nine tables — the zero is what does not move.)

The repository has been living with it: only 2 of the 81 revisions carry alembic's
autogenerate marker, and both are the legacy hash-named ones. **The 78 others were written
by hand, and BE-02 wrote its own by hand too.** Re-exporting the new model file from
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
`ALTER TYPE … ADD VALUE IF NOT EXISTS` inside `op.get_context().autocommit_block()`.

~~guarded by `if op.get_bind().dialect.name == "postgresql"`, because the same migration has
to run under SQLite in CI.~~ **No migration in this repository runs under SQLite, and none
can** (BE-02, 25/aug/2026, measured). `alembic upgrade head` dies on the first revision:
`20260226_0001` creates `users` with `server_default=sa.text("now()")`, which SQLite rejects
outright. Alembic is invoked in five places — `docker-compose.yml`, `Dockerfile.dev`,
`scripts/restore_local_db.sh`, `migrations.yml` and the deploy — and every one of them points
at PostgreSQL; the test suite builds its schema from `Base.metadata.create_all`, never from a
revision. So a dialect guard inside a migration is dead code no test can reach, and
`20260825_rr01` writes plain plpgsql. The **models** are where the split is real, and that is
where `append_only_ddl` puts it: one plpgsql trigger on PostgreSQL, a `RAISE(ABORT)` pair on
SQLite, chosen at `after_create` from the dialect in hand.

**One default in that idiom is worth naming, because it is silent.** `Enum` has carried
`create_constraint=False` since SQLAlchemy 1.4, so on a dialect with no native enums the
column is a bare `VARCHAR` and nothing refuses a fifth decision string — on precisely the
dialect the tests run. `app/db/models/resource_request.py` turns it back on: PostgreSQL emits
no CHECK beside a native enum, so it costs production nothing, and it is what lets a test
watch the database refuse `'rejected'`.

The four decision strings are frozen by the contract and will not grow, which is what makes
a native enum the right call for them. The six board columns are frozen too. Anything the
client might extend — the fund list, frozen at **one** by GATE-01 with four names pending
and BE-10's editable area coming — should be a **table**, not an enum.

### 8.3 Migrations: naming, one head, and a clean downgrade

Files are `YYYYMMDD_NNNN_snake_description.py` with `revision` equal to the prefix
(`20260819_room08`); the internalization-room series swapped the counter for a semantic tag,
so `20260NNN_rr01_…` with `revision = "20260NNN_rr01"` follows the precedent.
`migrations.yml` enforces the single head against a real PostgreSQL — it runs
`upgrade head`, `downgrade -1`, `upgrade head`, with `PYTHONWARNINGS=error::UserWarning`
because a duplicate revision id is only a warning.
**`downgrade()` is not decorative here; a migration that cannot come back down fails CI.**

~~There is exactly one head today, `20260819_room08`.~~ **It moved while this document was
in review, and the parent to hang a new revision off is read, never remembered** (BE-02,
25/aug/2026). `main` grew twelve revisions and three join revisions in that window, and the
head is `20260823_join4`, whose parents are `("20260821_join3", "20260819_room08")` — so
`room08` already has a child. `20260825_rr01` hanging off it would have been a **second
head**, and the failure is invisible where it is written: a stacked PR's CI runs against its
own base, where the single-head check is content, and the graph forks only when the branch
reaches `main`. `main` also grew the guard that catches it — `tests/test_migration_graph.py`,
which asserts one head *and* that the join names every line that would otherwise be one.
Bringing `main` down the stack before writing a revision is what makes both true; the
command is `git log --oneline -1 origin/main -- alembic/versions`, not memory.

**It moved a second time, and the second time is what turns the observation into a rule**
(29/aug/2026): `main` grew `20260828_seg01` off that same `join4` while this stack sat in
review, so `20260825_rr01` — written against `join4` four days earlier — was re-pointed at
`seg01`. Reading the head once, when the file is created, is not enough: the head keeps
moving for as long as a stacked PR waits, so the parent is re-read at **every** merge of
`main` down the stack. And nothing on this side says otherwise in the meantime — BE-01,
BE-02 and BE-05 were all green, `migrations.yml` included, because each ran against its own
base. The guard only speaks when `main` arrives, which is the moment to listen to it.

### 8.4 A request and its snapshot reference each other, so a flush needs telling

`rr_snapshots.request_id` points at the request and `rr_requests.revision_of_id` points
back at the snapshot a revision answers — the second is the contract's own wording, and it
is what says *which* evaluated version a revision came from when a request has more than
one.

The DDL side is solved and invisible: `use_alter=True` on the model, an `ALTER TABLE ADD
CONSTRAINT` after both tables exist in the migration, and an inline FK on SQLite, which
cannot ALTER and therefore does not need to.

**The unit of work is not.** No `relationship()` is declared anywhere in this module — the
services query explicitly, as the house rules ask — so a flush orders its inserts from the
table graph alone, and that graph has a cycle. Measured: adding a request, its snapshot and
its evaluation in **one** flush wrote the evaluation first and died on the foreign key. The
rule for BE-04, BE-06 and BE-08 is therefore one line long: **`await db.flush()` between the
request and its snapshot**, never one flush for both. `scripts/seed_resource_requests.py` and
`tests/test_resource_requests/test_schema.py` both do it that way, and the second is where it
was found.

### 8.5 The error envelope carries no field, and BE-05 needs one

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

**One limit found implementing it** (BE-05, OBT-454, 25/aug/2026). Pydantic locates an
error by *structure*, so a bad answer inside the `fields` dictionary reports
`loc: ["fields"]` and not `["fields", "lang_script"]`. Giving each answer its own location
would mean making every answer an object on the wire, which is a payload shape nobody asked
for — so the location stays `fields` and **the message names the offending keys**
(`lang_script: answer outside its vocabulary`). Every top-level claim — `stated_total`,
`budget`, `declaration`, `team`, `checks` — locates on itself, exactly as measured above.

**A second limit, found in review: riding on Pydantic means only `ValueError` is a 422.**
`Decimal.quantize` signals `InvalidOperation`, which Pydantic does not convert, so the
sub-cent guard turned `{"amount": "1E+30"}` into a 500 — the one payload in the module that
answered with a stack trace instead of a refusal. The money guard now checks magnitude
against what `Numeric(14, 2)` actually holds *before* it quantizes. The general rule for
anything added here: a validator may raise only `ValueError`, and arithmetic inside one has
to be reached with its own preconditions already checked.

### 8.6 The app key is named once, and a test says so

`tests/test_resource_requests/test_access.py::test_the_app_key_is_named_once_in_the_module`
globs `app/api/resource_requests/*.py` and fails if any file but `_deps.py` contains the
literal app key. Keep it that way: it is what made GATE-02's answer a one-file change.

**The service half stays out of the glob by not naming the key at all.** BE-03 gave the
module a second half under `app/services/resource_request/`, and `holds_capability` takes
`app_key` as a parameter rather than importing or re-declaring it — which is also what the
other seven applications here do, and what keeps a service from importing out of `app/api/`.
The one place outside the module that spells the literal is `20260828_rr02`, deliberately: a
migration must not import from `app.`, since that builds a database engine at import time and
an unrelated import error would fail the deploy before a statement runs.

---

## 9. The vocabulary mirror — how a Python check reads a TypeScript source

BE-05's DoD requires the constants to be **checked in CI against FE-22's contract** so the
two stacks cannot diverge. The contract raises the obstacle and hands it to this issue by
name: BE-05 runs in Python and cannot read `src/contract.ts`, and hand-copying 26 budget
categories into a second source is precisely the drift the check exists to prevent.

**Decision.** The frontend **emits** its vocabularies as JSON from the same
`src/constants/` modules the product renders, and this repository **vendors** that file —
committed, as `app/utils/resource_request_vocabularies.json`, carrying the frontend commit
it was emitted from. Not a build-time fetch and not a generated Python module. (§3's table
records why it sits in `app/utils/` and not in the service package.)

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

**The first consequence collected on itself, and the failure was not staleness** (28/aug/2026).
The vendored copy named `2bac57a`, a commit that existed only on the branch the frontend's PR
#28 was *based* on — and that base never reached `main`: its content was reapplied inside
another pull request and landed with a different sha, leaving the branch alive, not an
ancestor of `main`, and the provenance pointing at a commit nobody would ever be able to
check out from the merged history. The content was correct the whole time; what was broken
was the ability to reproduce it, which is the entire job of the field. Re-based onto `main`
and re-emitted, it now names `067458c`, and **only the provenance moved** — the eleven lists,
the 26 categories, the 18 criteria and the 45 keys came back byte for byte, which is the
independent confirmation that the three gates touched no vocabulary.

The general rule it leaves behind, worth more than the incident: **a provenance is only worth
the line it will merge into.** Naming a commit is not enough — it has to be a commit that
survives the merge, and a branch that is not an ancestor of `main` is not proof that it will
be one.

Three properties it must have, and they are why the decision is worth writing down:

1. **Emitted, never hand-written.** A JSON file typed by a human is the second source again.
2. **It carries keys, not only labels.** The four vocabularies that already carry keys, the
   seven the contract specifies but the frontend has not implemented yet, and the two lists
   nobody has keyed at all — the **26 budget categories** and the **3 × 6 criteria** (§4.3).
   Minting those last slugs is part of this work, not a separate afterthought: without them
   BE-02 has nothing to put in `category_key` and `criterion_key`.
3. **The counts are asserted**, the way the contract's own checksums are: 45 text keys, 9
   project categories, 10 supported goals, 26 budget categories, 6 criteria per type, **1
   fund**, 6 board columns, 4 decisions, 3 types, 30 max score. A list that comes back a
   different length fails the check rather than misleading a reader.

   Two of those numbers carry a date. **Funds was 5 until GATE-01 answered** (OBT-447,
   26/aug/2026): only *Shema Línguas* remains and the other four names are undecided, so the
   emission carries one. The count is expected to move again — the client floated an editable
   fund area (BE-10, OBT-471) — and moving it is the check working, not the check being
   wrong. **Supported goals stays at 10 while the gate's other half is open**: whether *Ready
   Vessels* survives among them is the one GATE-01 question still unanswered (§10), and it is
   this number's owner the day it is.

~~**This is not implemented here.**~~ **Implemented by BE-05** (OBT-454, 25/aug/2026), in
both halves. The frontend's `scripts/emit-vocabularies.mjs` loads `src/contract.ts` through
the app's own resolver — Vite's `ssrLoadModule`, so no new dependency and no parser over
TypeScript to age — and writes `docs/vocabularies.json`;
`app/utils/resource_request_vocabularies.json` is that file byte for byte, and
`resource_request_vocabularies.py` beside it is the only reader (§3 records why it is not
in the service package). `tests/test_resource_requests/test_vocabularies.py`
carries the ten counts above and the key spaces of §4.3.

Four things the implementation settled that the decision above did not say:

- **It carries only what BE-05 reads.** The capability table of §5.4 is BE-03's and the
  board's transition rules are BE-08's, and emitting them today would ship data nobody
  reads. Each costs one line in the emitter on the day it has a reader.
- **The seven unkeyed vocabularies emit their Portuguese label as the value**, because that
  is what a client sends today. The stable keys the contract's §5.2 designs for them are
  not emitted: they are not true yet, and the server validates what exists.
- **`emitted_from` carries `-dirty`** when the emission ran over an uncommitted source, so
  a provenance can never point at a commit that does not contain what was emitted.
- **One map could not be emitted, and it is named rather than faked.** Which of the 45 text
  keys each section owns is prose in the contract's §1.2 and inline in components over
  there — no data structure states it. So `SECTION_TEXT_FIELDS` is written in
  `vocabularies.py`, and a test partitions the 45 emitted keys against it in both
  directions: an orphan row and an unowned section each fail.

**And a fifth, added in review: the emission also carries `tableRowKeys`.** The first round
gave the *asked and answerable* rule to `fields` alone, so a row of `langs`, `team` or
`chrono` could carry any key with any value and be stored as though the question had been
put — the same **absent means not asked** distinction the mesa reads, losing its meaning one
level down. Both halves are now data rather than prose: `TABLE_ROW_KEYS` comes from the
frontend's own empty-row seeds (which is what `readRows` rebuilds every stored row from, so
a key outside them does not survive a round trip on that side either), and
`TYPES_WITH_TABLE` is read off the same Parte A/B composition `section_field_keys` reads —
which is what closed the second gap in the same place, `langs` never having been gated by
type at all while `team` and `checks` were. The budget is deliberately not among them: its
row is not keyed by column, the category *is* the key, and it arrives as `category_key` on
a typed line.

---

## 10. Open questions

Nothing in this document is guessed. Everything that is not decided is here, with the gate
that owns it and what it blocks.

| Question | Gate | Blocks |
|---|---|---|
| **Whether *Ready Vessels* stays among the ten `supportedGoal` options.** Its fund half is answered — it ceased to be a fund (D3) — but the question had two sides and one sentence came back | **GATE-01** (OBT-447) | **BE-02 and BE-05, no longer BE-07**: it stopped being a question about money and became one about a vocabulary. The list stays at ten with `Ready Vessels` among them, and the vendored emission carries it — removing it early would cost the list *plus* a migration of every answer already stored |

**Answered by GATE-02 and GATE-03 on 27/aug/2026** (OBT-448, OBT-449), and no longer open.
Recorded rather than deleted, because each one landed somewhere in this module — and because
in four of the seven the answer arrived with **more** than the question offered:

- **How teams get access** — **accounts, and everyone gets one**: `apps.auto_approve = true`,
  *"quem tiver uma conta"* (D1). Variants 2 and 3 fall, and with them the nullable author
  column: `rr_requests.created_by` and `rr_fund_movements.created_by` are **`NOT NULL` FKs**.
  **BE-02** carries that, and **BE-17** (OBT-477) carries the half the client separated
  himself — how mesa, Gestor and Líder de Base *get* their accounts, which blocks nothing.
- **What the Gestor does, and who may edit the team's text** — *"o Gestor pode alterar … só
  não aprova"* (D3) and *"a mesa pode alterar também"* (D4). One cell moved: `move_board`
  gained the Gestor. `edit_evaluation` stays denied to him — the restrictive default was
  **confirmed, not overruled**, and since 28/aug/2026 the confirmation is a sentence with a
  date on it: *"ele nem pontua nem decide, essa função é exclusiva da mesa"* — and
  `edit_requests` stays true for all three, which means
  the capability guard on `/a` and `/b` that §5.4 reserved is work the answer **dispensed**.
- **One evaluation per request** (D5), not one per member. And the answer did not stop at the
  option: the client added *"uma tag ou assinatura de qual dos membros da mesa estava
  representando a mesa"* and *"registro de quem eram as pessoas da mesa presentes"*. The first
  is the `evaluator`, signing **on behalf of** the mesa. **The second is new data of
  cardinality N** — a minutes-of-the-meeting list, not an audit trail, and confusing the two
  would build a table that answers the wrong question. **BE-02 gives it a shape; BE-06 fills
  it.**
- **Recording a decision moves the card** (D6), automatically. §2.3's decision↔column mapping
  stops being a correspondence table and becomes an execution path, and **when the decision is
  `approved` the same write appends to the ledger** — so BE-06 and BE-08 stop being
  independent and the write order starts to matter. The implication runs **one way only**: a
  decision implies a column, a column never implies a decision. The mesa may still drag a card
  it never evaluated, and a dragged card notifies nobody.
- **Audit trail for edits: yes, always** (D7), over both the solicitação and the avaliação,
  field by field. The third of the trail that had no owner has one: **BE-15** (OBT-475) — and
  **the two tables it writes into are already here**, because this document's own line said
  they are cheap before there is data and expensive after. §4.4 is where they are. Two things
  travel with them. Their subject exists only because of D1 — a document with an owner is what
  a trail is written about. And the generic `updated_by`/`updated_at` shape the answer asks
  for **must not be retro-applied to `rr_funds`**, which has no allocated column and must not
  gain one: the ledger of §7 is already the money's trail, append-only by design.
- **The request travels online** (GATE-03 D1), the attachment becomes a **file** in a private
  bucket (D3 — **BE-14**, OBT-474), and the team sees **its status and nothing else** (D4).
  §6 carries all three.
- **The team is told** (GATE-03 D5/D6), by e-mail *and* in-app, on the four decisions, fired
  on the saving of Parte C. The row above said **unowned**; it now reads **BE-12** (OBT-473)
  for the e-mail infrastructure and **BE-13** (OBT-480) for the notification, in that order —
  the ordering is the requirement, not a preference (§6).

**Answered by GATE-02 on 27/aug/2026** (OBT-448), and no longer open. Five rows left the
table above; each landed somewhere:

- **How teams get access** — accounts, and `apps.auto_approve` grants `equipe` on
  registration (D1). Variant 1, already built; `created_by` is a non-nullable FK. Written by
  `20260828_rr02` (BE-03). **How mesa, Gestor and Líder accounts are granted as a *process*
  is a separate issue the client asked for** — **BE-17** (OBT-477) — and until it exists
  `scripts/grant_app_role.py` seeds them by hand, which is how the first accounts were always
  going to be born. It never blocked BE-03.
- **The three capability cells** (D3, D4) — the Gestor does **not** author evaluations, he
  **does** move the board, and the mesa **may** edit a team's request. Two array elements in
  §5.4's map, exactly as designed, plus a fourth role the answer created: the **Líder de
  Base** (D2), narrowest of the four — he endorses and does nothing else. `endorse_request`,
  his read-without-edit view of Parte A/B, and the undecided `?` cell of the mesa are
  **BE-16** (OBT-476), and none of it is in this module's map yet.
- **One evaluation per mesa** (D5), signed by whoever represented it, plus a field no option
  offered: **who was present** when it was decided. That is minutes, not audit, and it is
  **BE-06**'s. `uq_rr_evaluations_snapshot_evaluator` holds under the answer, so §4.1's bet
  paid and no migration was needed.
- **Recording a decision moves the card** (D6), automatically on write, and in `approved` it
  writes to the ledger. **BE-06 and BE-08 stop being independent**, and it is the trigger
  BE-13 (OBT-480) fires on.
- **The audit trail** (D7) — yes, over the solicitação **and** the avaliação, on top of the
  ownership D1 made possible. **BE-15** (OBT-475). ⚠️ It is **not** retro-applied to
  `rr_funds`: there is no `allocated` column there and there must not be, or the *store two,
  derive the third* of contract §3.2 breaks and two audit designs stand over the same money.

**Answered by GATE-01 on 26/aug/2026** (OBT-447), and no longer open — it closed the money
half of the table above and left the vocabulary half. Recorded rather than deleted, because
each one landed somewhere in this module:

- **Which fund a request asks from** — **the mesa assigns it at triage** (D4), of the three
  shapes the gate offered. No field enters the form and none joins the request document — the
  45 keys stay 45 — so `rr_requests.fund_id` stays nullable by design, and null is the
  legitimate state of a request still in `triagem`, which is what the seed's three fundless
  cards exercise: two states not to conflate. The invariant that arrived with the answer —
  **a request does not enter `aprovado` with `fund_id IS NULL`** — is a service rule and
  deliberately not a CHECK, since the same null is correct one column earlier. **BE-11**
  (OBT-470) owns the write, and has built it: the rule is
  `app/services/resource_request/_fund_assignment.py`, read by both approval doors through
  `guard_stage_entry`, and the column it demands is written by `PUT /requests/{id}/fund`,
  recorded as a `rr_request_field_history` row keyed `fund_id` and moving both balances in one
  transaction when the request being reassigned is already approved. The re-ask its DoD
  carried — the client's aside that the *Gestor* would define which fund goes to which
  project — **came back on 28/aug/2026 as *"somente a mesa"***, so the route is gated on
  `assign_fund` and the Gestor does not hold it.
- **What each fund covers, and the old↔new mapping** — only *Shema Línguas* remains a fund
  (D1), and the other four names are **undecided rather than retired**: not approved either.
  The mapping closed by elimination instead of by mapping — *"leave it as it is"* (D2) — so no
  old category was paired with a new name. The seed writes the one row with
  `provisional = false`. What the answer opened — an editable area for funds, and the
  retired-fund flag item 7 below describes — is **BE-10** (OBT-471), which is also why §8.2
  keeps the fund list a **table and never an enum**.
- **Insufficient funds on a concurrent approve** — allowed with a warning, never refused
  (D5, §7.3). The lock stays; only the refusal is gone, and it is one branch: the warning one.
- **The Gestores enter the allocated value** (D6) — and `rr_funds` is where that answer could
  have been lost. **Funds are born at zero**: the table gains no `allocated`, no `updated_by`
  and no `updated_at`, because the literal reading of *an editable alocado carrying who and
  when* is three columns, and three columns would break *store two, derive the third* and
  stand a second audit design against GATE-02's. It is already built instead as an
  `ALLOCATION` movement in the append-only ledger, whose `created_by`/`created_at`/`reason`
  **are** the authorship, and a wrong one is corrected by a compensating movement. The
  allocation write path is **BE-09** (OBT-469).

And seven items with **no gate**, which need issues rather than answers:

1. ~~**The vocabulary JSON emission and the two unminted key lists** (§9, §4.3) — must land
   before INT-02.~~ **Closed by BE-05** (OBT-454, 25/aug/2026): both lists are minted, the
   emission exists and is vendored, and the seed's copy of the eighteen is gone.
2. **The frontend's CI does not run its test suite** (§9), so the checksum test that guards
   its constants never runs on a pull request there. Its own repository's issue, and the
   reason this side's assertion is the one load-bearing check.
3. **Stable vocabulary keys in the frontend.** The contract specifies them; implementing
   them plus migrating stored drafts is unowned, and until it happens a draft stores
   Portuguese prose where BE-02 expects an enum.
4. **`alembic/env.py` sees no tables** (§8.1) — repository-wide, affects seven other
   applications, not this module's to fix unilaterally.
5. **A PostgreSQL path for the test suite** (§7.3) — **half-closed by BE-07** (OBT-456):
   the concurrency test exists behind `RR_POSTGRES_TEST_URL` with a declared skip, and the
   `test.yml` service block that would run it on every pull request is written but waits on
   a push with the `workflow` scope — it rides in BE-07's PR description.
6. **The board card projects two chips the form does not collect** (BE-02, 25/aug/2026,
   found writing the seed). The contract's §6.2 records this about the card's *fund*; the
   same is true of its **povo** and its **língua** for two of the three request types. A2 is
   rendered by `traducao` alone, so `people_name` does not exist for `treinamento` or
   `equipamentos` and all five of the seed's non-`traducao` cards drop it; those two types
   reach a language only through A1-slim's table of language names — which the fixture's `—`
   and `Multi` are not — so four of those five drop that too. Writing either would say a
   section was asked when it never was. It belongs with the contract's §6.1 question about
   whether that chip survives beside the *solicitante*, and it needs the same owner:
   **before INT-04**, which builds the card against a real endpoint.
7. **`rr_funds` carries no active/retired flag, and a fund can never be deleted** (BE-02,
   26/aug/2026, from GATE-01's answer). `rr_fund_movements` references it and the ledger is
   append-only, so a fund that stops being one has to stay readable for the movements that
   already name it — a DELETE is not available and never will be. Ready Vessels is the proof
   that a fund can end: it ceased to be one before it ever took money *here*, so no row
   survives and nothing was needed. The day one ends **after** it has taken money, the answer
   is a flag. **BE-10** (OBT-471) owns the editable fund area, which is where the column and
   its reader belong together — a flag added without a reader would be the same unhonoured
   column `provisional` already is.

Two things this document changes elsewhere, and neither should be silent:

- **FE-22's contract §5.1** gains the money decision of §7.2 — `Numeric(14, 2)` and
  ISO-4217 on the server, implemented by BE-02 in `20260825_rr01`. The contract asked to be
  updated with that answer.
- **The frontend's `CLAUDE.md` §3.2** tells a reader that the ecosystem's BE-01 audited this
  repository and that its output should be read. It did not, and there is none (§1.1).

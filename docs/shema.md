# `shema` — module design

**Status:** written by BE-01 ([OBT-390](https://linear.app/shema-obt/issue/OBT-390)) on
11/sep/2026, against `origin/dev` at `39c840a3`.
**Audience:** whoever implements BE-02…BE-16 and INT-01…INT-12. It is written so you do
**not** have to read the frontend.
**Inputs:** [`AGENTS.md`](../AGENTS.md), [`CONTEXT.md`](../CONTEXT.md),
[`docs/resource_requests.md`](resource_requests.md) — the sibling module that already
settled the house shapes — FE-44's frozen contract
(`shemaobt/project-management-ecosystem`, `docs/data-contracts.md`, OBT-386), and the
ecosystem's `CLAUDE.md` §3.2/§5/§6/§8.

---

## 0. How to read this

Every statement below carries one of four markers. They are
[`docs/resource_requests.md`](resource_requests.md) §0's markers, and FE-44's, deliberately,
so the three documents read the same way.

| Marker | Meaning |
|---|---|
| **Decided** | Settled here. A later issue that departs says so in its PR and edits this section. |
| **Provisional** | Written for convenience, not because anyone decided it. Named so the wave does not inherit it by accident. |
| **Open · GATE-0n** | Not decided by the client. The gate issue is where the answer comes from — do not guess, and do not freeze a schema around a guess. §9. |
| **Open · BE-nn** | An engineering question this document deliberately hands to a named later issue, because that issue has the evidence and this one does not. §10. |

Three tie-breakers, because this document is the junior of three:

- Where this document and [`AGENTS.md`](../AGENTS.md) / [`CONTEXT.md`](../CONTEXT.md) /
  `docs/` disagree about **how this repository is written**, the repository wins and this
  document has rotted. Say so rather than working around it.
- Where this document and FE-44's contract disagree about **what the product's data is**,
  the contract wins. It was frozen against a built, client-reviewed product; this one was
  not. The one exception is §1.3 below, which is this document correcting the contract's
  reading of *this* repository — the contract's own second tie-breaker asks for exactly
  that.
- Where this document and [`docs/resource_requests.md`](resource_requests.md) disagree
  about **a house shape for a module** — the layout, the plural rule, the `app/models` ÷
  `app/db/models` split — that document wins, and a divergence here is named as one with
  its reason (§2.2, §3).

This is a **delta**, not an audit. It does not restate the house rules; it records the
places where building this module needs a decision the house rules do not already make.

---

## 1. What this is a delta against

### 1.1 The module does not exist — verified, twice over

`git ls-tree -r origin/dev` finds no `app/api/shema/`, no `app/services/shema/`, no
`app/models/shema.py` and no `app/db/models/shema.py`. Grepping the whole application
package for `shema` case-insensitively returns **three** files, none of them a module: two
docstrings in the `resource_requests` module naming the `shemaobt` GitHub org, and
`app/core/config.py`'s CORS list and `noreply@shemaywam.com`.

OBT-390's own description says *"See PR #127, which scaffolded it."* **PR #127 is open, was
never merged, and its base is `main`** — which this stack does not build on. What it carries
is read in §1.4 and mostly not taken.

### 1.2 What this is a delta against instead

Three things, all of which exist:

| Input | What it settles |
|---|---|
| [`docs/resource_requests.md`](resource_requests.md), 1,563 lines | Layout, the plural rule per directory, aggregate ownership, the `app/models` ÷ `app/db/models` split, and the traps of §8 — **for this repository**, against a module that shipped 11 routers, ~57 one-operation services and 8 migrations. |
| FE-44's `docs/data-contracts.md`, 1,389 lines | What the product's data is: 55 + 18 fields, nine derivations pinned over 127 records, the privacy rules as server requirements, and one endpoint section per screen. |
| The code on `origin/dev` | Every verdict in §4 was read, not inferred. Paths and counts below are measured. |

The ecosystem's `CLAUDE.md` §3.2 was corrected on 11/sep/2026 and now says the module does
not exist. This document is the artifact it and FE-44 §12.1 both point at.

### 1.3 Three corrections this document owes its inputs

FE-44 §3 verified `shema-api` at `origin/main` `f3f02c85`. This stack builds on `origin/dev`,
which carries a whole sibling module `main` does not, and one of the three verdicts changes
because of what `dev` holds.

**C1 — Signed URLs exist in this repository. The contract and `CLAUDE.md` are both pointing
at the one module that has none.**

FE-44 §3.1 says *"Media upload + signed URLs" has no signed URL*, and it is right about
`app/services/storage/upload.py`. It is wrong about the repository. Three places mint a v4
signed URL today:

| Where | What it does |
|---|---|
| `app/services/oral_collector/gcs_utils.py` | `generate_signed_download_url(bucket, blob, expiry_minutes, response_content_type)` and `upload_gcs_object` — the reusable pair, taking the bucket as a parameter. |
| `app/services/annotation_studio/storage.py` | `presign_put` / `presign_get`, v4, cached ADC credentials refreshed on demand. |
| `app/services/resource_request/_attachment_storage.py` + `attachment_download_url.py` | A dedicated **private** bucket, content-addressed keys, a 15-minute signed GET minted per call and stored nowhere. Its docstring refuses `app/services/storage/upload.py` **by name**. |

This changes BE-04's work from *invent signed URLs* to *copy the sibling's three-line
adapter against a Shemá bucket*. §4.6 is the verdict.

**C2 — `app/services/notifications/` has a fourth app helper the package does not export.**
`get_oc_app_id.py` exists on disk and is absent from `app/services/notifications/__init__.py`'s
imports and `__all__`, while `get_mm_app_id` and `get_rr_app_id` are both exported. BE-15 adds
`get_shema_app_id` beside them and should export it; fixing `get_oc_app_id`'s omission is
somebody else's one-line PR, named here because BE-15 will be the next person to read that
file.

**C3 — FE-44 §9.6 gives the intercessor network to BE-09; the Linear issue titles give it to
BE-13** (*"BE-13 · Equipe e intercessores"*, OBT-402), and BE-09 is *"Oração: pedidos,
autorização e geração do Pulso"* (OBT-398). **The owner is not chosen here.** The routes are
`/api/shema/prayer/intercessors` in both readings (FE-44 §9.6), so §3.1 puts them in
`prayer.py` and §5.7 keeps the aggregate whole whoever writes it; what is contested is only
**which issue writes them**, and §11 puts that boundary on both descriptions rather than
picking for the two.

> **Settled by BE-13: the network is BE-13's.** The evidence is in the graph rather than in
> either document — **INT-10, *Integrar Equipe e Intercessores*, is blocked by OBT-402 and not
> by OBT-398**, so the screen that consumes the network waits on BE-13 — and every line of
> OBT-402's Context section is about that table: contact details, consent, removal, sensitive
> countries. BE-09 keeps the wall, the authorization of requests and the Pulse, which is what
> its own title says. **The frozen paths did not move**: the routes are still
> `/api/shema/prayer/intercessors`, where the console's `prayerAPI` namespace points, in
> `app/api/shema/intercessors.py`; `prayer.py` stays BE-09's. §10 item 5 is closed.

### 1.4 What PR #127 carries, and what is taken from it — **Decided**

PR #127 (`feat(OBT-266): scaffold the Shemá module inside tripod-api`, branch
`levigft/obt-266-shm-011-scaffold-fastapi-alembic`) is open against `main`. The ecosystem's
`CLAUDE.md` §3.2 says OBT-266 belongs to the retired SHM epic and should be closed rather
than resumed. **This anchor is a re-derivation on `dev`, not a cherry-pick.**

| What #127 carries | Taken? | Why |
|---|---|---|
| `/api/shema` prefix; `app/api/shema/`, `app/services/shema/`, `app/models/shema.py` | **Yes** | They agree with OBT-390's own text, with FE-44 §9, and with `CLAUDE.md` §3.2. Three documents naming the same paths is the decision already made; §2.1 only confirms it. |
| The `for _sub in (...): router.routes.append(route)` aggregation loop | **No** | The sibling that shipped uses `router.include_router(...)`, one line per sub-router — which is also what the wave's collision rule asks every later issue to append. §3.2. |
| `GET /api/shema/health` + `get_module_status` + `ShemaHealthResponse` | **No** | A module health probe duplicates `/health`, and it makes the anchor's first act *adding a route* when the whole point of the anchor is that it carries none (§3.2). It is also a route with no consumer in FE-44's twelve screens. |
| `app/core/version.py`, `HealthResponse.version`, the `jwt_secret_key` blank-rejecting validator, `.env.example`, `README.md` | **No** | Repository-wide changes that improve the repository and have nothing to do with this module. They deserve their own issue against `dev`; smuggling them in under a module anchor is how a design PR becomes unreviewable. |

`app/models/shema.py` is therefore free: nothing of #127 claims it here.

### 1.5 What is inherited unchanged, and is not repeated here

[`AGENTS.md`](../AGENTS.md) and `docs/` in force, verbatim: `app/api/` is HTTP access only
with **zero database access**; every query lives in `app/services/`; services never import
`fastapi.HTTPException` and raise from `app/core/exceptions.py`; `AsyncSession` comes from
`get_db` and I/O is async end to end; every schema change ships as an Alembic migration;
public functions carry full annotations and concise docstrings, never `#` comments; line
length 100; documentation in English, identifiers untouched.

[`docs/resource_requests.md`](resource_requests.md) §8's traps hold here too and are not
re-derived — most sharply §8.1 (autogenerate sees zero tables, so migrations are written by
hand and the new model file must still be re-exported from `app/db/models/__init__.py`) and
§8.3 (the parent revision is **read** off the base at write time, never remembered). §7
below adds only what is new for this module.

---

## 2. Module naming and boundaries

### 2.1 The name and the prefix — **Decided**

The module is **`shema`** and its routes live under **`/api/shema`**. The design document is
this file, `docs/shema.md`.

Not a new decision so much as a confirmed one: OBT-390's description names `/api/shema` and
`app/services/shema/`, the ecosystem's `CLAUDE.md` §3.2 names both, FE-44 §9 writes every
one of its twelve endpoint sections under that prefix, and PR #127 built it there. Fixing it
here is what lets BE-02…BE-16 stop asking.

**The plural rule of [`docs/resource_requests.md`](resource_requests.md) §3 does not apply,
and this is why.** That rule reads off the pairs where both sides exist:
`app/api/access_requests.py` ÷ `app/services/access_request/`, `projects/` ÷ `project/`,
`meaning_maps/` ÷ `meaning_map/`, `languages.py` ÷ `language/`. **Every one of those is an
entity name**, and the plural on the API side is the collection the routes address. A
**product** name has no plural and this repository never invents one: `annotation_studio`,
`sound_necklace`, `oral_collector`, `internalization_room`, `project_health`, `book_context`
and `platform` are spelled identically under `app/api/` and `app/services/`. Shemá is a
product. So both sides are `shema`, the two model files are `shema*.py` on both sides, and
the module is consistent with six siblings rather than in breach of a rule about entities.

### 2.2 The model files are prefixed and flat — **Decided**, and the one divergence from the sibling

`resource_request` keeps nine tables in one `app/db/models/resource_request.py` and one
`app/models/resource_request.py`. That worked for a module whose schema landed in a single
issue (BE-02, `20260825_rr01`). **This module's schema does not.** Eleven aggregates (§5)
are authored by BE-02 and then grown by twelve issues that run in waves beside each other; a
single file on either side is a merge conflict in every one of them.

The repository already has the shape for a product this size, and it is the Oral Collector's
and the Annotation Studio's: **flat, prefixed, one file per aggregate** —
`app/models/oc_project.py`, `oc_recording.py`, `oc_storyteller.py`, `oc_genre.py`,
`oc_acousteme.py`, `oc_stats.py`; `app/db/models/as_speaker.py`, `as_tier_a.py`,
`as_tier_b.py`, `as_tier_c.py`, `as_export.py`, `as_analysis_result.py`,
`as_language_member.py`.

So: **`app/models/shema.py` for the project record, and `app/models/shema_<aggregate>.py`
for the rest, mirrored name for name under `app/db/models/`.** The mirroring rule of
[`docs/resource_requests.md`](resource_requests.md) §3 still holds — the two sides carry the
same file names — and the wave's collision rule falls out of it: *create your own file, do
not grow BE-02's.*

⚠️ `app/models/` is Pydantic and `app/db/models/` is SQLAlchemy. There is no `app/schemas/`.
The naming trips every newcomer once.

### 2.3 The app key and its roles — **Decided**

| | |
|---|---|
| `app_key` | **`shema`** |
| Role keys | **`coordinator`, `obtLab`, `resourceCircle`**, and **`admin`** since OBT-523 (§6.8). ~~`globalStrategist`~~ was the fourth and left on 7/oct/2026 (OBT-572): Karina had meant to retire it; Daniel decided its holders lose it and the Admin grants another role — `20261007_shema572` revokes the grants and the pending invites, the row stays unseeded |
| Seeded by | `scripts/seed_apps_roles.py`'s `SEED_APPS` and `APP_ROLES_OVERRIDE` — BE-03; `admin` by its `PLATFORM_ADMIN_APPS` and by `20260927_shema08` — OBT-523 |
| Named in code | `app/api/shema/_deps.py` and nowhere else in the module |

The role keys are the frontend's own ids verbatim, which is the precedent
`resource-request-form` set with `equipe` / `mesa` / `gestor` / `lider` and the reason
`seed_apps_roles.py`'s docstring already gives: *"the four keys are the role ids of the
frontend's `capabilities.ts` verbatim, not a translation of them."* Here the ids are
camelCase (`SessionRole` in `src/types/role.ts`) while most of this repository's role keys
are snake_case. **Keep the camelCase.** `GET /api/shema/session` (§6.3) must answer a
`SessionRole` the frontend can use as a key; a translation table between two spellings of
one vocabulary is a second place to be wrong, and it would be read on every request.

`admin` is lower-case and not camelCase because it is not one of the four personas: it is
OBT-522's Admin, one role seeded in this app and in `resource-request-form` under the label
*"Admin da plataforma"*, and not `users.is_platform_admin` (§6.8).

`role_key` is `String(100)` free text scoped per app (`uq_roles_app_role_key`), so nothing
in the platform objects.

~~**`app_url` is Open · BE-03.**~~ ~~**Answered: `https://shema.shemaywam.com`, in `SEED_APPS`
and in `cors_origins`, both by BE-03.**~~ **Corrected by OBT-567 (6/oct/2026): `app_url` is
`https://project-management-ecosystem-f7ssqjozfq-uc.a.run.app`**, the Cloud Run address the
PME answers on. `seed_apps_roles.py`'s docstring records that the column is not decoration —
`request_password_reset` builds `{app_url}/reset-password?token=…` from it, `send_invite` builds
`/convite?token=…`, the intercessor's exit builds `/leave/<token>` and the intake link reads the
same row, so a wrong value breaks every letter the PME sends, silently. BE-03 had nothing to read off a deployment and followed the
eight conventional rows in `SEED_APPS`; the hostname never got a DNS record, and the
reset e-mail led nowhere. The user decided on 6/oct/2026 that `shema.shemaywam.com` is not a
planned domain, so the seed carries the deployed address and `20261006_shema567` is the
one-row UPDATE BE-03's docstring had anticipated, guarded by the old value so a row someone
already corrected by hand is left alone. `cors_origins` still lists the old hostname: it is
the platform core's, and the deployed PME never needed an entry — its nginx proxies `/api` to
`$BACKEND_URL`, so the browser calls the API on the PME's own origin and CORS is not consulted.
Invites, leave links and intake links are whole again — `convite` and `leave/:token` are routes
the PME has. **What this does not restore is password recovery itself**: the PME (`origin/main`
on 6/oct/2026) has no `/reset-password` route and no *forgot password* screen, so that link now
points at a host that exists and a page that does not — the token lands on the catch-all
behind the session gate. That screen is the PME's (`project-management-ecosystem`); no issue
owns it yet, and whether it comes before anything else is the user's call. This issue fixes
the half the server owns.
§10 item 3 has the history.

### 2.4 What it shares — **Decided**

The whole authentication spine, and only through `app/core/access_control.py` and
`app/services/authorization/`: `users`, `apps`, `roles`, `user_app_roles`, `access_requests`,
`access_invites`, `refresh_tokens`, `password_reset_tokens`.

**This module's services never query the grant tables directly** — `user_app_roles`, `roles`,
`apps` and the two access tables. The guards are the interface; a service that reaches for
`user_app_roles` has reimplemented `require_role` badly. When the
module needs the join from the other end — *who holds this role* — it asks
`authorization_service.list_role_holders`, which the sibling added for exactly that and whose
docstring states the rule. OBT-543's history asks the same way (`list_grant_history`).
Reading `users` for an account's existence or name is not that:
`save_region_team` checks a seat's account there and OBT-524's roster names its members from it,
and neither reads a grant.

> **Two readings of this rule since OBT-543, both named rather than absorbed.**
> `access_invites` is reached through the invite module that owns it —
> `app/services/resource_request_access/invite_store.py`, gate-free — OBT-549 retired the form's
> access doors and left this store in place (30/sep, option A); moving it into this module is a
> follow-up — and not through `authorization/`. And `users` is read by id where a name or a
> lock is the point: the Admin's history resolves names in one query, and a grant locks the
> account it writes to, as `save_region_team` already reads one by id.

Two things this module owns about identity: the region dimension of §6.1, which the platform
has no column for, and — since OBT-524 — **project membership** (§6.9), the link from an account
to the Shemá projects whose team it is on.

### 2.5 What it deliberately does not share

Verdicts and evidence are §4. In one line each: `projects` and `languages` are **not shared,
no FK** (§4.3, §4.4); `organizations` is **not applicable** (§4.5); `phases`,
`project_health`, `permissions`/`role_permissions` and `app/services/i18n/` are **not
applicable** (§4.7, §4.8, §4.10, §4.11).

### 2.6 There is no third module to draw a boundary against

[`docs/resource_requests.md`](resource_requests.md) §2.4 asked what it shares with the Shemá
module and answered *nothing, because there is no Shemá module*. The answer is unchanged from
this side: the two share the auth spine of §2.4 and **nothing else** — different products,
different aggregates, different app keys. The first person to reach for the other's tables
should be asked why.

> **OBT-543 is where the two meet, deliberately.** The PME's Admin grants the form's roles
> too (OBT-522), so this module composes the form's invite store and its mesa × Gestor rule
> (`_rules.assert_role_compatible`), and the form's acceptance applies the regions a Shemá
> invite carries (`apply_invited_scope`). Both directions import by **submodule path**, the only
> spelling that binds a function whichever package loads first —
> `tests/test_app_boots.py::test_the_grant_packages_import_in_either_order` walks both orders.
> OBT-549 moves the form's half into this module rather than deleting it (§6.10).

Two shared-by-accident surfaces are worth naming because they are one import away:
`app/services/notifications/` (§4.6 — call it as it is, do not change its signature) and
`app/services/oral_collector/gcs_utils.py` (§4.6 — the sibling already reuses it with its own
bucket, which is the precedent, not a trespass).

---

## 3. Module layout

### 3.1 The table

| Path | Owner | Holds |
|---|---|---|
| `app/api/shema/__init__.py` | **BE-01** | The module router, mounted once in `app/main.py` under `/api/shema`. Aggregates the sub-routers, one `include_router` line each. Since OBT-555 the outer `router` carries `NO_STORE`, so every route the module mounts answers `Cache-Control: private, no-store` (§3.3's *Caching* row). |
| `app/api/shema/_deps.py` | BE-03 **· built**; OBT-523 | `APP_KEY`, `Db`, `CurrentUser`, the four role aliases and `AdminUser`, §6.1's region-scope dependency, and the PME's door (`DOOR`, `SessionRoles`, §6.8), and — OBT-528 — the caller's reader (`Reading`, §6.4), and — OBT-555 — the cache rule (`PER_READER_CACHE_CONTROL` and the `NO_STORE` dependency that writes it). The app key is named here and nowhere else in the module. |
| `app/api/shema/_routing.py` | **OBT-556, built** | `ShemaRoute` and `ShemaRouter`: every route included into the module's three routers answers a 422 without the `input` it refused, and lets an unexpected Pydantic error reach the log by its location and never by its value (§6.4). |
| `app/api/shema/projects.py` | **BE-05, built**; BE-06 | The collection read, the record read, `POST`, `PATCH`. |
| `app/api/shema/health_assessments.py` | **BE-07, built** | `POST`/`GET /projects/{id}/health-assessments`, plus `GET /health-questions` — the question sets as provenance (§5.3's note). |
| `app/utils/shema_health_questions.py` | **BE-07, built** | Every published set of guiding questions, append-only. The dimensions and the i18next key of each question, never the rendered sentence. |
| `app/services/shema/_health_audience.py` | **BE-07, built** | Who may read a reading of a team, and who is told when one turns critical — one list, two uses. |
| `app/services/shema/_health_notice.py` | **BE-07, built** | What a notice about a struggling team may say, which is the part of that feature that needed deciding. |
| `app/api/shema/prayer.py` | **BE-09, built** | The wall, `GET /prayer/requests` (any Shemá role, in its scope), and the Prayer Pulse, `GET /prayer/pulse?lang=pt-BR\|en` (`resourceCircle`). The network's routes share the prefix and live in `intercessors.py` (§1.3 C3). |
| `app/models/shema_prayer.py` | **BE-09, built** | `PrayerRequestEntry` — FE-44's `PrayerRequest`, a `LeavingShape` validated off the project row — and `render_prayer_pulse`, **the Pulse's format and the only place it lives** (§9.3). |
| `app/services/shema/list_prayer_requests.py`, `generate_prayer_pulse.py` | **BE-09, built** | The wall, derived on every call; the Pulse, which is the wall rendered and logged without its content. |
| `app/api/shema/meetings.py` | **BE-10, built** | The log: `GET`/`POST /meetings/log`, `DELETE /meetings/log/{meetingId}/{scopeKey}/{period}`. No definitions route — §9.2. |
| `app/utils/shema_meetings.py` | **BE-10, built** | GATE-02's set as the server needs it: the three logged meetings and their cadences. Titles, attendees and readiness stay in the console's `RITMO_MEETINGS`. |
| `app/services/shema/_meeting_log.py` | **BE-10, built** | The log's one rule, for reads and writes: `_health_audience.py`'s audience, inside the caller's region scope; `global` refused with the reason. |
| `app/api/shema/eten.py` | **BE-11, built** | `GET /eten/report?year=`, `GET /eten/credits`, `PUT /eten/credits/{projectId}/{year}` — FE-44 §9.8. |
| `app/models/shema_eten.py` | **BE-11, built** | `EtenYearReport`, the line `EtenYearSnapshot` (a `LeavingShape` whose `country` is FE-44's `LocationDisplay`), the ledger entry, and the evidence each carries. **The one owner of the report's form** (FE-44 §9.8's today) and of what is recorded, `EtenYearReport.recorded()`. |
| `app/services/shema/eten_report.py` | **BE-11, built** | The report: listed projects in scope, their history, the year's manual rows, `account_for` per project, and the report **recorded** in `shema_eten_reports` as it was answered. |
| `app/services/shema/record_eten_credit.py`, `list_eten_credits.py` | **BE-11, built** | The manual ledger: the only writer, with who may set a figure (`ETEN_LEDGER_AUDIENCE`), and its scoped read. |
| `app/api/shema/forms.py` | BE-12 | Submissions, the Pulse artifact, intake links, and the two **unauthenticated** intake routes. |
| `app/api/shema/regions.py` | BE-13 | The org chart and its audit trail. The editor's read of one region (`GET /regions/{key}/team`, the account behind each seat) is scoped like the write since OBT-556. |
| `app/api/shema/intercessors.py` | BE-13 | The network, at FE-44 §9.6's frozen `/prayer/intercessors` paths — §1.3 C3. OBT-531 added `POST …/{id}/review`. |
| `app/api/shema/intercessor_exit.py` | **OBT-531, built** | The module's **second** unauthenticated seam: `GET`/`POST /intercessors/leave/{token}`, the intercessor's exit link. §6.4's OBT-531 note. |
| `app/api/shema/transfer.py` | **BE-14, built** | `GET /export/projects?format=json\|csv&lang=` and `POST /import/projects` — FE-44 §9.12. §6.4's *What BE-14 built*. |
| `app/models/shema_transfer.py` | **BE-14, built** | `ExportedProject`, the export's allowlist — a `LeavingShape` built for nobody — the header's words in `pt-BR` and `en`, the CSV's hygiene, and the import's answer and refusal keys. |
| `app/services/shema/export_projects.py`, `import_projects.py` | **BE-14, built** | The file, through the listing's scope, the boundary and the consent gate, and logged; its inverse, coordination's only, checked whole and applied through `create_project`/`save_project` under one commit. |
| `app/db/models/shema_export.py` | **BE-14, built** | `shema_exports`, append-only: who exported which projects and requests, when, over which scope — ids and counts, never text. |
| `app/api/shema/notifications.py` | BE-15; OBT-541 | The derived panel, preferences, read state. Since OBT-541 the panel and its read mark sit behind the door (§6.8); the preferences stay behind the app gate. |
| `app/services/shema/_request_notices.py` | **OBT-541, built** | The resource-request form's arrival and decision, rung in the PME's bell: who is told (the starter; the Admin off the `shema` grant and the Gestor off the form's), with the registered name and the stage and nothing else, and the `shema_request_notices` detail each row carries. |
| `app/api/shema/session.py` | BE-03 **· built**; OBT-523 | `GET /api/shema/session` — §6.3, behind the door of §6.8. |
| `app/api/shema/access.py` | **OBT-543, built** | The Admin's seven routes under `/access` — §6.10. |
| `app/services/shema/_grant_rules.py` | **OBT-543, built** | The one owner of what the Admin's surface grants and how: the vocabulary (built from `_scope.py`), `admin` in both apps, regions with a regional role and with no other, and the fresh check of the Admin's own standing. |
| `app/services/shema/{find_account,grant_role,revoke_grant,send_invite,withdraw_invite,list_invites,list_grant_changes,apply_invited_scope}.py` | **OBT-543, built** | One operation each. **Flat, against the issue's `access/**`**: every structural scan of this package (`test_layering.py`, `test_privacy_owners.py`, `test_people_privacy.py`, `test_scope.py`, `test_needs.py`) reads `*.py` without recursing, and a sub-package would sit outside all of them. |
| `app/models/shema_grant.py`, `app/db/models/shema_grant.py` | **OBT-543, built** | The surface's wire shapes; and `shema_scope_changes`, the append-only trail of every region scope change. |
| `app/services/shema/` | BE-03…BE-16 | **All** logic and **all** queries. One operation per file with an `__init__.py` re-export — the newer house style (`app/services/access_request/`, `project/`, `auth/`, `resource_request/`), not the grouped `*_service.py` of `annotation_studio/`. |
| `app/services/shema/_scope.py` | BE-03 **· built**; OBT-524; OBT-528 | Which projects a caller reaches, from role **and** region — and, since OBT-524, from a live project membership (`member_projects`, `roster_projects`, `RosterReach`, §6.9) — whose one statement, `live_membership_ids`, is public since BE-19 (OBT-520), because the resource-request form reads the same fact. The `app/services/resource_request/_scope.py` precedent, with §6.1's second axis. It holds the module's region predicate, and every service that reads `shema_projects` composes it — a check in `tests/test_shema/test_scope.py` refuses one that does not. **OBT-528:** `readership` — who reads the truth of a sensitive place, per region — in a function of its own; `visible_projects` untouched. §6.4. **BE-09:** `Readership.withheld_prayer`, whether the caller reads a request nobody authorized — `_consent.py`'s rule, set by `_deps._reading`. |
| `app/models/shema_privacy.py` | **BE-04, built** | `LeavingShape` — the sensitive-country rule itself, applied in a model validator, plus `REGION_CENTROIDS` and the `ShemaAudience` vocabulary. The rule is here rather than in the service package because a response model may not import `app/services/` and the rule has to be reachable from the shape; §6.4 carries the argument. **OBT-528:** the reader (`ShemaReader`, `read_by`), `SessionShape` with `readAs`, and the write vocabularies. |
| `app/services/shema/_redaction.py` | **BE-04, built**; OBT-528 | The sensitive-country owner on the query side: `is_withheld`, `withheld_note`, `log_reference`, `searchable_text` — the last two by reader since OBT-528 — and `unwritable_fields`, the write's question; since BE-14, `never_lowered`, the import's one-way rule on the flag. The only reader of the guarded columns in the two `shema` packages. §6.4. |
| `app/services/shema/_consent.py` | **BE-04, built**; BE-09 | `reaches_prayer_wall` — the **only** reader of the three prayer columns. §6.4. BE-09: `authorized_requests` / `authorized_requests_by_project`, the one assembly of what may leave, which the wall, the Pulse and BE-14's export read; `PRAYER_AUDIENCE`, who reads a request nobody authorized; `request_written` / `need_written`, what an authorization is attached to. OBT-554: `submission_reaches_prayer_wall`, the prayer notice's gate — what a submission authorized, and the record. |
| `app/api/shema/members.py` | **OBT-524, built** | A project's roster and `/me/projects` behind the PME's door; the Admin's add and removal behind the app gate. §6.9. |
| `app/services/shema/_roster.py` | **OBT-524, built** | The live row of an account on a project, and the `ProjectMember` shape one row leaves in. The two writers (`add_project_member`, `remove_project_member`) and the two reads (`list_project_members`, `list_my_projects`) are one file each beside it. |
| `app/db/models/shema_project_member.py`, `app/models/shema_project_member.py` | **OBT-524, built** | `shema_project_members` — one live row per account and project by a partial unique index; removal marks, never deletes — and `ProjectMember` / `ProjectRef` on the wire. |
| `app/services/shema/_directory.py` | BE-13 | A person's contact, their consents and their country — the **only** file in either package that names `ShemaIntercessor`. §6.4's fourth owner. |
| `app/services/shema/_media_sharing.py` | **BE-04, built** | `can_share_media` — authorization, then audience, then the sensitive flag; and `can_export_notes`. §6.4. |
| `app/utils/shema_derivations.py` | **BE-05, built**; BE-10; BE-11 | FE-44 §7's nine pure functions of `(record, now)`, and §7.5's period keys in a block of their own (BE-10). **Not** in the service package — see below. BE-11 added §7.8's ETEN block at the end: the fiscal year, `completion_date_after` and `account_for`. |
| `app/utils/shema_facets.py` | **BE-05, built** | FE-44 §7.6's `filterProjects`: one pass producing the visible list **and** every facet count, plus the screen's five orders. A second file beside the derivations rather than inside them — §6.5 says why. |
| `app/utils/shema_books.py` | **BE-06, built** | FE-44 §5.2's 66 books — the table a `bookProgress` row is checked against. Not `bible_books`, which is the Meaning Map's: minted uuids, seeded rows, one language, an `is_enabled` flag another product owns. §5.2's note. |
| `app/models/shema_record.py` | **BE-06, built**; OBT-528 | The record's **read** shape — FE-44's `Project`, 55 + 21, key for key (`derived`, `readAs` and, since OBT-413, `completedDate` are the contract's own keys now), plus `locationWithheld` — and every sub-shape the ficha is made of. A leaving shape built for its reader since OBT-528. Separate from `app/models/shema.py`, which is what a client *sends*. |
| `app/db/models/shema_audit.py` | **BE-06, built** | `shema_record_edits` — the trail: who moved which field, when, from what to what. Append-only, by the same trigger `shema_progress_history` uses. |
| `app/services/shema/_audit.py` | **BE-06, built** | The trail's writer and its one reader. Names no guarded column and records no guarded **value**. |
| `app/services/shema/_progress.py` | **BE-06, built** | FE-44 §7.2's `applyProgressUpdate`, server-side: the roll-up and the history entry. The module's **single** progress writer; BE-12's import goes through it. |
| `app/services/shema/save_project.py` | **BE-06, built** | The create, the partial update, and the version guard. The one thing in the module that moves `shema_projects.version`. |
| `app/services/shema/read_record.py` | **BE-06, built** | The record read, and `build_record` — the assembly the write path answers with. |
| `app/models/shema.py`, `app/models/shema_*.py` | BE-02 …, per §2.2 | **Pydantic** request/response models. `ConfigDict(from_attributes=True)` on read models; separate `Create` / `Update` / `Response`. |
| `app/db/models/shema.py`, `app/db/models/shema_*.py` | BE-02 authors, each issue grows its own | **SQLAlchemy** tables. Must be re-exported from `app/db/models/__init__.py` — [`docs/resource_requests.md`](resource_requests.md) §8.1. |
| `alembic/versions/20260NNN_shemaNN_*.py` | BE-02 onward | Migrations. Single head, clean `downgrade -1`. §7.1. |
| `tests/test_shema/` | all | Extend; do not replace. `test_mount.py` is BE-01's. |
| `http/shema*.http` | BE-03 onward | Request examples, as the siblings keep them. `http/shema_session.http` is the first. |

**The derivations are in `app/utils/`, not in the service package, and the reason is a rule
this repository enforces with a test.** `tests/test_app_boots.py::test_no_dto_module_reaches_up_into_the_service_layer`
forbids any module in `app/models/` from importing `app/services/` — that inversion is what
closed an import cycle once. FE-44 §7's derivations (status, progress, roll-up, staleness,
overall health, the period keys, region, the presets, the ETEN accounting) are **pure
functions of a record and a clock**: they touch no database, they are needed by Pydantic
response models *and* by services, and the response models are the half that may not reach
into `app/services/`. `app/utils/description_rule.py` is the precedent and the same shape,
and `app/utils/` is flat, so the files carry a `shema_` prefix rather than forming a package
its siblings do not have. This is the sibling's §3 note applied before it costs a rewrite
rather than after.

### 3.2 The anchor, and what it is for — **Decided, and built by this issue**

`app/api/shema/__init__.py` declares an `APIRouter` with **no routes**, and `app/main.py`
mounts it **once**:

```python
app.include_router(shema_router, prefix="/api/shema", tags=["shema"])
```

That single line is the whole of this module's footprint in `app/main.py`, and BE-01 is the
only issue that writes it. Every later router is included in `app/api/shema/__init__.py`, on
a line of its own at the end of the block — never by reordering or deleting somebody else's
line, and never by touching `app/main.py` again.

`include_router`, not the `routes.append` loop of `app/api/annotation_studio/__init__.py`
that PR #127 copied: the sibling that actually shipped
(`app/api/resource_requests/__init__.py`) uses `include_router`, one line per sub-router,
and a sub-router here declares its own full path rather than a second prefix, so nothing is
applied twice.

**Mounting a router with no routes registers nothing** — no path on the application, no
OpenAPI entry — so there is no response to probe. `tests/test_shema/test_mount.py` therefore
proves the wiring the way `tests/test_resource_requests/test_mount.py` does: it hangs its own
route off the module router, rebuilds the app with `create_app()`, asserts
`/api/shema/_mount_probe` is among the application's paths, and removes the route in a
`finally`. That check survives the module having routes of its own, and it is the one that
catches the failure that does not fail loudly — a route mounted under a prefix nobody
registered does not raise, it 404s.

### 3.3 Where each concern lands, against the layering rules

The rule is three lines long and the DoD asks to show the module against it. Reading the
table from the left: nothing in column 2 issues a query, everything in column 3 does, and
nothing in column 3 imports `fastapi`.

| Concern | `app/api/shema/` does | `app/services/shema/` does |
|---|---|---|
| **Authentication** | Nothing of its own. `CurrentUser = Annotated[User, require_app_access(APP_KEY)]` in `_deps.py`, over the platform's JWT middleware. | Nothing. |
| **Role** | The four aliases, `require_role(APP_KEY, key)`. | Nothing. |
| **Region scope** | Declares the dependency; receives a `RegionScope` value. | `_scope.py` computes it from `shema_user_regions` and the granted roles, and **every list query takes it as a parameter**. §6.1. |
| **Validation of the four required fields** | Pydantic models reject a payload before a service is called (FE-44 §5.1.1). | Re-checks nothing Pydantic already refuses; owns the cross-record rules (a new record's id must be a minted UUID — a slug is a `ValidationError` before anything is read, OBT-551 — and a duplicate UUID is a `ConflictError`). |
| **Redaction (sensitive country)** | Nothing but hand down the caller's reader (`Reading`, OBT-528), as it hands down the scope. A router may not decide what leaves. | Nothing either, and that is BE-04's correction to this row: the rule is **inherited** by the response model (`LeavingShape`), not called by a service — which says only **who reads** (`read_by`). `_redaction.py` owns what a `Select` cannot inherit. §6.4. |
| **Consent (prayer)** | Nothing. | `_consent.py` is the only reader of the three prayer columns; the wall's query (BE-09) is the only one that applies the gate. §6.4. |
| **Media authorization** | Nothing. | `_media_sharing.py`, plus the signed-URL adapter of §4.6. |
| **Derivations** | Nothing. | Services call `app/utils/shema_derivations.py`; response models may import it too (§3.1). |
| **Errors** | Maps a business exception onto a status, or lets the global handlers do it. | Raises `NotFoundError` / `ConflictError` / `ValidationError` / `AuthorizationError` from `app/core/exceptions.py`. **Never imports `HTTPException`.** |
| **The intake link (unauthenticated)** | The two `/intake/{token}` routes carry no auth dependency — the first deliberate hole, and it is a router-level fact. The intercessor's exit link (OBT-531) is the second, of the same shape. | `verify_intake_token` is the guard: a service function, so the rule holds for any future caller of it. §6.6. |
| **Caching** | Declared once: the outer `router` in `__init__.py` carries `NO_STORE` (`_deps.py`), so every answer the module builds says `Cache-Control: private, no-store` — every read is built for its reader, and the link routes answer whoever holds the link (OBT-555). A `GET` whose handler returns a `Response` of its own (the export, the Pulse, the exit link's 204) writes `PER_READER_CACHE_CONTROL` itself, because FastAPI does not merge the injected response's headers into it; `tests/test_shema/test_cache_control.py` calls every `GET` and reads the header off the wire. Not reached: the error envelopes of `app/core/exceptions.py`, shared by every app and not a reader's record, and the four answers a write builds itself — the record's 409 (on the `PATCH` and on the import), the import's 400, and the `POST`s of the intake (202) and of the exit link (204), the last two with no `Authorization` — which no cache stores, since none carries explicit freshness. | Nothing. |

---

## 4. The capability audit — every verdict read off `origin/dev`

The DoD's first line. Each row was read in the file named, not inferred from a table. The
three that change FE-44's or `CLAUDE.md`'s reading are marked **⚠ correction**.

### 4.1 Authentication — **Reuse whole**

`app/api/auth.py`, `app/core/auth_middleware.py`, `app/services/auth/` (15 one-operation
files), `app/db/models/auth.py`. JWT access + refresh, `refresh_tokens` and
`password_reset_tokens` with hashed tokens and expiry, `users.is_platform_admin` as the
platform guard, `users.is_active`, `users.locale`.

Shemá adds **no login of its own**. INT-01 targets `POST /api/auth/login`, `/refresh`,
`/logout`, `GET /api/auth/me`. The only Shemá-specific session read is §6.3's
`GET /api/shema/session`, and it exists because of the region, not because of the login.

### 4.2 Roles and app scoping — **Reuse the spine, extend the scope**

`app/core/access_control.py` (`require_app_access`, `require_role`),
`app/services/authorization/` (10 files), `app/db/models/auth.py`, `app/api/roles.py`.

What it does, measured: the grant is `user_app_roles (user_id, app_id, role_id, granted_by,
granted_at, revoked_at, revoked_by)` and `list_roles` answers `(app_key, role_key)` pairs for
one account, excluding revoked grants. `require_app_access` admits any holder of any role in
the app; `require_role` is a membership test on the same cached list. Both return early on
`is_platform_admin`. The cache is per `(user, app_key)` with `AUTH_CACHE_TTL_SECONDS`
(30 s since ENG-551), invalidated by `grant_app_role` and `revoke_role` in-process only.

**The gap, and it is the one FE-44 §3.1 names: the grant has no region.** `require_role`
answers a global yes/no per app; Shemá's authorization is by role **and** by region. §6.1 is
the decision.

Two behaviours to design around, both inherited from the sibling's §5.5 and both true here:

- **A platform admin passes every guard.** Refusing them inside this module would make one
  route stricter than the route beside it and buy nothing, since an admin can grant
  themselves any role with one call. The cost lands on the tests: **a negative test written
  per role must not use an admin account**, or it passes for the wrong reason.
- **A grant written outside this process is not seen until the cache entry ages out.** That
  is the installation's standing trade, not this module's bug. Anything that must see a grant
  immediately reads `list_roles` directly, as
  `app/services/resource_request/holds_capability.py` does and says why.
- **An app's `admin` role manages that app's roles** (`assert_can_manage_roles`, the predicate
  behind `/api/roles/assign`, `/revoke` and `/check`). Since OBT-523 this app seeds one — the
  Admin of §6.8 — and **OBT-543 grants it, in both apps, through `/api/shema/access`** (§6.10),
  which applies the product's rules. So the raw `/api/roles/assign` and `/revoke` **refuse
  `shema` and `resource-request-form` to anyone but an installation admin** (`PME_APP_KEYS` in
  `app/api/roles.py`): every Admin would otherwise pass the predicate there and step around
  the self-grant, the mesa × Gestor exclusion, the mirrored `admin` and the regions in one
  request. `/check` still reads the predicate.

`scripts/grant_app_role.py` matching on `(user_id, app_id)` and **overwriting** `role_id` is a
live platform bug with its own issue (OBT-484), recorded in `holds_capability`'s docstring. It
matters here because a Shemá account will legitimately hold more than one role — a regional
`coordinator` who is also `resourceCircle` — so **BE-03 grants through
`app/services/authorization/grant_app_role.py`, never through that script.**

### 4.3 Projects — **Not shared. No FK. Decided.** (The DoD's second line.)

This is the question `CLAUDE.md` §3.2 and OBT-390 both call the hardest, and *"getting this
wrong is a migration, not a refactor."* FE-44 §4 answered it from the frontend side; this is
the answer from the code, and it agrees.

**What `projects` actually is**, read in `app/db/models/project.py`:

```
projects: id (String(36), uuid4), name (String(200)), description (Text, null),
          language_id (FK languages.id, RESTRICT, NOT NULL, indexed),
          latitude (Float, null), longitude (Float, null),
          location_display_name (String(500), null), created_at, updated_at
```

Nine columns, plus three access tables beside it: `project_user_access` (per user, with a
`role` string and `invited_by`), `project_organization_access` (per organization) and
`project_invites` (by e-mail).

Four measurements decide it:

1. **`language_id` is `NOT NULL` with `ondelete="RESTRICT"`.** Creating a Shemá project
   through this table *requires minting a `languages` row first*. And `languages.code` is
   `String(3)`, **unique**, indexed — while the export carries `jaa-b` (5 chars), `not iso
   language` (16), `N/A`, `?`, `LLL`, `Rop`, three empty strings, and **`pah` on five
   different projects**, which the unique index rejects outright. The one mandatory column of
   the row is the one the data cannot fill. That is not a boundary judgement; it is a
   constraint.
2. **Eleven foreign keys across six model files point at `projects.id`** — measured:
   `project.py` ×3, `sound_necklace.py` ×4, `oc_recording.py`, `oc_storyteller.py`,
   `device.py`, `phase.py`. Every one is `ON DELETE CASCADE` or `SET NULL`. Putting 127 field
   records into that table makes four other products' cascade behaviour a Shemá concern, and
   a Shemá delete a four-product event.
3. **The overlap is four fields of seventy-three.** `name` ↔ `languageName`, `language_id` ↔
   `languageCode`, `latitude`/`longitude` ↔ `coords`, `location_display_name` ↔ `location`.
   The other 69 have nowhere to go, and the four would have to stay in sync between two
   products forever.
4. **The primary keys are different kinds of thing.** `projects.id` is a uuid4 minted by the
   default. The Shemá record's id ~~is **the export's slug** (`afrikaans-kaaps`,
   `purepecha-de-capacuaro`), frozen by FE-44 §5.1 as the address every screen, URL and saved
   view already carries, and BE-16 must not mint new ones~~ **is an opaque UUID since OBT-552
   (1/out/2026, Daniel)** — the slug named the place on every shape that left the server, so
   revision `20261001_shema552` moved all 127 and OBT-551 has every new record born with one.

**Verdict: `shema_projects` is its own table, with no FK to `projects` and no `language_id`.**
`language_name` and `language_code` are text on the row, checked and never refused (FE-44
§5.1). A **nullable** `tripod_project_id` FK is the day-one-cheap answer if the two products
ever need to point at each other — added then, by the issue that needs it. Conflating them
now is the migration the issue warns about.

### 4.4 Languages — **Not shared. No FK.**

`app/db/models/language.py`: `id`, `name (String(200))`, `code (String(3), unique)`,
`created_at`. Eight foreign keys point at it — `projects` plus the Annotation Studio's seven
(`as_speaker`, `as_analysis_result`, `as_tier_a/b/c`, `as_language_member`, `as_export`).
Widening and de-uniquing `code` is a migration against all eight to serve data that is, by
FE-44 §5.1's rule, *checked and never refused*. Text on the Shemá row.

### 4.5 Organizations — **Not applicable** as the scoping dimension

`app/db/models/org.py`: `organizations (id, name, slug unique, description, logo_url,
manager_id → users, created_at, updated_at)` and `organization_members (user_id,
organization_id, role ∈ {member, manager})`, with `app/core/org_scope.py` answering
`get_managed_org_ids(db, user_id)` — the union of orgs the user manages as a member and orgs
whose `manager_id` is them.

It is a real per-user scoping dimension and it is the wrong one. §6.1 is the argument and the
decision. The row is **not applicable**, not *not useful*: if the client ever asks for a
YWAM/JOCUM **base** as a first-class tenant — which FE-44 §5.1 says `team`/`ywamBase` is only
a string today — this is the table that already exists for it, and that is a different
question from the region.

### 4.6 Notifications and media — **Extend**, and one of the two is a correction

**Notifications — Extend the table; do not reuse the router.**
`app/db/models/notification.py` is `notifications (id, user_id, app_id, event_type, actor_id,
title, body, is_read, created_at)` with an index on `(user_id, app_id, is_read, created_at)`,
plus `notification_meaning_map_details`, which is one application's. `create_notification`
takes `commit: bool = True` — the flag the sibling added so a caller owning its transaction
can stage a notice **inside** it.

- **`app/services/notifications/create_notification` is called as it stands.** No signature
  change. The `commit=False` path is what a Shemá writer uses when it owns its transaction,
  and its docstring's rule holds: whoever passes `False` owns the commit and takes it before
  anything leaves the process.
- **`app/api/notifications.py` is not reusable.** Every route on it carries
  `require_app_access("meaning-map-generator")` and reads `get_mm_app_id`. BE-15 writes
  `app/api/shema/notifications.py` and adds `get_shema_app_id` beside `get_mm_app_id` /
  `get_rr_app_id` — and exports it (§1.3 C2).
- **No Shemá detail table** — until something deep-linked. `notification_meaning_map_details` is
  one product's, and a Shemá one would have had no reader. **OBT-541 is that reader**: the
  resource-request form's notices, rung in the PME's bell, lead to the project's record, so each
  of those rows carries `shema_request_notices` — the project, and the registered name and stage
  the console renders in its own language. **OBT-559 added the second**,
  `shema_project_notices`: the four project writers' rows carry what happened — the day, the
  needs and their totals per currency, who signed the Pulse — and never who or where, which the
  panel reads off the project when it is read (§6.4). The bell words both in its reader's
  language; the rows' English `title` and `body` stay for the readers that are not the bell.
- **There is no channel delivery of any kind** — no e-mail, no push, no WhatsApp, anywhere in
  `app/services/notifications/`. FE-44 §5.8's `NotificationPrefs` records the choice of three
  channels; BE-15 inherits a preference with nothing behind it, and that is the honest state
  to ship rather than a half-wired sender.
- **§5.10 decides the panel itself**: the Shemá panel is *derived*, so the platform table is
  the wrong home for it. This row is about the delivered-notice half.

**Media — Reuse `gcs_utils`; refuse `app/services/storage/upload.py`. ⚠ correction (§1.3 C1).**

`app/services/storage/upload.py` is a server-side proxy upload: `ALLOWED_CONTENT_TYPES` is
`{image/jpeg, image/png, image/webp, image/svg+xml}`, `MAX_FILE_SIZE` is 5 MB, it writes to
the open `tripod-image-uploads` bucket and returns
`https://storage.googleapis.com/tripod-image-uploads/<folder>/<uuid>.<ext>` — **a plain,
unsigned object URL**. `app/api/uploads.py` adds a fourth constraint the contract did not
name: `folder` is silently coerced to `"images"` unless it is `app-icons` or `avatars`.

Four reasons it cannot carry Shemá media, in the order they bite: FE-44 §8.3 makes per-item
authorization a server-side rule, and **a rule that ends in a public URL enforces nothing**;
the accept list is images only, while `ProjectMaterial.kind` is `text | audio | video` and
prayer requests carry audio; 5 MB is below one field-recorded audio file; and the folder
allowlist has no Shemá entry.

**But the capability exists in this repository** and BE-04 copies rather than invents:

```
app/services/oral_collector/gcs_utils.py
    generate_signed_download_url(bucket, blob, expiry_minutes, response_content_type)
    upload_gcs_object(...) / download_gcs_object / delete_gcs_object
```

The shape to follow is `app/services/resource_request/_attachment_storage.py`: a dedicated
**private** bucket (uniform bucket-level access, public-access prevention enforced), a
content-addressed key so a replacement never overwrites its predecessor, the client's
filename never in the key, the row storing **a key and not a URL**, and the URL minted per
call as a short-lived signed GET that nothing persists. Its docstring refuses
`app/services/storage/upload.py` by name and says why; BE-04's should too.

**Verdict:** `app/services/storage/` **not applicable**; `gcs_utils` **reuse**; a
`shema-private` bucket and a `_media_storage.py` beside it, **new** — BE-04, with BE-02
owning the `storage_key` column.

**Built (BE-04).** `_media_storage.py` (bucket, expiry, key) and `media_download_url.py` (the
gate and the minted link). The key is scoped by the media row's uuid rather than by the
project slug — §6.4 carries that argument — and the route that calls it belongs to the issue
that first has a screen for media (BE-09, BE-14). **The upload half is not built**: it needs a
content type and size policy per collection (`ProjectMaterial.kind` is `text | audio | video`)
and a screen to be wrong in front of, and nothing here freezes it. `upload_gcs_object` with
`GCS_SHEMA_BUCKET` and `storage_key` is the whole of what that issue has to write.

### 4.7 Phases — **Not applicable**

`app/db/models/phase.py`, `app/services/phase/`, `app/api/phases.py`,
`app/api/projects/phases.py`: workflow phases of a translation project, FK'd to `projects.id`.
Shemá's `ProjectPhase` is a free `{label, scope, date}` typed on the record (FE-44 §5.2),
empty on all 127 records. Different concept, same word.

### 4.8 `project_health` — **Not applicable**, and this one is worth reading before assuming

`CLAUDE.md` §3.2 warns not to conflate it, and the code confirms the warning.
`app/api/project_health/` is five routers (`interviews`, `prompts`, `reports`, `voice`,
`admin`) and `app/services/project_health/` is an AI interview engine with `agents/`,
`prompts/` and `voice/` packages. `app/db/models/project_health.py` starts with
`PHLanguage(en|pt|es|fr|id|sw)` and `PHInterviewStatus(in_progress|completed|abandoned)` as
native Postgres enums over `ph_interviews (project_name, team_name, language, status, …)` —
a conversational instrument that stores project and team as **free text** and is not even
FK'd to `projects`.

Shemá's *Avaliação de Saúde* is a four-dimension rating (`"" | boa | atencao | critica`)
filled in-app by an OBT Lab mentor, with a per-dimension note, an assessor, a date and a
history (FE-44 §5.1, §7.4). **Nothing is shared, nothing is reused, and the two data models
stay apart.** BE-07 builds its own.

### 4.9 Places and geocoding — **Available, unused. Do not wire it in.**

`app/api/places.py` exists. FE-44 §3 is explicit: the record types `location` as free text
and plots from `coords`, and nothing in wave 1 calls a geocoder. **Do not wire one in as a
side effect of BE-06.** Two rules would break if you did: `languageName` and country strings
are *never normalised* (FE-44 §5.1, §5.3 — `COUNTRY_REGION` is keyed on the export's exact
spelling, `São Tomé e Príncipe` in Portuguese and `East Timor` in English), and `[0, 0]` means
*no coordinate* rather than a place in the Gulf of Guinea.

### 4.10 Permissions / role_permissions — **Not usable**

`permissions` and `role_permissions` exist as tables in `app/db/models/auth.py` and are **not
wired into `app/core/access_control.py`** — both guards check roles only. The sibling reached
the same finding (§2.3 of its document) and built a capability map in Python rather than
turning them on. **Shemá does not need one:** FE-44's authorization is `{role, regionScope}`
and nothing in the twelve screens asks a question the four role keys cannot answer. If a
later issue finds one, the sibling's `capabilities.py` + `holds_capability.py` pair is the
shape to copy, not these tables.

### 4.11 `app/services/i18n/` — **Not applicable**

Two files: `translate_content.py` and `back_translate_content.py`, Gemini machine-translation
of authored JSON content. Shemá's PT/EN is an i18next catalogue in the frontend, and FE-44's
Appendix A is explicit: **the backend serves keys and data, never rendered labels.** Every
`labelKey` in the contract's types is an i18next key the frontend resolves.

### 4.12 The summary table — the DoD's first line in one place

| Capability | Where it is on `dev` | Verdict |
|---|---|---|
| JWT login, refresh, logout, current user, platform-admin guard | `app/api/auth.py`, `app/core/auth_middleware.py`, `app/services/auth/` | **Reuse whole** (§4.1) |
| App-scoped roles: grant, revoke, check, cached resolution, role holders | `app/core/access_control.py`, `app/services/authorization/` | **Reuse the spine, extend the scope** (§4.2, §6.1) |
| Organization scope | `app/core/org_scope.py`, `app/db/models/org.py` | **Not applicable** as the scoping dimension (§4.5, §6.1) |
| Projects + access grants + invites | `app/db/models/project.py`, `app/services/project/`, `app/api/projects/` | **Not shared. No FK.** (§4.3) |
| Languages | `app/db/models/language.py` | **Not shared. No FK.** (§4.4) |
| Phases | `app/services/phase/`, `app/api/phases.py` | **Not applicable** (§4.7) |
| Places / geocoding | `app/api/places.py` | **Available, unused — do not wire in** (§4.9) |
| Media upload, public URL | `app/services/storage/upload.py`, `app/api/uploads.py` | **Not applicable** (§4.6) |
| Signed URLs (v4, private buckets) | `app/services/oral_collector/gcs_utils.py`, `annotation_studio/storage.py`, `resource_request/_attachment_storage.py` | **Reuse** — ⚠ correction (§1.3 C1, §4.6) |
| Notifications table + `create_notification` | `app/db/models/notification.py`, `app/services/notifications/` | **Extend** for delivered notices; **not applicable** for the derived panel (§4.6, §5.10) |
| Notifications router | `app/api/notifications.py` | **Not reusable** — gated on another app's key (§4.6) |
| `project_health` interviews | `app/api/project_health/`, `app/services/project_health/` | **Not applicable** (§4.8) |
| Permissions / role_permissions | `app/db/models/auth.py` | **Not usable** — not wired into the guards (§4.10) |
| Content translation (i18n) | `app/services/i18n/` | **Not applicable** (§4.11) |
| Inngest job queue | `app/inngest/`, `app/core/inngest_client.py` | **Available, unclaimed** — nothing in wave 1 needs a background job. Named so BE-12 knows it is there if the Pulse import grows one. |

---

## 5. Aggregate ownership

Eleven aggregates, from FE-44 §5. Table names were **Provisional** — an `shema_` prefix and a
plural, chosen so the rest of this document has something to point at; BE-02 confirms or
renames them in one place. **Every table is created by BE-02**, which §3 gives
`app/db/models/` and the first `alembic/versions/` file; the owner column names two issues
wherever there is a table, because BE-02 authors the schema and the second issue builds the
behaviour on it.

> **BE-02 ([OBT-391](https://linear.app/shema-obt/issue/OBT-391)) confirmed every working
> name below, renamed none, and built sixteen tables in `20260911_shema01`.** Three
> departures from this section, each argued in the model file that carries it:
>
> - **`shema_user_regions` is created here too**, against row 5.13's owner column and on
>   this preamble's own reading — BE-03 runs in the wave above and would otherwise open a
>   migration against this head for one small table. Nothing else of the aggregate moved:
>   the scope service, the session endpoint and the granting path are still BE-03's.
> - **`shema_meeting_definitions` was not built**, as row 5.9 already makes conditional on
>   GATE-02. **`shema_submissions` has no `kind` column**: only the Pulse is archivable, and
>   a column with one value invites a second.
> - **The health rating is three enum members and NULL**, not four with `""`. That is FE-44's
>   own `HealthLevel`, and NULL is the `""` — §7.3's rule survives untouched, because NULL is
>   not `boa` and nothing can default it to one.

| # | Aggregate | Tables (working names) | Owner | The invariant |
|---|---|---|---|---|
| 5.1 | **Project record** | `shema_projects` | BE-02 (schema), BE-06 (lifecycle) | **The concurrency token is a `version` column and a save must quote it** (BE-06 — `If-Match` required, `ETag` on every read; a stale save is a 409 naming the version, the fields and the person). A save that changed nothing moves nothing. ~~The primary key is the **export slug**, not a minted uuid~~ — **every project id is an opaque UUID since OBT-552 (1/out/2026, Daniel)**: revision `20261001_shema552` moved the 127 imported slugs, because the id travels unredacted on every shape and `sa-di-of-high-egypt` handed back the country the redaction had withheld; `shema_project_rekeys` keeps the old slugs for the downgrade and is read by nothing else. Records created since OBT-551 were already born with one, because a create that looked a chosen slug up answered 409 for a slug that exists anywhere, an existence oracle no ordering of the checks could close. The console was already minting `crypto.randomUUID()`. Only four fields are required to save — `language_name`, `bridge_language`, `team`, `objective` — and **nothing else is `NOT NULL`**: 27 of the export's 55 columns are empty on all 127 records. No `translated <= total` constraint: three real records violate it. |
| 5.2 | **Progress and its history** | `shema_progress_history` (+ the aggregates on the record) | BE-02, BE-06 | The history entry is **produced by the server**, never accepted from the client — the previous values are the server's own read before the write. An entry is appended **only if an aggregate changed**, and it snapshots the three unit tables. Roll up **only** the tables that can express counts. Stamp the actor's **local** day — which the server cannot know, so BE-06 has the client state it in `X-Shema-Local-Date` and bounds it to ±1 day of the server's own, the window every real offset fits in and a backdated ETEN credit does not. **A row is checked against the book that exists** (`app/utils/shema_books.py`): not a book, a scope longer than the book, a count above its own row. The ceiling is **per row and never over the aggregates** — three export records carry `156/25`. |
| 5.3 | **Health assessment** | `shema_health_assessments` | BE-02, BE-07 | **Its own aggregate.** The flat fields on the record are a *projection of the newest entry*, never a second truth; append and re-project in one step, and carry a pre-history record into the history before appending. The **per-dimension note is the data**; the running note is derived from it at write time. `""` is not `boa`. |
| 5.4 | **Needs** | `shema_needs` | BE-02, BE-08 | They **travel with the project** — edited on record tabs, saved by the record's `PATCH`. No separate needs endpoint in wave 1; adding one gives `needsItems` a second owner. Four states, not three: `dropped` leaves the open list without deleting the history a region is judged by. |
| 5.5 | **Media and materials** | `shema_media_items`, `shema_materials` | BE-02, BE-04 (the rule), BE-06 (the write) | **The default is not authorized** — only an explicit `granted = true` counts, so an undecided item behaves as a refused one. Every decision carries who and when, as a **snapshot that must not follow a rename**. **Replacing the artifact resets the decision to undecided.** The row stores a storage **key**, never a URL (§4.6). |
| 5.6 | **Prayer** | *(none for the wall)* | BE-09 | **The wall is derived, never stored**, which is what makes withdrawal free: moving a request back to `coordenacao` removes it from the next query with no cleanup step. The three columns live on the record; `_consent.py` is their only reader. If BE-09 ever stores requests, a withdrawn one is **deleted from that store**, never flagged and retained. **The one store that kept the text is the archived Pulse, and since OBT-561 (2/out/2026, Levi) it is cleaned too**: Karina, via Daniel, 1/out/2026 — *"o pedido é apagado também do Pulso guardado"* (the other options were keeping the Pulse whole for coordination only, or as it was). A withdrawal is the team **stating** a visibility other than `rede` over a request that was on the wall (`_consent.withdraws_authorization`), on a save or a health reading; `_submission_archive.erase_shared_requests` then removes the request, and the visibility answer that authorized it, from **every archived Pulse of the project that shared one** — that answered `rede` — whatever its words: the health wizard writes an edited text and restates `rede` in one save, so matching by text would miss a request the record has since spelled otherwise (Levi, 2/out/2026, on the review of shema-api#622). A Pulse that kept its request in coordination is left as it arrived. The row keeps `prayer_request_erased_at`/`_by` — never the text. A new text replacing the request is **not** a withdrawal and erases nothing. The content hash stays the hash of the bytes as they arrived, so the same file sent again is still a no-op. |
| 5.7 | **Intercessor network** | `shema_intercessors`, `shema_intercessor_consents` | BE-02, **BE-13** — §1.3 C3, settled | **Never joined to roles, in either direction.** Country is ISO 3166-1 alpha-2, never prose. At least one usable channel or the record is **refused**. **Removal erases** — no tombstone, no `removed` flag, the contact absent from storage. **BE-13 added consent as a row per (person, context)**, not a column: presence *is* the consent and withdrawal deletes the row, so a `granted = false` cannot exist; withdrawing the `network` context erases the person, because it was the basis the row stood on. **OBT-531:** a contact untouched for more than a year — the latest of entry, review and send — is **flagged for review**, served as `reviewDue` and never derived by the client; and a person with no account **leaves through an exit link**, which is the same erasure. |
| 5.8 | **Org chart** | `shema_region_teams`, `shema_role_changes` | BE-02, BE-13 | **The single source of who holds which role where**, with four consumers, all by reference. No other model stores a role-holder's name. A team change is a write **with an audit row**, not a silent update, and the name in the audit row is a snapshot that must not follow a rename. **BE-13 gave a seat a nullable `holder_user_id`** — the account, never the name; changing `holder_name` clears it, because the link belongs to the holder and not to the slot. |
| 5.9 | **Meetings** | `shema_meeting_log` (+ `shema_meeting_definitions` only if GATE-02 says so) | BE-02, BE-10 | Unique per `(meeting, scope, period)` — a second log for the same period **replaces** the first. The server derives `period` from the date and the cadence, never from the client. ~~**Whether the definitions are a table at all is Open · GATE-02** (§9.2).~~ **Answered by GATE-02 on 22/set: the set is global, so there is no definitions table** — §9.2. |
| 5.10 | **Notification preferences and read state** | `shema_notification_prefs`, `shema_notification_reads`, `shema_request_notices` (OBT-541), `shema_project_notices` (OBT-559) | BE-02, BE-15, OBT-541, OBT-559 | The panel's entries are **derived from the projects**, so their ids are not rows. The read state is its own small table keyed by `(user, derived id)` — which FE-44 §5.8's stable-id rule is what makes safe. **Route by role and region *before* capping at 30**; capping first lets one region evict another recipient's entries. |
| 5.11 | **ETEN ledger** | `shema_eten_credits`, `shema_eten_reports` (BE-11) | BE-02, BE-11 | A stored `manual` entry **overrides** the computed value; `calculated` marks what the rule produced. **A year with no data is not a year of zero credits.** Do not seed. The rule was **Open · GATE-01** (§9.1) and closed on 25/sep/2026 — BE-11's note below. |
| 5.12 | **Forms and intake** | `shema_submissions`, `shema_intake_links` | BE-02, BE-12 | The import is **idempotent and transactional** — a double import is a no-op. The submission is archived **byte-identically**. **Only the Pulse is archivable.** The leader link grants the intake form and nothing else, and it expires. Format is **Open · GATE-03** (§9.3). |
| 5.13 | **Region scope grant** | `shema_user_regions` | BE-03 | §6.1. One of the two things this module owns about identity (5.14 is the other). Empty means global. |
| 5.14 | **Project members** | `shema_project_members` | OBT-524 | §6.9. **One live row per account and project**, as a partial unique index (`WHERE removed_at IS NULL`); **removal marks** `removed_at`/`removed_by` and never deletes, and coming back is a new row. **Only the Admin writes.** Read by the project's scope, its own live members and the Admin. A membership is **not** a region. |

> **BE-06 ([OBT-395](https://linear.app/shema-obt/issue/OBT-395)) built the record's
> lifecycle on rows 5.1 and 5.2, and four decisions travel with it.**
>
> - **The version is an integer column, not `updated_at`.** The issue named both; this module
>   has already measured why the timestamp loses. `shema_progress_history`'s own docstring
>   records that `func.now()` hands every row of one transaction the same microsecond and that
>   SQLite's `CURRENT_TIMESTAMP` has one-second granularity — and two coordinators saving
>   inside one second is the case the guard exists for. A counter has no granularity to lose.
>   `SnSessionState.version` is the repository's precedent and `If-Match`/`ETag` the transport.
> - **The guard is required, against the precedent it otherwise copies.**
>   `app/services/sound_necklace/autosave_state.py` makes its `If-Match` optional because its
>   writer is one tab autosaving its own session. Here the writer is one of several
>   coordinators, so a skippable guard is last-write-wins one forgotten header away.
> - **The audit is its own append-only table** (`shema_record_edits`, §3.1) rather than a
>   column pair, and it is what makes the 409 explainable: keyed by the version a save
>   produced, it answers *what moved between the version I read and the current one*. The
>   **values** of a guarded field stay out of it — the key travels, `old`/`new` are NULL —
>   because a country copied into a second table with different readers has left the boundary
>   §6.4 holds. `shema_progress_history` gains **no** author column: `ProgressHistoryEntry` is
>   a shape FE-44 froze, and the trail is where the author of every write lives, progress
>   included.
> - **The progress batch is the record's own `PATCH`, not a second endpoint.** FE-44 §9.3
>   names the only split it will accept and asks in letters that BE-06 *not invent a different
>   one*. Atomicity is a property of the write path instead: the whole batch is validated
>   before a row is applied — every bad row named at once, by index — and the roll-up, the
>   history entry and the trail commit together or not at all.

> **BE-07 ([OBT-396](https://linear.app/shema-obt/issue/OBT-396)) built row 5.3, and five
> decisions travel with it.**
>
> - **The question set is a constant, not a table.** `app/utils/shema_health_questions.py` holds
>   every published set as an append-only tuple of `(version, [(dimension, i18next key)])`. A
>   version cannot be added by data alone — a new question needs its key in the console's
>   catalogue before it can be rendered, so a row inserted with no catalogue entry would be a
>   question with no text. §4.11's rule is what makes it cheap: a set names **keys**, never the
>   rendered sentence, so a translation changing is not a new version. `app/utils/shema_books.py`
>   is the precedent and `GET /api/shema/health-questions` serves the table as **provenance** —
>   what set *N* asked — and never as a second owner of what the wizard renders.
> - **`question_set_version` is nullable and NULL is not version 1.** The entry carried out of
>   the record's flat fields answered a Notion column rather than a questionnaire, and stamping
>   it would manufacture provenance. §7.4's two absences, arriving a third time.
> - **The author is its own pair of columns**, `created_by` / `created_by_name`, beside the
>   `assessor` the contract already has: the assessor is *who read the team* and the author is
>   *who entered the row*, and a mentor's visit typed up by the coordinator is one row with two
>   people in it. `shema_record_edits`'s pair is the shape, RESTRICT included.
> - **Immutable in the write path and not by trigger.** `append_assessment.py` is the only writer
>   and only ever inserts; no route updates or deletes an assessment. The trigger stays off for
>   the reason `app/db/models/shema_health.py` already gives — a mentor's typo in a note is a
>   person's to correct — so §7.2's *exactly two database-level invariants* is unchanged.
> - **No `If-Match`, against the record's own write.** Appending is not replacing: two mentors
>   filing two readings are two rows and neither is lost, so a version guard could only refuse a
>   reading taken in a conversation. The version is bumped and leaves in the `ETag`, because the
>   flat fields did move. The cost is stated where it is paid: the prayer request and the pastoral
>   answer a submission may carry are last-write-wins between two simultaneous wizards.
>
> And the **audience** is this module's answer to *read access at least as narrow as the
> record's*: `coordinator`, `obtLab` (and `globalStrategist`, until OBT-572) — `resourceCircle` opens the ficha and is
> refused the assessment, off FE-44 §5.8's own table. The same list addresses the critical notice,
> because notifying somebody who may not read it leaks the fact that it exists.

> **BE-11 ([OBT-400](https://linear.app/shema-obt/issue/OBT-400)) built row 5.11, after GATE-01
> closed on 25/sep/2026** — and the number it produces leaves the organisation, so the
> decisions are about making it explainable from stored data rather than reconstructible from code.
>
> - **The rule is `account_for` in `app/utils/shema_derivations.py`**, FE-44 §7.8's function over
>   ETEN's fiscal year (August to July; `?year=2026` ends on 31/07/2026, read by calendar fields).
>   It reproduces the console's `accountFor` with FE-51's two sources: a `concluido` record with
>   a `completed_date` and a defined scope is credited in the stamp's fiscal year; otherwise the
>   approved count crossing the scope between the two cuts decides. Three facts only the server
>   sees move it, each argued in the function: an approved count still copied from the export
>   (`approved_units_unverified`) is not a reading until a save moves it; a record that arrived
>   already complete (an `initial` entry at the scope) is undated, not credited in the year it
>   was filed; and a status recorded after the scope had already closed does not move a credit a
>   report has already given.
> - **`save_project` stamps `completed_date`** with the saver's day on the move into
>   `concluido`, clears it on the way out, and never on a create; the stamp is a `completedDate`
>   row in `shema_record_edits`, which is the event a credit is traced back to. **The record
>   serves it as `completedDate`** (`YYYY-MM-DD` or `null`) since OBT-413 (29/sep/2026): the
>   console's `Project` gained the key for FE-50's annual report and ETEN (PME #64), so it is the
>   contract's key, not one the server invented. It is the server's to write: the
>   write shape has no such field, so a `PATCH` or `POST` that carries it is a 422 on the whole
>   save, and the console's saves never carry it (`SERVER_WRITABLE`).
> - **Every report answered is recorded** in `shema_eten_reports` (append-only, deduplicated
>   against the newest row for the same year and scope), so the report sent in July still says
>   what it said after the data moves — the issue's *store the snapshot with the report*. Each
>   line carries its evidence on the wire too: the history entries read and their days, what
>   decided the year, who set a manual figure. **The recorded content holds the region and never
>   the country**, even for a project that is not flagged: a country in an append-only table is
>   beyond the reach of a flag raised later.
> - **The form is one owner, apart from the rule and the record.** ETEN changes its own report's
>   format every year, and on 28/sep/2026 the client had not received this year's (§9.1). So:
>   the rule is `account_for`; the data is the fields of `EtenYearReport`/`EtenYearSnapshot`;
>   the form in force is FE-44 §9.8's — how those shapes serialise (camelCase, `country` as a
>   `LocationDisplay`); and the record is `EtenYearReport.recorded()`, **the data under the
>   fields' own names**, which reads no alias and no computed field
>   (`test_the_recorded_report_keeps_the_data_and_not_the_form`). **ETEN's format, when it
>   arrives, is a presenter in `app/models/shema_eten.py`** — a function from `EtenYearReport`
>   to the shape ETEN asks for — served, if the server is the one that writes ETEN's file, by a
>   route of its own in `app/api/shema/eten.py` beside `GET /eten/report`, whose console
>   contract does not change. (The console's CSV and PDF are wave 2 and have no owner yet; if
>   the file is built there, the same presenter is the front's to write.) Neither the rule nor
>   the record moves; a fact the format asks for that the line lacks is a field on
>   `EtenYearSnapshot`, filled in `eten_report._line`, and it reaches the record as one more key.
> - **The `projectId` travels on the line** — the client allowed it on 28/sep/2026 (§9.4).
> - **The ledger holds manual rows only**, and names who set each one; a calculated figure is
>   kept with its readings in the recorded report instead. Setting one is the coordination's
>   (`coordinator` in its region, the `admin`; `globalStrategist` until OBT-572) — this issue's reading, one tuple to change.
> - **The line is an `outside` reader**: withheld for every role, the region's own coordinator
>   included, and still counted in the totals. `test_privacy_owners.py`'s route audit now walks
>   computed fields as well, with `EtenLocationShown` on a named allowlist.

> **OBT-541 (BE-21) rang the PME's bell for the resource-request form**, and three decisions
> travel with it.
>
> - **A detail table, because the notice finally points somewhere.** `shema_request_notices` is
>   keyed by the `notifications` row and holds the project, the registered name and the stage —
>   GATE-03 D4's whole ceiling, as columns, so nothing of the evaluation has one to arrive
>   through. A snapshot, like every name this module keeps in a trail. `stage` is text with a
>   CHECK over the five stages a notice announces, not the form's native enum.
> - **Who hears what is the door's own reading.** The decision reaches `started_by`; the arrival
>   reaches `admin` off the `shema` grant and `gestor` off the form's; neither reaches the actor; the mesa
>   is told in the form. No region routing: the Admin and the Gestor reach none and read every
>   request (BE-24). A request with no project — the Admin's link (OBT-537), a card the board
>   opened, a seed — rings nothing here, and an installation with no `shema` app rings nothing
>   and refuses the form nothing.
> - **The pointer is answered only to a reader who reaches the project.** A project's id is its
>   export slug, which names a place (§6.4). The panel answers `projectId` on a request notice when
>   the project is inside the caller's scope or the caller is one of its live members, and `null`
>   otherwise — where the record would have answered 404 anyway. The name and the stage go to
>   every recipient: the board already reads both on the form's card.

> **BE-09 ([OBT-398](https://linear.app/shema-obt/issue/OBT-398)) built row 5.6 — the wall, the
> authorization of a request and the Prayer Pulse — and stored nothing**, so the row's invariant
> holds as written: a withdrawn request is absent from the next read because there is no copy.
>
> - **One assembly of what may leave.** `_consent.authorized_requests` is FE-44's
>   `buildPrayerRequests` per project: the project's request under `reaches_prayer_wall`, each need
>   under its own `prayer_shared`, a request with no text left out. The wall
>   (`list_prayer_requests`) wraps it in `PrayerRequestEntry`, a `LeavingShape` validated off the
>   row and built for nobody — `outside`, so the region's own coordinator reads the region there
>   too; the Pulse (`generate_prayer_pulse`) is the wall rendered; BE-14's export reads
>   `authorized_requests_by_project`. None of the three has a path to the columns of its own.
>   The wall's projects are `visible_projects`, so a project the Admin has not confirmed
>   (OBT-547's `registered`) is on neither the wall nor the Pulse, for any reader.
> - **An authorization belongs to the request it was given for.** The project holds one request,
>   so a new one lands where the last one was and would inherit its `rede` — and the Pulso Mensal
>   writes the visibility only when the leader answers it. So a text or recording written without
>   the visibility in the same write clears an authorized request to NULL (`request_written`, in
>   `save_project` — the import included — and in `append_assessment`), and a shared need whose
>   description is rewritten without `prayerShared` is unshared (`need_written`). Stating it keeps
>   it: the health wizard sends both, and the console's consent control sits beside the text. The
>   media rule, *replacing the artifact resets the decision*, applied to the request. **The prayer
>   notice asks it of the submission** (OBT-554): it is staged before anybody applies the Pulse,
>   while the record still holds the last request's answer, so `submission_reaches_prayer_wall`
>   lets it through only when the Pulse itself answered `rede` and the record already says so. A
>   Pulse that wrote a request without that answer — a new text, `coordenacao`, the same text
>   again — announces nothing, whatever the project said before.
> - **Who reads a request nobody authorized is the health assessment's audience**
>   (`PRAYER_AUDIENCE = HEALTH_AUDIENCE`): `coordinator` and `obtLab` (and `globalStrategist`, until OBT-572) in their
>   scope, and an installation admin. The request is raised in the assessment and kept on the
>   health tab, and `coordenacao` is *the people who follow up and support*. `resourceCircle` —
>   the wall's audience, the role that shares with the network — reads what the team authorized:
>   the record answers it `prayerRequests: ""` and no recording for an unauthorized request
>   (`request_as_read`, carried by `Readership.withheld_prayer`, which `_deps._reading` sets), and
>   a `PATCH` from it naming the text, the recording or the visibility is a 403 on every record
>   (*não dá para editar o que não se vê*). The same reading BE-12 took for the submission inbox
>   and FE-44 §5.8 for the prayer notice. **Nor does it decide what is shared**: a need's
>   `prayerShared` is the team's authorization too, so a batch from it that raises a shared need,
>   shares one, unshares one or keeps one shared over a description it rewrote is a 403
>   (`undecidable_shares`) — read off the values, because the console sends a need back whole and
>   a flag that leaves the share where `need_written` would leave it without the flag decides
>   nothing. A rewrite sent without the flag is still its to make, and unshares the need. On a
>   create it writes the text it types (OBT-528's create exception, for the same reason) and not
>   `rede` (`authorized_on_create`). `refuse_prayer_decisions` is the one refusal for the three.
> - **The recording travels nowhere yet.** `prayer_requests_audio` takes any string a save writes,
>   so signing what it holds would let a writer mint a link to any object in `shema-private`; the
>   wall omits FE-44's optional `audioUrl` and the Pulse is text. An audio-only request reaches
>   neither until the recording has an upload path whose keys the server mints.
> - **Generating is not sending.** The Pulse writes nothing — not `last_sent_at`, not an exit link;
>   both are the send's, which is out of scope — and logs who generated it, over which scope and
>   with how many requests, never a word of what it said.

**Two shapes worth naming because they are easy to get wrong the same way the sibling did.**
The health assessment (5.3) is the module's counterpart of
[`docs/resource_requests.md`](resource_requests.md) §4.1's evaluation: the frontend edits it
inside the record, and that is a one-user convenience, not a persistence model. And the
progress history (5.2) is the counterpart of its §4.5 write path: one service function is the
single writer, and an imported update and a typed update go through it identically — which is
what makes them indistinguishable afterwards, and is exactly what FE-44 §9.9 requires.

---

## 6. The seams

### 6.1 Seam A — the region dimension — **Decided**

**The problem, stated exactly.** `require_role(app_key, role_key)` answers a global yes/no
per app. FE-44's `SessionPersona` is `{role, regionScope}` and a regional holder sees and
edits **their region**. `RegionKey` is one of seven fixed keys —
`south-america`, `north-america`, `africa`, `asia`, `oceania`, `europe`, `other` — and a
project's region is **derived** from the first country in its `location` string
(`getCountry` → `COUNTRY_REGION` → `other`), never stored as a membership.

Three shapes were available. The decision is the third.

| Option | What it costs | Verdict |
|---|---|---|
| **A — a `region` column on `user_app_roles`** | A platform migration touching the grant shape for **eight** applications, both guards in `app/core/access_control.py`, the role cache key, `grant_app_role`, `revoke_role`, `list_roles`, `list_role_holders` and `app/api/roles.py` — to serve one product's dimension. | **Refused.** A module does not migrate the platform's identity table. |
| **B — seven `organizations` rows + `organization_members`** | Reuses `app/core/org_scope.py` and nothing else fits. `organizations` carries `slug`, `logo_url` and **`manager_id`** — and `manager_id` would be a *second owner of "who leads a region"*, beside the org chart FE-44 §5.3 freezes as the single source with four consumers. `organization_members.role` is `member|manager`, a second role vocabulary beside the four Shemá keys. And a region is not a tenant: nobody joins it, it is computed from a country string. | **Refused.** It reuses a table by spending the one invariant the product is built on. |
| **C — a module-owned scope table, read by one service** | One small table, one service function, zero platform change. | **Decided.** |

**The shape.** `shema_user_regions (user_id → users, region_key)`, unique on the pair. A row
means *this account's scope includes this region*. **No rows means global** — the
`globalStrategist`, and any account the client wants unscoped — a case with no holder since OBT-572 retired that role. The grant itself stays
`(user, app, role)` and is written through
`app/services/authorization/grant_app_role.py`, never through `scripts/grant_app_role.py`
(§4.2).

**Why this is the same split the sibling already made, not a new idea.**
`app/services/resource_request/_scope.py` answers *which rows does this caller reach* in the
service layer, from the roles the platform grants, because the capability table had no scope
axis and the frontend's contract should not grow one. Here the platform has no **column** for
the axis, so the module keeps the column too — but the split is identical: **the platform
answers "who are you and in what role"; the module answers "how far does that reach."**

**The rules, so BE-03 does not have to re-derive them:**

- `app/services/shema/_scope.py` exposes one value, computed from one read — the sibling's
  `Reach` precedent, and for its reason: two questions off one fact should not be two queries.

  ```python
  class RegionScope(NamedTuple):
      global_: bool          # no rows, or a platform admin
      regions: frozenset[str]
  ```

- **Every list query takes it as a parameter.** A scope applied per endpoint is a rule the
  next endpoint forgets — the same argument FE-44 §8.2 makes for the consent gate.
- **A platform admin is global**, short-circuiting before the query, as they pass every other
  guard in this repository.
- **The region a project belongs to is derived, not stored** — but a derived column is what a
  scoped query needs to be sargable over 127 rows and more. **Open · BE-02:** store the
  derived `region_key` as a generated/maintained column written by the same service that
  writes `location`, so the derivation keeps exactly one owner
  (`app/utils/shema_derivations.py`) and the query keeps an index. Never a second hand-typed
  field.
- **Writes are scoped by the same value as reads.** A regional `coordinator` who may read a
  region may write it; there is no third answer in the product about *which records*. *Which
  fields* is §6.4's question since OBT-528: the place and the flag are coordination's to write.

**What a caller sees of another region's project — answered by BE-03: nothing.** The issue
named the two defensible answers, *nothing* and *the existence without detail*, and asked
that one be chosen rather than fall out of how a query was written. An out-of-scope project
is absent from the collection, absent from every count, and refused on a direct id with
`NotFoundError` — **never** `AuthorizationError`. The status code is the sharp end of the
choice: a 403 on a direct id **is** the existence-without-detail answer delivered by status
code, and a caller who can tell *this slug is real but not yours* from *no such slug* holds
an oracle over the whole collection. A Shemá slug was `<language>-<place>` (every id is an opaque UUID since OBT-552), and for the two
records FE-44 §8.1 flags, existence in a region is precisely the fact being protected. The
two refusals therefore carry the same exception and the same message.

**And the log line does not tell them apart either — it records the event, not the verdict.**
`get_project`'s branch fires on any miss of the scoped statement, so a mistyped id reaches
the same line an out-of-region one does, and settling which case it was would take the
unscoped query the 404 exists to avoid. So the line names the caller, the operation, the id
asked for and the regions the caller does hold — the fields a misconfigured scope and a probe
look different in — and classifies the outcome as *no row, out of region scope or no such id*
rather than announcing a refused authorization the service never decided. An investigator
allowed to know which it was joins the id where being allowed is checked —
`app/services/shema/_scope.py`.

**"No rows means global" held for `globalStrategist` and for nobody else, and since OBT-572 for nobody at all — BE-03 narrowed
it, deliberately.** The sentence above names who the empty case serves; read as *anyone with
no rows is global* it inverts the product's own rule, which is that a regional coordinator
sees **their** region. It also has a live path to it: `app/services/access_request` grants a
role on approval and grants no region, so every approved account would land globally scoped.
So a **regional** role with no row reaches nothing, and making such an account unscoped is
an explicit act — name its seven regions (granting `globalStrategist` was the other way, until OBT-572). The
`default_role_for("shema")` entry is `resourceCircle` for the same reason: an approval hands
out a role and no data.

**Since OBT-543 the Admin's surface clears the rows when the last regional role goes**, and every
change to them — by that surface, by an accepted invite, by an operator — is a row in the
append-only `shema_scope_changes` (§6.10). Other doors still leave rows behind, which the next
paragraph makes harmless.

**And a row counts only under a regional role — OBT-523 closed the converse.** An account
holding no regional role reaches nothing whatever rows it has,
without the table being read. Nothing deletes an account's rows when its regional role is
revoked, and a seat or an operator can leave one behind; without this, the `admin`, `gestor`
and `mesa` of §6.8 would reach a region by accident of data. The three regional roles reach
exactly what they reached before.

### 6.2 What the region scope is *not* allowed to become

Two temptations, refused here so nobody spends a week on them:

- **Not a filter the router applies.** `app/api/shema/` may declare the dependency and hand
  the value down; it may not `WHERE` anything. Zero database access in `app/api/`.
- **Not a second copy on the project row.** `regionalCoordinator`, `obtLabPerson` and
  `resourceCirclePerson` are export columns that are **empty on all 127 records and stay
  empty on purpose** (FE-44 §5.1). The server **rejects or ignores a write that fills them**.
  A name stored there is a second owner of a fact `shema_region_teams` owns.

### 6.3 Seam B — how the frontend learns its own scope — **Decided**

```
GET /api/shema/session -> {role: SessionRole, roles: SessionRole[], regionScope: RegionKey[] | null,
                           name: string | null, apps: {resourceRequestForm: string | null}}
```

`roles` and the door it sits behind are OBT-523's, §6.8; `role` is the first of `roles`, kept
only through the transition. `apps` is OBT-544's: the form's `apps.app_url` from the registry,
without a trailing slash, `null` when the registry has no row or no value — the address for the
PME's *Solicitar recurso* and *Resource Circle* entry (project-management-ecosystem#70), so the
console holds no constant for it.

`GET /api/auth/my-roles` cannot answer this, because the grant has no region. The three parts
come from three places and **none of them is a store of the session's own**: `role` (and, since
OBT-523, `roles`) from `authorization_service.list_roles` — one read of both apps, §6.8, plus, since OBT-524, one
read of `shema_project_members` for the `equipe` a live membership adds (§6.9); `regionScope` from
`shema_user_regions` (`null` = global); and **`name` resolved from the org chart** (§5.8) —
it is not a user profile field, and renaming a role-holder renames who the session says you
are.

`admin` is a role key with no org-chart seat (the chart's three roles are per
region). FE-44 §12.2 leaves `GLOBAL_STRATEGIST_NAME` as the frontend's one remaining
hardcoded name. ~~**Open · BE-03:** whether `name` for that role falls back to
`users.display_name`.~~ **Answered by BE-03: yes, and the fallback is one rule rather than
four special cases.** The chart's rule exists so there is no second owner of a seat's name;
a seatless role has no seat, so there is no fact being duplicated and no rename to follow,
and the rule does not reach it. `null` was the alternative the contract permits, and it would
guarantee that `GLOBAL_STRATEGIST_NAME` stays — which is what this endpoint exists to retire.

So: the seat is read when there is exactly one seat to read — the role has a seat **and** the
scope names exactly one region **and** the seat is filled. Global scope, a two-region scope,
a seatless role, and an unassigned seat all fall back to `users.display_name`, and the
last of those is the ordinary path rather than an edge case: all twenty-one seats ship
unassigned.

### 6.4 Seam C — privacy, and why it is three owners and not one — **Decided; BE-04 built; OBT-528 made it depend on who reads**

FE-44 §8 is written as server requirements and `CLAUDE.md` §6.1/§6.2 as invariants. The
scheduling is already right: BE-04 lands **before anything that emits data**. What this
document adds is where the rules live, because *"enforced in the service layer"* is not yet a
file.

**Three owners, each the sole reader of what it guards:**

| File | Owns | The rule |
|---|---|---|
| `app/services/shema/_redaction.py` | `sensitive_country` | The location is replaced by the **region name** — the withheld **marker**, never an empty string, so the redaction travels in the shape and a renderer downstream cannot leak what the payload does not hold. Coordinates become the region centroid. **The base name goes with the location** in any file that leaves: both flagged records carry a base that names a place (`YWAM Egypt`, `YWAM Morelia`), so withholding `Egypt` while printing `YWAM Egypt` one column over redacts nothing. Since OBT-528 it also answers the write's question — which fields a reader who is not coordination may not write — and addresses the withheld notice to a reader. |
| `app/services/shema/_consent.py` | `prayer_requests`, `prayer_visibility`, `prayer_requests_audio` — **and `source["prayerRequests"]`, which is a fourth copy of the same text** | **The only reader of those three columns**, and one query applies the gate. `prayerRequests` is one of the export's 55 keys, so `shema_projects.source`, which keeps the export row verbatim, carries that key too under the export's own camelCase spelling — empty in today's export, and where the next one's text lands; `prayerVisibility` and `prayerRequestsAudio` are two of the 18 the product added and are not in it. The column is **nullable and NULL means `coordenacao`** — do not default it to `rede` and do not backfill it. It is a **visibility level, not a published boolean**: a team that has not consented to being shared still reaches the people who follow up. |
| `app/services/shema/_media_sharing.py` | `authorization` on media and materials | Composes, most restrictive wins: an authorized item reaches `coordenacao`; the same item on a sensitive project **never** reaches `publico`. |

**Who reads, and not only where it goes — OBT-528.** BE-04 drew the line at the door of the
record: the record read carried the truth to its whole audience, and every shape that left
coordination carried the redaction. GATE-04 moved the line
to the reader (Karina, 22/sep, items 1.1–1.3; Daniel, 23/sep, on who coordination is): **the
truth of a sensitive place belongs to coordination**, and every other role reads the region
in its place, *inclusive na ficha*. So every leaving shape — the ficha included — is built
**for a reader**, `ShemaReader`, and one class covers the three values:

| | `coordination` | `trusted` (OBT-571) | `other` | `outside` |
|---|---|---|---|---|
| **Who** | a `coordinator` on a project in a region of their scope; the `admin` (*the issue's reading, confirmed by Daniel on 8/oct/2026*); an installation admin (and `globalStrategist`, until OBT-572 retired it) | a `resourceCircle` on a project in a region of its scope — reads the truth, writes nothing of coordination's | every other session in the console: `obtLab`, `resourceCircle` | whatever leaves the system: the export, the ETEN report, the Pulse, the leader's link, the urgent-need notice |
| `location`, `country` | the truth | the truth | the region **key** | the region key |
| `location2`, the base (`team` / `ywamBase`), the three contacts, `sensitivity` | the truth | the truth | `""` | `""` |
| `notes`, `healthNotes`, `statusComments`, `scopeDetails` (OBT-556) | the truth | the truth | `""` | `""` |
| `coords` | the truth | the truth | the region centroid | the region centroid |
| `sensitiveCountry` (the ficha) | the flag | the flag | the flag | — |
| `locationWithheld` | the flag, fail-closed | the flag, fail-closed | the flag, fail-closed | the flag, fail-closed |
| `readAs` (card and ficha) | `"coordination"` | `"trusted"` | `"other"` | — |
| `locationsWithheld` (the collection) | how many, or `null` when none | how many, or `null` when none | `null` | — |

Only a **withheld** record is reduced — flagged, or built from something that could not say.
A cleared record is the truth for every reader. On a reduced ficha `location2` and the two
optional contacts read `""` rather than `null`.

**The `trusted` column is OBT-571's** (Karina, via Daniel, 6/oct/2026: *"o Resource Circle poderá
ver tudo, mesmo os projetos em países sensíveis, só não podem editar"*; Daniel, 7/oct/2026: the
*tudo* includes the **health**, and the **OBT Lab stays redacted**). The Resource Circle reads a
sensitive project in its own scope exactly as the coordination does — the place, the base, the
contacts, the reason, the real language name, the free text, the needs' descriptions, the
history's notes, the count of withheld projects and the `sensitive` facet — and the health on
the ficha, the card, the health tab, the filter, the order and the file it exports
(`_health_audience.HEALTH_READERS`). **And it writes nothing** — Daniel, 7/oct/2026, reading
Karina's *só não podem editar* whole: no project write on any route, not even the fields the
`other` reader edits in its own scope, nor a need's description on any project. Until then the
Circle saved and created records as any Shemá role did in its scope; `save_project.refuse_circle_writes`
now refuses both (`Readership.edits_no_project`, read off the `trusted` field — a Circle who also
coordinates is coordination and edits; one who is also OBT Lab is refused too, the stricter
reading). The refusal comes **after** the scope's own 404, so a project out of reach still hides.
`readAs` is a third value because the console asks it two questions at once — *is this the
truth?* and *may I edit the place and the flag?* — and this is the first reader whose answers
differ. `Readership.trusted` carries where a caller reads the truth apart from where it
coordinates, so every other write path (`refuse_unread_health_writes` — now gated on the
**audience**, `import`, the ETEN ledger, the meetings' log, filing an assessment) keeps asking
the coordination and the audience; `tests/test_shema/test_resource_circle_reads.py` holds a 403
per write route, the save and the create included. A `trusted` payload is refused as an import, because it is still not the
whole record: a prayer request kept in coordination is `""` to the Circle
(`_consent.PRAYER_AUDIENCE` did not move). The meetings' pastoral log did not move either — the
issue names the ficha, the card, the health tab, the filter and the order, and a debriefing is
none of them.

**Where the reader comes from.** `app/services/shema/_scope.py`'s `readership` answers it from
the grant and the scope the request already read — no query of its own — as a `Readership` the
services ask per project (`reader_of(region_key)`), and `app/api/shema/_deps.py` hands it down
as `Reading`, exactly as it hands down `Scope`. A `coordinator` is coordination **in the regions
of its own scope** and `other` anywhere else it reaches. Region rows are per account and not per
role, so an account holding `coordinator` and `obtLab` is coordination wherever it reaches; the
org chart is not consulted. The `admin`'s coordination is one line — `COORDINATION_EVERYWHERE`,
a hypothesis of OBT-528's until Daniel confirmed it on 8/oct/2026 — and undoing it is deleting
`admin` from it. `visible_projects` is untouched: who may **reach** a
project and who may read its **place** are two questions.

**Who builds a shape for it.** Only the two reads of the console: the Projetos screen's cards
(`browse_projects`) and the record (`build_record` — `GET`, `POST` and `PATCH /projects…` and the
health-assessment `POST`). A shape reaches its reader only through `LeavingShape.read_by`, which
puts it in the validation context; the reader is kept on the instance and **no input can set
it**, and a shape built any other way is `outside`. So every other leaving shape — the export
row, the ETEN line, the Pulse entry, the leader's form, the need line an urgent notice is written
from — is `outside` whoever asked for it, and an endpoint written by somebody who never read this
section still emits the form that leaves. The notification panel builds its stale cards with
`NO_COORDINATION` for the same reason: a notice is an output path.

**The marker is the flag, for every reader.** `locationWithheld` says *this record's place is
withheld from everything that leaves coordination* — the same bit whoever reads, and a
coordination payload carries the truth **beside** it. That is deliberate: the console maps the
bit to `sensitiveCountry` and redacts its own map and its client-side export from it, so a
coordinator who now receives the truth keeps the bit that keeps their export redacted. What says
whether the payload in hand is the truth or the reduction is `readAs`, added to the card and the
ficha only: `locationWithheld && readAs == "other"` is a reduced payload, whose `location` holds a
region key; `readAs == "coordination"` is one whose place and flag this reader may edit. The
console reads that answer instead of keeping a second copy of the rule (OBT-532).

**The notice is coordination's.** `withheld_note(records, reader)` counts the markers and
announces them to `coordination` only; the caller says who the announcement is for, which is not
always who the rows were built for — the Projetos screen addresses it to its caller, and a file a
coordinator exports would carry rows built for `outside` under a header addressed to the
coordinator (BE-14's). Every card still carries its marker — GATE-04 decided the notice, not the
bit. **The `sensitive` facet is the same notice counted again, so since OBT-556 it is
coordination's too**: for a caller who coordinates nothing it is absent from `groups` and
`groupAll`, and their `?sensitive=` is ignored, because its `matched` would be the number again.

**The search and the facets read the card the reader was given.** Coordination finds a withheld
project by the place it reads and counts it under its country; everybody else can do neither,
because their haystack and their card hold the region.

**The write: *não dá para editar o que não se vê*.** `save_project` asks
`_redaction.unwritable_fields` which of the fields a save sent this reader may not write, and
refuses them with `AuthorizationError` — a 403 naming the fields in the client's spelling and
nothing about the record, raised after the scope has found the record and **before** the version
is compared, logged with `log_reference`:

| Field | `coordination` | anybody else |
|---|---|---|
| `location`, `location2`, `coords`, `sensitiveCountry`, `sensitivity` | writes | refused on **every** record |
| the base (`team` / `ywamBase`), `teamContact`, `teamLeaderContact`, `mentorContact` | writes | refused on a **withheld** record; writes on a cleared one |
| `notes`, `statusComments`, `scopeDetails` (OBT-556) | writes | refused on a **withheld** record; writes on a cleared one |
| a need's `description` (OBT-556) | writes | on a **withheld** record, the `""` it was handed is read as unchanged and any other text is refused; a new need is its author's to describe |

There is no `country` to write: it is the first segment of `location`, so refusing the location
is refusing the country. The answer depends on the **names** the payload set and never on their
values, so it is not an oracle. **A create is not the refused write**: the creator sees what they
type, and closing it would need a narrower rule (the flag and the reason only), because the
location a record is filed with is what puts it in its creator's region — an open question for
Daniel, recorded in the PR. The form imports reach `save_project` with the importer's own reader.

**No route is exempt any more, and one list replaces the exemption.** `COORDINATION_ROUTES` in
`tests/test_shema/test_privacy_owners.py` is empty again: the record is a leaving shape and the
route audit asks it like any other. `READER_ROUTES` names instead the routes whose dependencies
reach the caller's reader — the only ones that may build a payload carrying the truth — and a
new route that took `Reading` (an export, say) is red there until somebody lists it and argues
it. The collection's and the record's answers carry `Cache-Control: private, no-store`
(`PER_READER_CACHE_CONTROL`): one URL — and one version of one record — now reads two ways, and
no cache may hand one reader's body to another. Since OBT-555 that is every answer the module
builds, not these two: the outer router carries the rule (§3.3's *Caching* row), and
`tests/test_shema/test_cache_control.py` calls every `GET` to see it on the wire.

**Two coordinations, deliberately.** `ShemaReader.COORDINATION` is GATE-04's membership — who
reads a sensitive place. `ShemaAudience.COORDENACAO` is FE-44's destination — every role that
follows up and supports — and it still decides notes and media (`can_export_notes`,
`can_share_media`). GATE-04 decided the place per role and said nothing about notes, prayer text
or media, so those keep their own owners. **Except a withheld record's free text, since
OBT-556** (the paragraph below): the client decided on 2/out/2026 that it goes with the place.

**Who reads a team's health — OBT-553.** The assessment's own route refused the Resource
Circle (`require_reads_assessments`), while the ficha, the card and the search handed it the
projection, the history and the pastoral follow-up. `_health_audience.py` now answers the
question for every door, once: `in_health_audience` reads it off the grant the request already
holds, `app/api/shema/_deps.py` sets `Readership.reads_health` with it (`False` by default, so
`NO_COORDINATION` reads no health), and `health_as_read` is what a shape becomes for a reader
outside `HEALTH_AUDIENCE` — every health field as a project nobody has assessed holds it
(`null`, `""`, `needsPastoralIntervention: "nao"`, `healthHistory: null`), the keys kept because
the contract is frozen. It is `_consent.request_as_read`'s mould, a service-side update, and it is
applied **before** anything derives, filters, counts or sorts from the shape, because the card's
tone (`priority`), `derived.health`, `healthScore`, the *atenção* preset, the health facet and the
health order are all computed from those fields. One named place per surface, where a later rule
about the same reader sits beside this one:

| Surface | Where | For a reader outside the audience |
|---|---|---|
| The ficha | `read_record._record_as_read` (with the prayer request's `request_as_read`) | health fields empty, history `null` |
| The card | `browse_projects._card_as_read` | health fields empty |
| The search's question | `browse_projects._query_as_read` | `?health=` **ignored** — as an unknown preset is; an invalid value here answers an empty list, which would say *no project matches* and zero every count — and `sort=health` falls back to `deadline`, echoed in `sort` |
| The search's counts | `browse_projects._facets_as_read` | no `health` key in `groups` or `groupAll` — not `{"na": total}`, a number about nothing |
| The file | `export_projects._write` | `overallHealth: "na"` in every row; the place is `outside` for everybody, as before |
| The panel | `list_notification_panel` | delivered health notices left out in the query, before the cap — a notice is read by who the account is now |
| The write | `save_project` → `refuse_unread_health_writes` | the three pastoral fields refused 403 by name (*não dá para editar o que não se vê*); a create stays free, OBT-528's exception |

The Shemá `admin` role is outside the audience, as `require_reads_assessments` already had it; an
installation admin reads. `tests/test_shema/test_health_reader.py` holds every row per role, a
net that fails when a shape gains a health field the reduction does not name, and a net that
fails when a service builds a record, a card or an exported row without asking `health_as_read`.
**Residuals, named:** the prayer wall dates an authorized request by
`healthAssessmentDate || lastUpdated` (FE-44's rule, `_consent._request_day`), so the circle can
infer the day of a reading — never its level, notes, assessor or follow-up; the 409's
`changedFields` names `healthHistory` and the pastoral keys that moved, without values (OBT-556
item 2 filters it by what the reader sees); the trail stores the pastoral values and no route
reads them; and a hand-made file built from the Shemá `admin`'s record, which reads as
`coordination` and now carries empty health, would write the empty follow-up over the truth if a
coordinator imported it — the same gap the import has for the prayer request.

**Residuals named and not closed** — each can name a place and none is reduced for `other`:
~~the slug `<language>-<place>`, which is the record's address on every shape~~ (closed by OBT-552: every id is an opaque UUID); the free text of
the ficha that OBT-556's list left out (`partnerOrg`, `statusGoal`, `phases`, `needsNotes`,
`objectiveNotes`, `financialNotes`, a need's `estimatedValue`, a material's file name or link,
media captions and URLs); `storyProgress[].recordLocation` and its copy in
`progressHistory` — reducing a field inside a table the progress tab saves whole would make the
next save of that table erase the truth; and the text a team authorized for prayer, which
reaches the wall, the Pulse and the export by its consent (`_consent.py`) whether or not the
place is withheld. They belong to GATE-04's *Notes & media* column, which the grid has not
answered per role. ~~`notes`, `healthNotes`, `statusComments`, `scopeDetails`, a need's
`description`, the assessments' notes and the submissions inbox's free text~~ — closed by
OBT-556 on a withheld record, below.

**What a withheld record holds back beyond its place — OBT-556.** The INT-12 pass found the
record's text leaving by five doors, and the client decided on 2/out/2026 to close them all
(*recolher tudo*) for every reader who is not coordination:

- **The record's own four** — `notes`, `healthNotes`, `statusComments`, `scopeDetails` — are
  `FREE_TEXT_FIELDS` in `app/models/shema_privacy.py`, so `LeavingShape` empties them as it
  empties the base, on the ficha, the card and any shape that declares one later. The export
  carries none of them (`can_export_notes` refuses notes for `publico`, and the 24 keys hold no
  other), which a test now holds on the bytes.
- **What the record joins after it is built** — each need's `description`, and the assessments'
  `notes` and `dimensionNotes` — is reduced by `_redaction.free_text_as_read` in
  `read_record._record_as_read`, the record's one reduction point; the assessments' own route
  (`GET /projects/{id}/health-assessments`) by `_redaction.assessments_as_read`, which is why
  it is in `READER_ROUTES`.
- **A received Pulse** answers the free text that maps to no column as `{}` with
  `answersWithheld: true`.
- **The write**: the four are in `WITHHELD_WRITES`, refused by name like the base. A need's
  description is read by value instead (`_redaction.need_text_as_written`), because the console
  sends every need back whole: the `""` the reader was handed comes back and is read as
  *unchanged* — the text stays and its share for prayer does not fall — while anything else is
  a text typed over one the reader cannot see, refused as `needsItems.description`.
- **The conflict a save meets** (`_audit.changes_since`, told to a `Readership`): the 409 names
  only the fields the reader reads on that record, with who and when from the newest change
  they can see — `null` for both when there is none. A prayer request kept in coordination is
  left out for a reader outside its audience the same way.

One predicate decides when, `_redaction.reads_the_truth(project, reader)`: coordination, or a
record whose place is not withheld. The console's `mayWrite` does not know the four yet; until
it does, a value typed into one of them on a withheld record is the 403 that names it.

**A validation error says nothing about the value it refused — OBT-556.** FastAPI's 422 hands
each field error's `input` back to whoever sent it, and an unexpected Pydantic error — a row
that will not validate into its shape, a response that does not fit its model — reached
`handle_unexpected` and then the server's own traceback with `input_value=` in its message, a
place or a contact as easily as anything else. Every route under `/api/shema` is a
`ShemaRoute` (`app/api/shema/_routing.py`), because the module's three routers are
`ShemaRouter`s and hand the class to whatever is included into them: a 422 keeps `type`, `loc`
and `msg` in FastAPI's own envelope, and an unexpected error leaves the route as
`UnexpectedShapeError`, named by model, location and kind. `msg` travels as the validator wrote
it, so a validator of this module says what it expected and never the value it refused — the
need's currency and amount, a book's id and chapters, a row's counts, a health note's key and a
question set's version used to, and `tests/test_shema/test_quiet_errors.py` holds them to it. **Only here**: the handlers in
`app/core/exceptions.py` are eight applications', and their 422 is a contract other clients
read. It is a route class and not a handler because Starlette's `ServerErrorMiddleware`
re-raises after the handler answers, so a handler alone would leave the server's log as it was.

**The check that makes it a rule rather than an intention.** FE-44's frontend has a scan test
that fails the build if any shipped file outside the record's own editing surfaces reads the
raw prayer columns. **BE-04 owns the same test here**, and this repository already has the
shape for it:
`tests/test_resource_requests/test_access.py::test_the_app_key_is_named_once_in_the_module`
globs a directory and fails on a literal. `tests/test_shema/test_privacy_owners.py` globs
`app/services/shema/*.py` and `app/api/shema/*.py` and fails when a file that is not the
named owner references one of the guarded columns. A rule applied per endpoint is a rule the
next endpoint forgets; a glob is not.

**The literals that test looks for are four, not three.** `prayer_requests`,
`prayer_visibility` and `prayer_requests_audio` are the columns, and `prayerRequests` is the
same field again inside `source` — the export row kept verbatim (§5.1). A guard written on the
three snake_case names reads that copy and does not see it.

**The acceptance test the delivery plan already names:** an unauthorized prayer request is
absent from **all four** output paths — the wall, exports, the ETEN report and notifications.

> **BE-13 added a fourth owner, on a different subject.** The three above guard facts about a
> project; `app/services/shema/_directory.py` guards a **person** — the network's contact
> column, its sensitive-country flag and every read and write of `shema_intercessor_consents`
> — and it is the only file in `app/services/shema/` or `app/api/shema/` that names
> `ShemaIntercessor`, checked by the glob this section asks for
> (`tests/test_shema/test_people_privacy.py`). It reuses this section's mechanism rather than
> inventing a second: the same flag, the same withheld marker (FE-44 §9.6's `country: ""`
> beside the marker), the same *redact on every path that leaves* split — the network's read is
> still a coordination surface; OBT-528's reader is about a project's place and did not reach
> it. If the shapes want to be one function, `leaving_person` folds into `_redaction.py` and the
> glob moves with it.
>
> **One residual is named and not closed.** A withheld person's *name* still travels, because
> the rule above withholds a **location**. Whether a person's name is itself a location in a
> dangerous place belongs to §9.4's fourth gate, whose own instruction is to raise it rather
> than invent it surface by surface.

> **OBT-531 answered §10 item 8's other two questions**, with the client's answers of 22/sep,
> and every file is still under the fourth owner: `_directory.py` names the new table too.
>
> - **A contact nobody has used in a year is reviewed, not expired** (4.3). `shema_intercessors`
>   gained `reviewed_at` and `last_sent_at` — the second is BE-09's to write when the Prayer Pulse
>   goes out, NULL until then — and `_directory.review_due` is the one reading: due when more
>   than 365 days have passed since the latest of `added_at`, `reviewed_at` and `last_sent_at`.
>   The list serves it as `reviewDue`; `POST /prayer/intercessors/{id}/review` (`resourceCircle`)
>   stamps the review. A review is explicit — an edit, a read of the contact or a re-stated
>   consent does not reset the year.
> - **The people no list may show are counted, not reviewed.** Somebody with no `directory`
>   consent is on no screen, so nobody can review them there; `withheldReviewDueCount` is a
>   number beside `withheldCount`, read from three dates and nothing else. What to do with them
>   is a question for the client, raised in the pull request. **Both count the members of the
>   network** since OBT-556 — holders of `network` — so a row imported with no consent at all
>   is announced by neither (`_directory.count_withheld`).
> - **A person with no account leaves through an exit link** (4.2, *"ainda não existe
>   caminho"*). `shema_intercessor_exit_links` keeps one row per link minted — the digest only,
>   §6.7's module, `ON DELETE CASCADE` from the person — and `leave_intercessor.issue_exit_link`
>   is what BE-09 calls once per send. **No link is revoked by a newer one**: each lives
>   `shema_intercessor_exit_link_days` (365), so the reader of an older message can still leave,
>   and a link that leaks can only remove somebody, which is the safe direction; a link past its
>   clock is deleted at the person's next send. The issue's
>   *rotated at each failed confirmation* is read as *every send carries a fresh token and none
>   is ever reused*; burning a link on a failed confirmation could only strand the person who
>   wants out, and that reading is raised in the pull request rather than built.
> - **The confirmation page is the console's, and the API answers 204.** `GET
>   /api/shema/intercessors/leave/{token}` reads and changes nothing — a link previewer opens
>   every URL — and `POST` erases the person, their consents and every link, by the same
>   `_directory._erase` removal uses. Every link that opens nothing gets **one** sentence, so a
>   forwarded link does not tell whoever holds it whether the person is still in the network.
>   Both routes are limited **per address** with `shared_limit` and a fixed scope: slowapi's
>   default scope is the URL, which here carries the token, so `@limiter.limit` would have been
>   per address *and token* — and would keep the raw token in the limiter's key. The intake
>   routes have that shape today; it is named in the pull request, not changed here.
> - **The batch consent waits for the client** (4.1). `scripts/shema_backfill_network_consent.py`
>   takes the basis as an argument, inserts `network` only where it is missing and never
>   restamps an answer that stands, and nothing runs it.
#### What BE-04 built

**The rule is not in `_redaction.py`. It is in `app/models/shema_privacy.py`, and it is
inherited rather than called.** Everything else in this section held; this one line did not,
and it is worth the paragraph because the reason generalises.

The DoD asks that *adding a new endpoint without knowledge of the rule still yields protected
output*. A service function cannot deliver that — it has to be **called**, and a call is what
the next endpoint forgets, which is the very sentence this section opens with. So the rule
lives in `LeavingShape`, a Pydantic base class that every shape leaving coordination inherits,
and it is applied in a `model_validator(mode="after")`: an author who writes
`class PrayerRequestOut(LeavingShape)` with a `location` field gets the redaction **by
declaring the field**, which is the one act they cannot skip. That is the serialization
boundary the issue asks for, spelled in the only place FastAPI gives one.

It could not live in `app/services/shema/_redaction.py` because
`tests/test_app_boots.py::test_no_dto_module_reaches_up_into_the_service_layer` forbids a DTO
module from importing `app/services/` — the inversion that closed an import cycle once — and
the rule has to be reachable from the shape for the paragraph above to be true. This is the
same trade §3.1 already makes for the derivations, arriving one issue earlier: the half that
both services and response models need lives where the response models may reach it.
`_redaction.py` keeps what a `Select` cannot inherit — `is_withheld`, `withheld_note`,
`log_reference` and `searchable_text` — and stays the module's sole reader of the guarded
columns.

**The fields a leaving shape reduces**, in one list, because the value of one list is that
there is one: `location`, `location2`, `country` (to the **region key**, never an empty
string), `latitude` / `longitude` / `coords` (to the region centroid, so the marker moves
rather than disappears), `team` / `base` and the three personal contacts (to `""`), and — since
OBT-528 — `sensitivity` (to `""`). A `coordination` reader reduces none of them.

**Fail closed, and the closed state is the default.** A shape built from something that cannot
answer whether the record is sensitive — a hand-assembled dict, a partial row, a join that did
not select the column — withholds. The cost is a coordinator clicking through to the record;
the alternative costs somebody their safety, and fails silently.

**The withholding is visible and says nothing about what.** `locationWithheld` is in every
leaving shape's output, always. For a collection or a file, `withheld_note` answers *how many*
rows are withheld — to coordination only, since OBT-528 — and answers `None` rather than `0`,
because *"0 locations withheld"* on a file with no sensitive projects is a sentence about the
absence of sensitive projects, said on every file, and interesting exactly when it should not be
said.

**Three nets, not one**, and `tests/test_shema/test_privacy_owners.py` is all three. The glob
this section already asked for, over both `shema` packages and now for three column sets
(sensitive country, consent, media authorization), each with a one-entry allowlist a later
issue extends by writing a line it has to justify. **A route audit** that reads the built
application's route table and fails when a response model under `/api/shema` can name a place
and does not inherit `LeavingShape` — the `UNAUTHENTICATED_PATHS` shape of
`test_access.py`, applied to the payload instead of the guard, with `COORDINATION_ROUTES` empty
today and BE-06's record read as the one line expected in it — BE-06 wrote it, and OBT-528
emptied it again when the record joined the boundary. And a vocabulary check, so the list of
guarded fields and the list of replacements cannot drift apart. OBT-528 added a fourth: the
routes that take the caller's reader (`READER_ROUTES`) and the two services that build a shape
for it.

**And the bytes, because a predicate that ends in a public URL decides nothing.** §4.6's
verdict is built: `app/services/shema/_media_storage.py` holds the `shema-private` bucket and
the content-addressed key, `app/services/shema/media_download_url.py` applies
`can_share_media` on the only address the bytes have, and the address is a signed GET that
expires in fifteen minutes and is persisted nowhere. **One departure from the sibling's key
shape, and it is this section's own argument arriving in the object store:**
`resource-requests-private` scopes a key by its `request_id`; this one scopes by the media
row's uuid, because a Shemá id is `<language>-<place>` and a signed URL travels further than
the payload it came from — into a history, a referrer, a proxy log, a forwarded message. The
refusal reads the same sentence whichever of its three reasons fired, for the reason the whole
section gives: *why* is the fact being protected.

**Two departures, each declared in BE-04's PR rather than absorbed here.** The base name is
withheld on **every** leaving shape and not only in a file (§9.4 — the gate keeps the console's
own rendering, which is presentation). And the collection read is a leaving shape, with only
the record read a coordination surface, because the issue names *list* among the output paths
and FE-44 §8.7 says display is never enforcement. OBT-528 closed the second: the record is a
leaving shape too, built for its reader.

**A notification that points at a project leaks its slug** (OBT-541) — *true until OBT-552, which made every id an opaque UUID; the rule below still holds and now costs nothing.* A project's id was the
export slug, `<language>-<place>`, so a notice that carries it tells its reader where a project
is — and the resource-request form's arrival reaches the Admin and the Gestor, who reach no
region. `list_notification_panel.py` answers a request notice's `projectId` only to a reader the
project is inside the scope of, or who is one of its live members, through `within_scope` and
`live_membership_ids`; everybody else gets `null`, which is §6.1's answer for a project out of
scope. The notification row itself carries no slug and no place in its title or body.

**A notice is read later than it is written, so who and where are read when it is read**
(OBT-559, closing OBT-556's first item). An urgent need's body used to name the place — the truth,
for a cleared project — and the panel answered the row as it was written: to a coordinator who
had since left the region, and about a project flagged since. Now the four project writers stage
facts beside the row, in `shema_project_notices`, and none of them is a name or a place; the panel
answers the five project kinds (stale included) with an empty `title` and `body` and reads off the
project, at read time: the language's name as every recipient may read it (`""` for a withheld
project — `language_name_for(project, ShemaReader.OTHER, fallback="")` once OBT-560 lands), the
region key, and — on an urgent need, and only for a reader who reaches the project now, by the
rule above — its place, as `ShemaNoticePlace`, a leaving shape built with no reader: `outside`,
so a withheld project's place is its region even for the coordination. A row written before
OBT-559 has no facts and answers its kind and nothing it said.

#### What BE-14 built — the export and the import

**The export is this section's rules at the one boundary where nothing is governed afterwards**
([OBT-403](https://linear.app/shema-obt/issue/OBT-403)). `GET /api/shema/export/projects` is one
code path through the filters every read already uses, never a payload assembled from rows: the
caller's scope through `list_projects` (the listing's own query), each row validated into
`ExportedProject` — FE-44 §8.4's allowlist of 24 keys, a `LeavingShape` built **for nobody**, so
`outside` — the prayer requests as `_consent.authorized_requests_by_project` answers them, and the
notes asked of `can_export_notes` under `publico`, which says no. A column added to the table later
is out of the file until somebody declares it on the shape. A sensitive project leaves with its
region key where the place was, an empty base and `locationWithheld: true` **whoever exports** —
the region's own coordinator included, because a file is what leaves.

**The route takes the caller's reader, and only to address the header.** How many places were
withheld is a line for coordination (GATE-04, 1.3) — `withheld_note`, told who the exporter is —
and every other reader, like a file with nothing withheld, gets no line at all. The header also
says what the file holds, when it was made and by whom, over which scope, that it is confidential,
and which log row it is. `READER_ROUTES` lists the route with that argument, and
`export_projects.py` calls no `read_by`, which the tree test holds.

**Every file is logged before it is handed back**, in `shema_exports` (append-only, the trigger
`shema_eten_reports` uses): who, when, the scope (`RegionScope.key`, the spelling
`shema_eten_reports` files a scope under too, so the two logs join), the format, how many rows
and how many withheld, and the ids of the projects and the prayer requests that went out — never
text, so a withdrawn request does not outlive its withdrawal in a table nobody can edit.

**Formats: `json` and `csv`, and that is a departure to record.** FE-44 §9.12 freezes
`format=json|csv`; on 28/aug/2026 the client answered PDF, a spreadsheet and a text document. The
CSV is the spreadsheet — BOM, `;`, every formula lead neutralised, as the console's own export —
and PDF and a text document are not built: each needs a renderer this repository does not carry
and a layout somebody has to review. The contract lives in the PME and is not edited from here;
the difference is recorded in this paragraph and in the pull request until one of the two changes.
The words of the header are the console's catalogue values copied into
`app/models/shema_transfer.py`; the cells are data — ISO days, FE-44's vocabulary values, the
region key where a place is withheld.

**A large export is not a job to poll.** The file is the collection `GET /api/shema/projects`
already answers in one request, read in three statements whatever its size
(`test_the_export_does_not_grow_its_queries_with_the_collection`), and the part that grows — a row
validated and written per project — runs in a worker thread. Measured on 30/sep/2026 on SQLite,
with the machine shared by four other runs: 127 projects in 46–131 ms; 2,000 in 0.33–0.68 s at the
best of three and up to 1.5 s at the worst, where the Projetos read of the same 2,000 took 0.59 s.

**Only coordination imports, and that is a decision to record.** A
`coordinator` in its regions, the `admin` role and an installation admin import; the OBT Lab and the Resource Circle
are answered 403 before the file is looked at (`readership.coordinates_anything`, the same answer
the export's withheld line is addressed by). The import is the backup that returns, and only
coordination reads a whole record: any other reader reads a sensitive place as its region, may
not write any project's place, flag or reason (OBT-528) and, outside the prayer audience, reads an
unauthorized request as `""` (BE-09) — so a file they hold restores nothing, and applied it would
be refused field by field or write a reduction over the truth. FE-44 §9.12 does not say who
imports and the console's header shows the button to every role: the contract and INT-11 are the
PME's to align.

**The import is the inverse risk, and it gets the write's rules, not a second set.**
`POST /api/shema/import/projects` reads the raw body, so the console's five refusal keys
(`import_invalid_json`, `import_is_export`, `import_not_list`, `import_bad_record` with the 1-based
index, `import_duplicate_id`) are the server's too. The exported file is recognised by what it
holds — the wrapper, any row of it, any payload read for somebody other than coordination (its
`readAs`, or a withheld place without one), the CSV by the sentence it opens with. Reading and
validating the file runs in a worker thread, as the export's rows do. Every record is validated
by `ShemaProjectCreate` before the database is read, and then applied through `create_project`
(an id the caller's scope does not hold) or `save_project` at the current version (one it does),
both with `commit=False`, and committed once: a refusal on the tenth record takes the first nine
with it, and answers as the write path answered it, item named — a record saved by somebody else
meanwhile is the record screen's own 409, with who changed what. So the region scope, the reader's fields
(OBT-528), the prayer request's reader (BE-09), the trail and the notices are a typed save's —
and so is the cost, about six statements a record (763 for 127 records, 3–4 s on SQLite here),
paid inside one transaction, which is the price of one write path. Nothing is deleted: a
project the file does not name is left alone.

**Nothing in a file authorizes anything.** `prayerVisibility`, the recording and a need's
`prayerShared` and `acknowledged` are dropped before validation; an imported request arrives as
the write leaves any request whose authorization was not restated — a new or changed text
unauthorized, an unchanged one as the organisation left it — and the file can neither publish nor
withdraw one. **The sensitive flag moves one way**: a file may raise it and may not clear it on a
withheld record (`_redaction.never_lowered`), BE-16's rule for the Notion import, because a backup
taken before a project was flagged would otherwise publish its place by momentum. What the server
writes from something else — the health projection, the progress history, media, materials,
`derived`, `readAs`, `locationWithheld`, `completedDate`, the org chart's three names — is dropped
too, and `ignoredFields` in the answer names every key that was, so an import is never read as
having restored what it could not.

**A project pending confirmation (§6.11) is in neither direction**, and neither file adds a filter
for it: the export starts at `list_projects`, the import reads what it may update through
`visible_projects`, and both compose `_scope.registered` by starting where every reader starts. The
file never carries it, its request or its id in `shema_exports`; an import naming its id is refused
409 by the create, nothing applied — confirming or correcting it is the Admin's act on the project
(`test_a_pending_project_never_reaches_the_file`, `test_the_import_cannot_reach_a_pending_project`).

**Residuals, named.** ~~A slug that exists outside the caller's reach is answered 409 by
`create_project`, the existence oracle `POST /projects` already has; the import inherits it by
being the same path.~~ **Closed by OBT-551 (1/out/2026, Daniel), and the id stopped naming a place altogether with OBT-552:** a new record's id is a minted
UUID, and a slug is refused before anything is read with one fixed sentence, so neither the create
nor the import can tell a slug that exists elsewhere from one that never did (§5.1). The free text of an authorized request and the vitality
can still name a place — this section's residuals. ~~The language name~~ **closed by OBT-560 (2/out/2026):**
a sensitive project's language name can name the place (*Sa'di of High Egypt*), and Karina, via
Daniel, 1/out/2026, chose *"um nome alternativo, cadastrado pela coordenação"*. That much is hers.
`shema_projects.public_language_name` holds it, written by coordination alone
(`COORDINATION_WRITES`) and read by `_redaction.py` alone (`REDACTION_COLUMNS`); `LeavingShape`
replaces `language_name`/`language` with it for every reader but coordination, beside the place,
and says so in `languageNameWithheld`. **Ours, not hers:** while none is registered the **region
key** stands in, as it does for `location` — fail closed; a notice says *a project* and the Pulse
*Projeto sensível* instead of the key (OBT-562 extended it to the stale and urgent-need bodies through
`LeavingShape.spoken_name`); the search finds the card by the name the reader reads;
and the Pulse inbox and the two notices — paths that are not shapes — take the same rule through
`language_name_for`. `tests/test_shema/test_language_name.py` sweeps every leaving shape that
declares a name, found by walking the subclasses. ~~**Left named:** the collection and the ETEN
report still **order** by the real name, so a reader could infer a little from a card's position.~~
**Closed by OBT-563 (Daniel, 2/out/2026 — ours, not Karina's):** `list_projects` orders by the
opaque id, so the rows arrive saying nothing; the Projetos screen orders its cards by the name each
card carries before its stable sorts run, so a tie falls where the reader's name puts it; and the
export orders its rows by `language_name_for(project, OUTSIDE)`, the name it prints. The ETEN report
already ordered by its redacted line and only gained the test. `ix_shema_projects_language_name`
no longer serves the collection read. `tests/test_shema/test_name_order.py` puts a project whose
real name sorts first and public name last before OBT Lab, and it was seen to fail against the
previous order on the screen and in the export. **Still left named:**
`ProjectRef` (a member's own projects) and the intake form behind a leader's link print the real
name, because their reader is the team — the form declares it in `IntakeForm._withhold_name`. The header's language reuses BE-09's
`PulseLanguage`, which is the console's two locales under a name that says *Pulse*.

### 6.5 Seam D — the derivations must match, not merely agree — **Decided**

FE-44 §7 pins nine derivations over all 127 records at `2026-05-14` in
`src/utils/__tests__/dataJsParity.json`. **A server that computes them differently is wrong,
not different.**

- They live in `app/utils/shema_derivations.py` (§3.1), as pure functions of
  `(record, now)` with `now` injected.
- **`dataJsParity.json` is vendored** into `tests/test_shema/` and a test replays it. This is
  the sibling's vendored-emission precedent (`app/utils/resource_request_vocabularies.json`,
  copied byte for byte with a CI check against its source), applied to an acceptance artifact
  instead of a vocabulary. BE-05 owns the vendoring; every issue that implements a derivation
  extends the replay.
- **Two of the nine are timezone traps and both are already documented failures on the
  frontend.** The year boundary is read **from the ISO date by field**, never through a
  `Date` (FE-44 §7.8 — it is what makes the ETEN year correct). And the progress stamp is
  the **actor's local day**, not a UTC day: in UTC−3 a save after 21:00 lands on tomorrow,
  and on 31 December in the next *year*. `app/utils/stored_time.py` already exists in this
  repository and BE-05 reads it before writing a second clock helper.

#### What BE-05 built, and the two places it departs from this document

**One — the collection read takes the filter and the counts together, so its response is an
envelope and not `Project[]`.** §9.1 of the frozen contract froze `GET /api/shema/projects` as
the whole scoped collection with no pagination, no filter parameters and no facet counts, and
BE-01's note on OBT-394 read that as *serve the scoped collection and do not build a second
facet engine*. BE-05 read it the other way, and the argument is §9.1's own escape clause:

> past roughly 2,000 projects, or when a role's scope stops being expressible as "these
> regions" […] the server takes the filter **and** the counts together, in one endpoint, never
> the filter alone — a filtered list with client-computed counts is the defect this note exists
> to prevent.

The defect §9.1 guards against is a **second owner** of the counting rule. Refusing the DoD
does not avoid it: the DoD's third line already makes the server the owner of status, health
and staleness, and §6.5 already demands those match exactly. With the derivations on both
sides, the counting rule is the half that remains, and *one endpoint that answers both* is the
shape §9.1 itself blesses for that case. So it is built now rather than at the two-thousandth
project, with the property held by the return type: `counts` is not optional, no parameter
suppresses it, and a request with no parameters still answers the whole scoped collection —
§9.1's default, kept as the default. **What the contract owes in return is one edit: §9.1's
`-> Project[]` becomes `-> {items, counts, matched, total, limit, offset, sort,
locationsWithheld}`.** INT-02 reads `items` where it read the array.

**Two — the facet pass is a second file in `app/utils/`, not part of `shema_derivations.py`.**
§3.1 names one file. The nine derivations are FE-44 §7; the facet pass is §7.6, and it
*consumes* them. They have different lifetimes: `shema_facets.py` is the file the ~2,000-project
trigger replaces, and the derivations do not move when it does. Splitting them keeps that
replacement a single file with one import direction.

**And one thing that is not a departure, recorded because it looks like one.** The list item
inherits `LeavingShape`, so a card in a sensitive country carries its region where its country
would be (to every reader who is not coordination, since OBT-528 — §6.4) — against §9.1's *"`Project` carries the true `location`"*. That is **BE-04's decision
inherited**: `app/models/shema_privacy.py` names *the collection read* among the shapes that go
through the boundary, and `COORDINATION_PATHS` is empty with a comment saying the one line
expected in it is BE-06's record read. Following §9.1 here would mean adding this route to that
list, which is a line somebody has to justify — and the justification does not exist, because
the console draws cards and markers from the region anyway (`getLocationDisplay`,
`getMapPlacement`). The facets read the card rather than the row, so a count cannot name a place
the payload beside it withholds.

### 6.6 Seam E — the unauthenticated intake — **Decided**

`GET /api/shema/intake/{token}` and `POST /api/shema/intake/{token}` were the first routes in
this module with no `Authorization` requirement, by FE-44 §9.0; the intercessor's exit link
(OBT-531, §6.4) is the second pair and follows the same three rules:

- **The token is the whole guard**, so the guard is a **service function**
  (`verify_intake_token`) and not a router condition — the rule then holds for any future
  caller, which is the same argument §6.4 makes for the consent gate.
- **It grants the intake form and nothing else.** No console, no project data, and it
  expires. It is not a session and it mints no token pair.
- The token is stored **hashed**, following every other token in this repository —
  `refresh_tokens`, `password_reset_tokens` and `access_invites` all store a `String(64)`
  `token_hash` and let the raw value leave only once.

> **BE-12 ([OBT-401](https://linear.app/shema-obt/issue/OBT-401)) built this seam, and five
> decisions travel with it.** All three rules above held; what follows is what they did not
> cover, because the section was written about the guard and these are about what the guard
> lets through.
>
> - **`POST /api/shema/intake/{token}` does not write `shema_projects`.** It archives, notifies
>   and answers `202`; a coordinator applies it through
>   `POST /api/shema/forms/submissions/{id}/import`. FE-44 §9.9 already spells the split —
>   `202` on this route and a `ReceivedSubmission` on the other — and the machinery agrees:
>   `save_project` takes an actor that `shema_record_edits` names and a version somebody read,
>   and a link has neither. Writing one would mean a nullable author in the trail or a
>   synthetic account, and `PULSE_LOOP`'s `import` step is the coordinator's in the console's
>   own constants. So the weakest credential in the system cannot move the numbers the ETEN
>   report is reconstructed from without a person who can be asked about it.
> - **The link pins the definition version it was minted with.** A leader opens the form,
>   drives out to where the team is and answers days later; a definition edited in that window
>   would otherwise reject an answer nobody gave wrongly. The client's `definitionVersion` is
>   checked *against the link* rather than used to select a form.
> - **Write-mostly is enforced by the `SELECT` list, not by the response model.**
>   `read_intake_form` reads one column — `shema_projects.language_name` — so there is nothing
>   else in memory for a later edit to reach for. The shape inherits `LeavingShape` anyway and
>   declares no place field, which is a choice rather than a requirement: the day somebody adds
>   `location` so the leader can confirm the project, the boundary is already underneath it.
> - **The definitions are stored and versioned, and the spec is authored in
>   `app/utils/shema_forms.py`.** A version is cut by content hash and never edited, because a
>   definition changed in place rewrites the meaning of every answer already given to it. The
>   spec lives in `app/utils/` for §3.1's stated reason and for one of its own: it holds the
>   mapping from a form field to a record column, three of which the consent gate guards, so
>   the ingest services name no guarded column at all and `test_privacy_owners.py` needs no
>   allowlist entry for this issue.
> - **`GET /api/shema/forms/submissions/{id}` serves an applied answer from the record and a
>   pending one from the archive.** An answer the import applies is readable on the record, under
>   the rules that surface enforces, so this read does not serve it — and that is only true once
>   the import has run. Between the `202` and the import an answer that maps to a column is on
>   **no** surface, which left a coordinator clicking *import* applying chapter counts and a
>   `prayerVisibility` they had never been shown, on the one route that decides whether a request
>   leaves coordination. The mapped answers are therefore served in exactly that gap and only to
>   the caller who closes it — `coordinator`, read as a value by `app/api/shema/_deps.py` from the
>   key the import route is guarded on — and the read goes narrow again once `appliedAt` is set.
>   Both edges matter: the archive is a second store of the guarded columns that §6.4's gate does
>   not reach into, so a `resourceCircle` account (the prayer wall's own audience) never reads a
>   request out of it, and a withdrawn prayer request does not stay readable one route over after
>   the record has erased it.
> - **A withdrawn request leaves the archive too** (OBT-561, 2/out/2026, Levi — Karina's answer of
>   1/out/2026). The withdrawal that took it off the wall takes it, and the visibility answer
>   that authorized it, out of every archived Pulse of the project that shared one, in the same
>   transaction: an applied Pulse no longer holds it, and a pending one, applied later, neither
>   writes an empty request over the record's nor authorizes the text again. `archived_payload`
>   is therefore verbatim **except** for that removal, and `content_hash` keeps the hash of the
>   bytes as they arrived. §5.6 holds the rule.
>
> **Not built, and it is GATE-03's:** `POST /api/shema/forms/pulse/{projectId}`, the generated
> artifact. §9.3's own list — the format, which of two is authoritative, the distribution model
> and withdrawal from an already-distributed file — is untouched by anything above.

### 6.7 Link tokens — one module, a table per purpose — **Decided**

BE-20 ([OBT-525](https://linear.app/shema-obt/issue/OBT-525)) built this. Before it, three
tokens were written three ways — the leader link with `token_urlsafe(32)`, the access invite
and the password reset with `token_hex(32)` — each deciding its own states, and the access work
of [OBT-522](https://linear.app/shema-obt/issue/OBT-522) adds four more: the handoff code, the
endorsement link, the external request link and the intercessor's exit link. A token that
reinvents its hash and its states is how one of them ends up with no expiry.

- **One module: `app/services/common/tokens/`.** `mint` (`token_urlsafe(32)` and its digest),
  `digest` (SHA-256, the value every token row in this repository already stores), `status`,
  `expiry` and `mint_code`. It lives in `app/services/common/` and not in this module's service
  package because its callers are three modules — the auth core, resource requests and Shemá.
- **What is shared is the function, not the row. There is no generic token table.** Each
  purpose keeps its own table with a real foreign key — `shema_intake_links.project_id`,
  `access_invites.role_id`, and one per new token — because each token points at something
  different and *used* means something different in each: the first answer on a multi-use link,
  the acceptance of an invite, the spend of a handoff code. A table keyed by a kind and a target
  id would trade every one of those keys for a string the database cannot check.
- **The raw value leaves once**, in the response that creates the row. `mint` and `mint_code`
  return it beside its digest; only the digest reaches a column. §6.6's third rule, now held in
  one place.
- **One order of states: `revoked > expired > used > pending`**, the leader link's. Revoked
  first, so a link taken back never reads as one that merely ran out; expired before used,
  because on a multi-use link `used_at` records the first answer and not the end of the link.
  `status` reads a row with `expires_at`, `revoked_at` and `used_at`, and **`expires_at` is not
  optional** — a token with no expiry has no state there.
- **Each purpose's ceiling is a key in `app/core/config.py`, one per purpose**, read by the
  service that mints the token and passed to `expiry`; the module reads no configuration. The
  leader link's is `shema_intake_link_max_days` (90). Its default of 45 days stays in
  `_intake_tokens.py` — a product fact tied to the Pulse's monthly cycle — and a ceiling set
  below it shortens it rather than refusing the coordinator who stated nothing.
- **A six-digit code's digest is not what protects it.** A million values is brute-forced
  offline in no time; what protects a live code is its short life and the attempt limit, and
  the limit is a column of the table that uses the code — the trade
  `app/services/device/claim_code.py` already records for the Room.

**What moved, and what stays.** The leader link moved: `_intake_tokens.py` mints, looks up and
reads state through the module, and `tests/test_shema/` passed unedited. **The intercessor's
exit link was born on it** (OBT-531): `leave_intercessor.py` mints and digests, `_directory.py`
stores and reads the digest, and a link that is never revoked nor used-and-kept is shown to
`status` with those two stated as `None` rather than as two columns nothing writes. Four stay where they
are:

- **The access invite** (BE-17, `create_invite.py`, `accept_invite.py`, `_invite_status.py`)
  stays for later. [OBT-543](https://linear.app/shema-obt/issue/OBT-543) changes
  `AccessInvite` and `accept_invite.py` in the same wave, and moving it here would collide for
  no gain. Nor is it a mechanical swap: the invite reads `used` **before** `expired` — an
  accepted invite whose clock later ran out still reads as accepted in the admin's list — and
  its column is `accepted_at`, which `status` does not read. Whoever moves it decides that
  order first; the digest is already the same, so a live invite would keep working.
- **The password reset** belongs to the platform's auth core, outside this module.
- **Refresh tokens** — their rotation is INT-01's open item.
- **The Room's device claim code and credential** (`app/services/device/`) are not links and
  have a lifecycle of their own.

### 6.8 Seam F — the PME's door: one session over two apps' roles — **Decided; OBT-523**

OBT-522 (22 and 25/sep) put the mesa, the Gestor and the Admin inside the PME: *"todos da mesa
vão ter conta no PME com a função já definida"*. Their grants live in `resource-request-form`,
and the session route sat under `authenticated`, whose gate is `require_app_access("shema")`:
the mesa was refused at the door of a console it now belongs to. Six rules.

- **The session answers every role, and `role` is transitional.** `roles` is every key of
  `ROLE_PRECEDENCE` the account holds, in that order; `role` is its first entry, kept so no
  screen that reads one role breaks while the console moves to the list. The four Shemá roles
  lead the precedence, widest-first as before, so every account that reached the console
  before keeps its `role` byte for byte (an account holding `coordinator`, `admin` and `gestor`
  answers `coordinator`; the Admin of that day held `globalStrategist` first, until OBT-572); then `admin`, `gestor`, `mesa`, and the
  reserved `equipe`. The console's `SESSION_ROLES` is this tuple and refuses any key outside it,
  so the list is closed: a key added here is a key added there.
- **The door is a router of its own and opens one route.** `door` carries `DOOR` and holds
  `GET /session`; everything else stays under `authenticated`. *(OBT-524 added the member's two
  reads behind it, and made the pin `DOOR_ROUTES`, by method and path — §6.9; OBT-541 added the
  notification panel and its read mark.)* An account the form made gets its
  session and is refused by every other route — what each area shows it is OBT-544's.
  `tests/test_shema/test_access.py` pins the door's paths in `DOOR_PATHS`, so the next door
  route (OBT-524's `/me/projects`, for a member with no regional role) is a deliberate edit.
- **Who passes: at least one role of the vocabulary, counted per app.** From `shema`, the four
  and `admin`; from `resource-request-form`, `gestor` and `mesa`. **Not** the form's `equipe`
  — `auto_approve` hands it to everybody who registers there, and OBT-524 turns it into a
  project membership (§6.9: a live membership is the session's `equipe`) — nor `lider`, who has no account since 22/sep, nor the form's `admin` row:
  every guard below the door reads the `shema` grant, and a session answering *admin* off the
  form's row would name a power every admin route refuses. One `list_roles` read answers the
  door and the body (`_scope.session_roles`), so the two cannot disagree. An installation admin
  passes, as everywhere, and is answered the roles it actually holds.
- **`admin` is one role for two apps, and it is not the installation's admin.** Seeded in both
  by `20260927_shema08` and by `scripts/seed_apps_roles.py` under *"Admin da plataforma"*;
  OBT-543 grants it, in both apps (§6.10). `AdminUser` guards on it for OBT-524 and OBT-543.
- **Seeding it in the form closed a door there, and the door has since left.** The form's two
  access doors (`app/services/resource_request_access/`) granted any role the app had, and a
  Gestor could have named an Admin, who then passes `assert_can_manage_roles` and revokes
  through `/api/roles`; only an installation admin could name `admin` through them. OBT-549
  (FE-56, 30/sep/2026) retired both doors with the form's access screen. The concession lives
  in the PME since OBT-543 (§6.10), which also closed `/api/roles` to the two apps for everyone
  else.
- **`admin`, `gestor` and `mesa` reach no region** — §6.1's last paragraph.

**Left to others, and named so nobody assumes them done.** ~~OBT-543: granting `admin` should
grant it in both apps, and an `admin` held in the form passes `assert_can_manage_roles` there
without the form's mesa × Gestor exclusion.~~ **Closed by OBT-543** (§6.10): the grant writes
both rows, and `/api/roles/assign` and `/revoke` refuse the two apps to anyone but an
installation admin. The form's owner:
`admin` holds no capability in the form's table, and the form's `reach()` counts it as a fifth
role — the whole board. OBT-544: until its console half lands, an account at the door with no
Shemá role is refused by every other route the console calls, `/regions` on sign-in included. The
server's half is this module's — the session answers `apps` (§6.3). The console's half is the PME's
[project-management-ecosystem#70](https://github.com/shemaobt/project-management-ecosystem/pull/70):
once it merges, an account holding no Shemá grant stops reading `/regions` on sign-in, and one
holding only `gestor`/`mesa` sees the topbar and the *Resource Circle* entry and none of the six
areas. The server refuses those areas exactly as before either way.

### 6.9 Seam G — the member's reach: project membership — **Decided; OBT-524**

OBT-522 (22 and 25/sep) made *the team* the project's members in the PME rather than the free
text on the record (`team_leader`, `mentor`, `translators` stay, and the Notion export carries
them). `shema_project_members` is the link, and the form (OBT-520), *Solicitar recurso*
(OBT-544) and the Admin's access screen (OBT-546) read it. Seven rules.

- **Its own table, not `project_user_access`.** That table grants access to Tripod's `projects`
  rows, and a Shemá project is not one (§4.3).
- **One live row per account and project; removal marks.** The partial unique index is on the
  live rows, declared on the model for both dialects (the suite builds from `create_all`) and in
  `20260927_shema524` for PostgreSQL. `DELETE` writes `removed_at`/`removed_by`: a request a
  member sent stays the project's after they leave, so the stay is kept. Coming back is a new
  row. `added_by`/`removed_by` are `SET NULL`, the platform grant's shape — `RESTRICT` would make
  deleting the Admin, who writes every membership, fail.
- **Only the Admin writes** — `POST` and `DELETE` sit under `authenticated` with `AdminUser`
  (the `shema` grant). The regional coordination does not add members (*"por enquanto não"* —
  Karina, 25/sep). A duplicate live membership is a 409 and an unknown account a 422.
- **A live membership is the session's `equipe`.** `_scope.session_roles` adds it after reading
  the grants, so a member holding no role anywhere passes the door (§6.8). The form's own
  `equipe` grant still does not: only the PME's link counts.
- **The door holds the member's two reads**: `GET /projects/{id}/members` and `GET /me/projects`.
  `tests/test_shema/test_access.py` pins them in `DOOR_ROUTES`, by method and path, because the
  Admin's `POST` shares the roster's path behind the app gate. **OBT-541 added the notification
  panel and its read mark** (`GET /notifications`, `POST /notifications/read`): the form's
  notices are addressed to the Gestor and to whoever started a request, accounts only the door
  admits. Their scope is `DoorScope` — `scope_from_roles` over the session's roles, which reaches
  no region without a regional role — so such an account reads its own rows and no stale
  reading. The preferences stay behind the app gate.
- **Three readers of a roster, and a type of their own.** The project's region scope, its own
  live members, and the Admin — who reaches every roster because it writes them and holds no
  region (§6.8). `_scope.roster_projects` is the statement and `RosterReach` its input: not a
  `RegionScope`, so the Admin's reach over rosters cannot be handed to the collection or the
  record, and mypy says so. Anybody else gets the §6.1 answer, a 404 indistinguishable from a
  project that does not exist.
- **A membership is not a region.** `visible_projects` does not read it: a member reaches their
  projects' refs (`/me/projects`, `_scope.member_projects`) and rosters, and no other project.
  What else a member sees of their own project — the record included — was left to OBT-544,
  and composing `member_projects` is how it would. **Still open**: OBT-544 kept this module to
  the session's `apps`, so a member holding no regional role reads the project's request cards
  (`GET /api/resource-requests/projects/{id}/requests`) and not its record.

**A coordination surface that redacts nothing.** The roster names people, not places: a member of a
project in a sensitive country is named on it, to the people who reach that project. `name` is the
display name, else the e-mail (`_audit.author_name`), so an address can appear there — the
`CONTACT_FIELDS` of §6.4 guard a project's contacts on shapes that leave, and this shape does not
leave. No export reads the table until BE-14 decides. **`/me/projects` answers 403, not `[]`**, to
an account holding no role of the door's vocabulary and no live membership: the door refuses it
before the service runs.

### 6.10 Seam H — the Admin grants: one surface for two apps' roles — **Decided; OBT-543**

OBT-522 (Daniel, 23 and 25/sep): **only the Admin concedes and revokes, in both apps**, from one
screen in the PME (OBT-546) instead of the form's `/access`. This is that screen's server: seven
routes under `/api/shema/access`, all behind `AdminUser`, composing what existed —
`assign_role`, `revoke_role`, `set_region_scope` and the form's invite module — rather than a
second copy of any of it. `app/services/shema/_grant_rules.py` owns every rule below that is a
question of *what*; `AdminUser` and a fresh read of `assert_can_manage_roles` answer *who*.

**The routes.** Request and response keys are camelCase; the form's own routes, which the PME's
`/convite` page also calls, stay snake_case and are quoted as they are.

| Route | Body / query | Answers |
|---|---|---|
| `GET /access/people?email=` | exact e-mail, case aside | `AccountGrants` — `{userId, email, displayName, isActive, apps: [{appKey, roles[]}], regions: [{regionKey, grantedBy, grantedAt}], regionScope}` |
| `POST /access/grants` | `{userId, appKey, roleKey, regionKeys?}` | `AccountGrants`, as the account now stands |
| `POST /access/grants/revoke` | `{userId, appKey, roleKey}` | `AccountGrants` |
| `POST /access/invites` | `{email, appKey, roleKey, regionKeys?}` | 201 `{id, email, appKey, roleKey, regionKeys, status, createdAt, expiresAt, createdBy, inviteUrl, emailSent}` — the link once |
| `POST /access/invites/revoke` | `{inviteId}` | the invite, `status: "revoked"`; repeating is a no-op |
| `GET /access/invites` | — | the two apps' invites nobody accepted, newest first, at most 200 |
| `GET /access/changes` | — | `[{action: granted\|revoked, at, appKey, roleKey\|null, regionKey\|null, userId, userEmail, userName, actorId, actorEmail, actorName}]`, newest first, at most 200 |
| `GET /api/resource-requests/access/invites/{token}` | anonymous | `{status, email, app_name, role_key, role_label, account_exists, region_keys}` |
| `POST /api/resource-requests/access/invites/{token}/accept` | signed in, same e-mail | `{user_id, role_key, granted_at, granted_by, revoked_at, revoked_by}` |

**The rules.**

- **What is granted is the PME's own vocabulary.** From `shema`: the four and `admin`
  (`SHEMA_APP_ROLES`); from the form: `admin`, `gestor`, `mesa`. `equipe` is refused by name —
  a project membership since OBT-524 — and so is `lider`, who has no account since 22/sep.
- **`admin` is one role for two apps**: granting or revoking it under either `appKey` writes
  or revokes the row in both. The door reads the `shema` row; the form's guards read theirs,
  and its `reach()` gives any role but `equipe`/`lider` the whole board — so every Admin sees the
  form's board, which is OBT-522's *faz tudo exceto endossar*.
- **A regional role (`coordinator`, `obtLab`, `resourceCircle`) comes with at least one region,
  in the same call**, and `regionKeys` is **the account's whole scope**, because the table is
  per account: re-granting a held regional role is how regions are edited, and the screen
  pre-fills the current ones. Any other role touches no region — `regionKeys: []` beside it
  is *leave them*, never *reach nothing*. **Revoking the last regional role clears the rows**, so
  a later grant through a door that states no region (an approved access request) cannot bring
  an old scope back.
- **Nobody grants, revokes or invites themselves**, and **mesa and Gestor never share an
  account** — `_rules.assert_role_compatible`, the form's own rule and its one owner.
- **Every refusal comes before the first write**, and the writes are one commit: the role in
  each app, the close of any invite still pending for the same e-mail, app and role, and the
  regions. The account written to is locked `FOR UPDATE`, which serializes two acts on one
  person on PostgreSQL (SQLite ignores it).
- **The Admin's standing is read fresh** on every write — `AdminUser` answers from a
  thirty-second cache per process — and an Admin holding the role in one app only is refused
  with a sentence that says so.

**Invitations.** For somebody with no account. The link is always the PME's,
`{shema app_url}/convite?token=…`, whatever app the role lives in — the form has no sign-in
since 22/sep — and the letter is BE-12's `access_invite` template under the PME's name, sent
after the row is committed; `emailSent` says whether it left. **`admin` is never granted by
link**: a link can be forwarded, and signing up proves nothing about the e-mail. The regions of
a regional invite are stored on it (`access_invites.region_keys`) and applied on acceptance, in
the commit that grants the role and spends the invite, with the inviter as their author —
**unless the account already holds a regional role and a different scope**: a week-old link does
not rewrite a newer decision (409), and the Admin grants directly. A direct grant or revocation
closes pending invites for the same thing.

**Acceptance stays on the form's routes** for now — they are generic by token — so no new
public route enters this module. **OBT-549 must move, not delete**, before those routes answer
404: the lookup and the acceptance, `accept_invite`, `describe_invite`, `invite_store` and
`_rules.assert_role_compatible`.

**The history.** Roles come from `user_app_roles` through the auth spine
(`list_grant_history`): a grant carries `granted_by`/`granted_at` and a revocation
`revoked_by`/`revoked_at` — which `revoke_role` records since this issue — so every door that
writes a role is in it, an accepted invite reading as the inviter's grant. Regions come from
**`shema_scope_changes`**, the append-only trail `set_region_scope` writes on every change,
because moving somebody between regions writes no role row at all. It has **no foreign key**:
`SET NULL` is an UPDATE and `CASCADE` a DELETE, and its trigger refuses both. Only the roles the
surface writes are read — the form's automatic `equipe` is nobody's decision. What it cannot
say: a deleted account takes its role rows with it while its region rows stay under an id with
no name; a deleted author is anonymised; `admin` reads twice, one row per app; nothing of the
region half predates OBT-543.

**Refusals**, for the screen to render — status, `code`, the server's sentence:

| When | Status · `code` | `detail` |
|---|---|---|
| no Shemá role at all (a Gestor, a mesa) | 403 · `FORBIDDEN` | `You don't have access to the 'shema' application. Please contact support to request access.` |
| a Shemá role that is not `admin` | 403 · `FORBIDDEN` | `Role 'admin' is required for this action.` |
| the Admin holds the role in one app only | 403 · `FORBIDDEN` | `The admin role is not held in '<app>'. Granting the Admin writes it in both apps; an installation admin can grant it again to repair this account.` |
| `equipe` | 422 · `UNPROCESSABLE_VALUE` | `'equipe' is a project membership, added on the project, not a role granted here.` |
| any other role or app outside the vocabulary | 422 · `UNPROCESSABLE_VALUE` | `'<role>' is not a role granted here for '<app>'.` |
| a regional role with no region | 422 · `UNPROCESSABLE_VALUE` | `'<role>' is a regional role: grant it with at least one region.` |
| regions beside any other role | 422 · `UNPROCESSABLE_VALUE` | `Regions go with a regional role only; '<role>' is not one.` |
| `admin` by invitation | 422 · `UNPROCESSABLE_VALUE` | `The admin role is granted to an existing account, never through a link.` |
| an id that is no account | 422 · `UNKNOWN_REFERENCE` | `Target user not found.` |
| granting, revoking, inviting yourself | 400 · `BAD_REQUEST` | `You cannot grant a role to yourself.` · `You cannot revoke your own role.` · `You cannot invite yourself.` |
| revoking a role the account does not hold | 400 · `BAD_REQUEST` | `Active assignment not found` |
| mesa to a Gestor, or Gestor to a mesa | 409 · `CONFLICT` | `'mesa' and 'gestor' are mutually exclusive: revoke 'gestor' before granting 'mesa'.` (and the converse) |
| a second pending invite for the same e-mail, app and role | 409 · `CONFLICT` | `An invitation for this e-mail and role is already pending.` |
| recalling an accepted invite | 409 · `CONFLICT` | `This invitation was already accepted; revoke the granted role instead.` |
| no account for that e-mail · no such invite (or another app's) | 404 · `NOT_FOUND` | `No account with this e-mail.` · `Invitation not found.` |
| accepting would change an existing regional scope | 409 · `CONFLICT` | `This account already has a region scope, and accepting this invitation would change it. The Admin grants the role directly instead.` |
| a malformed body — an unknown region key, a bad e-mail, an unknown field | 422, no `code` | FastAPI's field errors |

Accepting keeps the form's own refusals: revoked, used and expired are 409, another e-mail is
403.

**`/api/roles`.** `/assign` and `/revoke` answer 403 `Roles of '<app>' are granted and revoked
through /api/shema/access.` for the two apps to anyone but an installation admin. `/check` did
not change: `dev` has required the app's `admin` or an installation admin to ask about somebody
else since OBT-506 (`9fb3129f`, 20/sep — the issue measured `main`), and asking about yourself
reveals nothing `/api/auth/my-roles` does not.

**Residuals, named.** Until OBT-549, the Gestor still concedes through the form's door, and an
installation admin can still invite `admin` there — that acceptance writes the form's row only.
The account lookup does not list project memberships, which are OBT-524's table.

### 6.11 Seam I — the project the mesa's approval files, and the Admin's conference — **Decided; OBT-547**

Karina, 25/sep: *"se o projeto for aprovado pela mesa ele é cadastrado sim, os membros também"*;
Daniel, 25/sep: *"sim, o admin confere antes"*. A team outside the PME asks through the Admin's
request link (`docs/resource_requests.md` §5.4.5); when the mesa approves such a request, the PME
gains a project **pending confirmation**, and the Admin confirms or discards it. Seven rules.

- **The approval files it, in the decision's transaction.** `save_evaluation` calls
  `create_pending_project_from_request` when it records `approved` on a request with a
  `request_link_id` and no `shema_project_id` — beside the ledger movement and the notices, under
  the same commit. `conditional` files nothing: it is not `approved` and moves no money. The call
  hands values over — the snapshot the mesa evaluated, the request's id, the link's id — and this
  module imports nothing of the form's services (`_request_notices.py`'s reason).
- **What the form carries becomes the project, and nothing else does** (`_filing.part_a`). The
  language's name and code (A1: `lang_name`/`lang_iso`, or the first row of the slim variant's
  table; the registered name, A0, when nobody typed a language), the place (A2's
  `people_location`, or A1's `tr_location`), `status = planejado`, `sensitive_country = false`
  and the region derived by `_redaction.derive_region`. The base (`team`) is empty: the form asks
  none. The id is a UUID, as the console mints for a record born in the product. The people it
  proposes are `shema_project_pending_members` — the A4's name and role, **with no e-mail**, and
  the link's own address under the requester's name (`tpp_name`).
- **Idempotent by request and by link.** A request that filed a project files nothing again; a
  link with a live project — pending or confirmed, not discarded — files nothing either: one team,
  one project. A request approved after its link's project was confirmed is stamped with it at the
  approval; while the project is pending, the confirmation stamps every request of the link.
  `uq_shema_projects_source_request` and the partial `uq_shema_projects_live_source_link` hold both
  rules against a race. **Neither source is a foreign key**: `rr_requests.shema_project_id` points
  back, and a pair naming each other could be deleted in no order.
- **Nobody reads a pending project through the scope — the Admin and an installation admin
  included.** `_scope.registered` is composed into `within_scope`, `member_projects` and
  `roster_projects`, so the collection, the counts, the record, the needs, the ETEN report, the
  notification panel, the rosters and any export that starts where every reader starts (OBT-403)
  cannot see one. The Atlas shows a project once it is confirmed. The Admin reads pending ones
  only through `_scope.pending_projects`, a statement of its own that no reader of the collection
  composes, and decides them through `_scope.filed_projects`.
- **Only the Admin reads and decides**, behind `AdminUser`, with the standing read fresh on each
  act (`_grant_rules.require_admin_in`). The list is built for the Admin's reader
  (`readership`): the place as typed, by `COORDINATION_EVERYWHERE` (§6.4).
- **Confirming** applies the Admin's adjustments and the flag — `sensitiveCountry` has no default
  in the body, so a client that forgets it is refused rather than read as *not sensitive*; a
  `languageCode`, `location` or `team` left out keeps what was filed (`model_fields_set`, as the
  record's save reads it), since a blank place would derive the region to `other` —
  re-derives the region, clears `pending_confirmation`, writes the trail under the Admin's name
  (version one: nobody could have read the record before), and stamps `shema_project_id` on every
  request of the link that has none. Each address on the list: an account (by e-mail, case aside)
  joins the team as OBT-524's membership, with the Admin as `added_by`; an address with no account
  is **invited to the team** — BE-22's `access_invites` row naming `project_id` and **no role**
  (`role_id` is nullable under `ck_access_invites_role_or_project`), read as `equipe` wherever a
  role would be, listed in `GET /access/invites` with `projectId`, recallable there, its link to
  the PME's `/convite` and its letter after the commit. Accepting it is the membership
  (`apply_invited_membership`); already a member is not a refusal. A blank address is left out and
  named back in `withoutEmail`; the same address twice is one person.
- **Discarding** marks and never deletes — `discarded_at`, `discarded_by` and a required reason —
  keeps the project out of every read, frees its link for a later approval, and leaves the request
  exactly as it was: approved, with no project. The answer says so.

**The routes.** Request and response keys are camelCase.

| Route | Body | Answers |
|---|---|---|
| `GET /pending-projects` | — | `[{id, languageName, languageCode, location, team, requestId, requestName, filedAt, members: [{name, role, email}], locationWithheld}]`, oldest first, `Cache-Control: private, no-store` |
| `POST /projects/{id}/confirm` | `{languageName, languageCode?, location?, team?, sensitiveCountry, members?: [{name?, email?}]}` | `{id, languageName, requestIds, joined: [{email, userId}], invited: [{email, inviteId, inviteUrl, emailSent}], withoutEmail}` — each link once |
| `POST /projects/{id}/reject` | `{reason}` | `{id, reason, discardedAt, requestId, requestProjectId: null, detail}` |

The list is not `/projects/pending`: the record's `GET /projects/{project_id}` is included before
this router and would take `pending` for an id.

**Refusals.** Any Shemá role but `admin`: 403, `Role 'admin' is required for this action.` The
mesa and the Gestor: 403 at the app gate. An id no approval filed: 404 `Project not found`. A
project already decided: 409 — `This project was already confirmed.` or `This project was
discarded; it is not confirmed or discarded again.` A body without `sensitiveCountry`, a blank
reason, a malformed address: 422, FastAPI's field errors.

**Open, and named.** GATE §9.5's fail-closed rule — *an unrecognised country is sensitive until
confirmed* — is the seed's; a project filed by an approval is born not sensitive because the issue
says so, and the Admin decides at the conference. Whether the client wants the seed's rule here
too is a question for Karina. The request link stays valid after its project is confirmed;
revoking it is the Admin's act.

---

## 7. Traps in this repository, for this module

[`docs/resource_requests.md`](resource_requests.md) §8 is the full list and is not repeated.
Three of its entries land differently here, and one is new.

### 7.1 The migration parent is read off `origin/dev`, at write time, every time

The sibling's §8.3 records a parent that moved **four times** while a stack sat in review, and
the failure is invisible where it is written: a stacked PR's CI runs against its own base,
where the single-head check is content, and the graph forks only when the branch reaches the
target. The head on this base, measured 11/sep/2026, is **`20260830_acc17`** — and that is a
measurement, not a value to copy into a file.

**The command is `uv run alembic heads` in your own worktree, immediately before writing the
revision**, and again at every merge of `dev` down the stack. Twelve issues in this module
author migrations in waves beside each other; whoever the user merges second re-points, and
the PR body is where that is written down so they know.

Naming follows the sibling's semantic form: `20260NNN_shemaNN_snake_description.py` with
`revision` equal to the prefix. `downgrade()` is not decorative — `migrations.yml` walks the
newest revision down and back up on a real PostgreSQL, and a migration that cannot come back
down fails CI.

### 7.2 No migration in this repository runs under SQLite, and none can

The sibling measured it: `alembic upgrade head` dies on the first revision, which creates
`users` with `server_default=sa.text("now()")`. The test suite builds its schema from
`Base.metadata.create_all` and never walks the graph. So **a dialect guard inside a migration
is dead code no test can reach** — write plain PostgreSQL. The split that *is* real lives in
the **models**, chosen at `after_create` from the dialect in hand.

This matters here more than it did there, because two of this module's invariants are
database-level: the append-only progress history (5.2) and the audit trail on the org chart
(5.8).

### 7.3 Native enums: `values_callable` is required, `create_constraint` is off by default

`Enum(SomeEnum, name="shema_x_enum", values_callable=lambda c: [m.value for m in c])` —
without `values_callable` PostgreSQL stores the member *names* and not the lowercase values
FE-44 froze. And `Enum` has carried `create_constraint=False` since SQLAlchemy 1.4, so on
SQLite — **the dialect the tests run on** — the column is a bare `VARCHAR` and nothing refuses
a fifth value. Turn it back on, as `app/db/models/resource_request.py` does: PostgreSQL emits
no CHECK beside a native enum, so it costs production nothing and it is what lets a test watch
the database refuse a bad value.

**Which of this module's vocabularies may be an enum, and which may not.** FE-44's Appendix A
freezes twenty; the test is whether the client can extend it.

| Enum-safe (frozen by a built screen) | Must be a column of text, or a table |
|---|---|
| `HealthRating`, `PrayerVisibility`, `NeedUrgency`, `NeedStatus`, `MaterialKind`, `StoryRecordStatus`, `EtenCreditSource`, `YesNo`, `RegionKey`, `RoleKey` | `statusGoal` and `orgRole` — **not vocabularies at all**, free text the export happened to produce, with no screen editing them and no list defining them. `formType` — a free `string` on purpose (FE-44 §12.9); typing it as `FormKind` rejects the prototype's own values on the first import. `languageCode`, `speakerCount`, `vitalityStatus` — text. |

`ProjectStatus` is the one that needs care: **eight values of which two are derived-only**
(`final`, `nao-iniciado`). An enum narrowed to the three editable values makes the 24 records
stored as `desconhecido`, `cancelado` or `concluido` unsaveable. Store all eight, derive the
two.

### 7.4 New here: two of FE-44's rules are *absences*, and an ORM default will undo both

The ones that a well-meaning `default=` erases:

- **`prayer_visibility` is NULL and NULL means `coordenacao`.** Do not give the column a
  server default, and do not backfill it in a migration. *Nothing has to be written for a
  request to stay private; something has to be written for it to travel.*
- **An unassessed health dimension is `""`, and `""` is not `boa`.** All 127 seed records
  arrive with every dimension empty, so *not assessed* is the dominant state, not an edge
  case. A server that defaults an unassessed dimension to `boa` **reports every silent team as
  healthy** — which is the exact failure the product exists to prevent.

A third of the same shape: **media authorization defaults to not authorized.** Only an
explicit `granted = true` counts. This one is a `false`/NULL default rather than an absent
one, but it fails the same way if it is inverted for convenience.

---

## 8. What BE-01 built

Three files and one line, and nothing else:

| File | What |
|---|---|
| `app/api/shema/__init__.py` | The module router. **No routes.** |
| `app/services/shema/__init__.py` | The service package. **Empty.** |
| `tests/test_shema/test_mount.py` | Proves the mount by hanging a probe route off the router and rebuilding the app. |
| `app/main.py` | **One line**, the module's whole footprint there. |

No models, no migration, no service, no endpoint. The anchor is what lets BE-02…BE-16 add
routers without touching `app/main.py` and without a second conversation about the prefix.

**What BE-03 added to it, and the one shape worth knowing before writing a router.**
`app/api/shema/__init__.py` now holds three routers: `router`, which `app/main.py` mounts and
which carries no dependency of its own; `authenticated`, which carries
`require_app_access(APP_KEY)` once; and — since OBT-523 — `door`, which carries the PME's door
and holds `GET /session` (§6.8) and, since OBT-524, the member's two reads (§6.9). **Include your sub-router into `authenticated`.** That is
what makes the module deny-by-default — a route added by a later issue is refused for an
account with no Shemá grant whether or not its author wired a guard — and it is a property of
the file rather than a thing to remember. `router` stays plain so BE-12's two unauthenticated
intake routes (§6.6) have somewhere to go: the hole is a named line in a diff instead of a
dependency somebody has to notice is missing. Two tests hold the shape —
`test_every_shema_route_is_guarded` reads the built application's route table against an
allowlist that is empty today, and `test_every_authenticated_route_reaches_the_application`
catches the one footgun of the arrangement, which is that `include_router` copies routes at
call time and a line added below the mount would 404 rather than fail.

---

## 9. The open client gates — what each one costs this module

None may be frozen by implementation. FE-44 §11 is the full statement; what follows is the
schema consequence, which is the part that outlives the gate.

### 9.1 GATE-01 — the ETEN credit rule ([OBT-387](https://linear.app/shema-obt/issue/OBT-387))

**Blocks BE-11.** Karina Marinho answered the core on 14/aug/2026 — *a credit is one completed
defined scope, counted in **approved** chapters*, **not a divisor**: a 25-chapter scope and a
260-chapter New Testament are worth one credit each. Formal confirmation with Youngshin is
still owed, so `accountFor` stays one swappable pure function.

**The schema consequence BE-02 must know about now:** `status` records *that* a project
finished and never *when*, and the report is per year. Closing item 6 of that gate needs a
real **`completed_date`** column. It is the one open item on the list that is a schema change.

And a data fact that lands on this gate: **the export's `approvedUnits` is a copy of
`translatedUnits` on all 127 records**, so migrating it as-is would credit approvals nobody
made. **Open · BE-16**, with BE-11 needing the answer.

> **Closed on 25/sep/2026** (OBT-387): the rule above confirmed, the fiscal year August–July cut
> on 31/07, the whole credit to each partner, the credit in the year the project ended, partial
> scope worth zero, and `completed_date` written from then on. **Built by BE-11** — see the note
> under §5. Still open, and not blocking: the format of ETEN's own report. On 28/sep/2026 the
> client said ETEN changes it every year and had not sent this year's, so it is not an answer
> that will close once — BE-11 keeps the form in one owner, where the next one lands as a
> presenter without touching the rule or the recorded reports (the note under §5).

### 9.2 GATE-02 — the Rhythm meeting set ([OBT-388](https://linear.app/shema-obt/issue/OBT-388))

**Blocks BE-10.** The expensive question is **whether the meeting set differs by region** —
a data-model fork, not a detail. Today `MeetingLogEntry.scopeKey` carries a region or
`"global"` while the *definitions* are global. A per-region set means the definition itself is
scoped, which changes the table **and** the readiness computation. **Do not build either shape
until the gate answers** — which is why §5.9 makes `shema_meeting_definitions` conditional and
`shema_meeting_log` unconditional.

> **Answered by the client on 22 and 25/set/2026, and built by BE-10
> ([OBT-399](https://linear.app/shema-obt/issue/OBT-399)).** The set is **the same in the seven
> regions**, so `shema_meeting_definitions` is never created and no migration was needed: the log
> table BE-02 built already had every column. Of the five encounters, three are logged —
> `bimestral_pi_campo`, `trimestral_pi_pontes`, `semestral_member_care` — and two are not: the
> Pulso Mensal's record is the submission received (BE-12) and the annual celebration is a report
> (FE-50). Six decisions travel with it.
>
> - **No `GET /api/shema/meetings`.** FE-44 §9.0 made it the one vocabulary endpoint only while the
>   set might differ by region; the issue records that `RITMO_MEETINGS` stays the console's source.
>   The server keeps what it enforces — each meeting's cadence, in `app/utils/shema_meetings.py` —
>   and because the console compares `period` as text, that table is pinned by a test.
> - **The period is read by field, with two new cadences.** `period_key`, `period_start` and
>   `period_end` sit in their own block of `app/utils/shema_derivations.py`: `YYYY-MM`, `YYYY-Bn`
>   (B1 = January–February), `YYYY-Qn`, `YYYY-Hn` (H1 = January–June), `YYYY`. The wire date goes
>   through `parse_iso_date`, which refuses what Pydantic's `date` and `date.fromisoformat` accept
>   and the console never sends — a timestamp, an offset, `20260301`, an ISO week.
>   `tests/test_shema/test_periods.py` moves the process to UTC-3 and UTC+14 and proves the trap is
>   armed before trusting a pass.
> - **A second log of a period replaces the first**, with the unique constraint as the arbiter: the
>   write reads, then creates or rewrites inside a savepoint, and retries once on the two races —
>   a concurrent first insert, and an undo landing mid-write.
> - **The log's audience is the health assessment's.** Its notes are a pastoral reading of a team,
>   so `_meeting_log.py` composes `_health_audience.py`'s list instead of copying it:
>   `resourceCircle` is refused the log on all three routes, fail-closed until the client defines
>   the bridge people and they turn out to include it. The region scope applies on both sides, and
>   out of scope is a 403.
> - **`global` is refused with the reason.** Every meeting kept is held per region.
> - **The notes are the artifact.** GATE-02's own table answered which encounters produce what; no
>   meeting produces a stored file, so the log carries no URL or storage key and opens no upload
>   path (§4.6).
>
> Readiness stays derived on the console (FE-44 §9.7): the Pulse's is FE-49 counting
> `GET /forms/submissions`, not anything this module stores twice.
>
> **The half GATE-02 left open, as of 28/set/2026.** The health assessment feeds the bimonthly
> meeting — confirmed by the client. The bridge people are **not defined yet**: the client does
> not have the list, and asked for the quarterly meeting to work without specific names. Here it
> already does, because the server stores no attendee. §10 item 13 keeps what is left.

### 9.3 GATE-03 — the Pulse file format ([OBT-389](https://linear.app/shema-obt/issue/OBT-389))

**Blocks BE-12 and part of BE-09.** Format, authority when two formats disagree, the
distribution model, and retention/withdrawal from an already-distributed file.

**What is *not* open, and BE-12 may build now:** the Pulse contains prayer requests and is
built to be forwarded, so **only authorized requests go in, and sensitive countries are
transformed before serialization, not at render time.** The privacy rule is
format-independent, and it is the part to raise in the client conversation, because it changes
what belongs in the file more than the format does.

Also not open: the import is idempotent and transactional, the submission is archived
byte-identically, and only the Pulse is archivable. Those are DoD lines, not format choices.

> **BE-09 built the Prayer Pulse's half of the rule, and the format is one function.** Karina
> (22/sep) separated the two Pulses: the *Pulso Mensal* comes back from the field (BE-12), the
> *Pulso de Oração* goes out to the network. For the second, only authorized requests go in, the
> place is reduced before serialization — the entries are leaving shapes, and the file is
> rendered from them and nothing else — and the file itself says it is for the intercessor network
> only, that whoever receives it does not forward it, and that what was sent cannot be recalled
> (3.1, 3.3). The format was delegated, *o mais simples possível*, to be measured in a field test
> whose leader has not been named: plain text, one entry after another, in `pt-BR` or `en`, in
> `app/models/shema_prayer.py`'s `render_prayer_pulse`. **It is a hypothesis until that test**;
> changing it is replacing that function, and the gate, the scope and the reduction do not move.
> Where the country is not printed, the entry names its region in the console's words — six of
> the seven: the console calls `other` *América Central*, and `other` is also where every country
> the map does not list and every empty location fall, so a file that cannot be recalled prints
> no place for it rather than a guess.

> The offline artifact is this project's highest technical risk: an unknown Android phone, no
> connectivity, and a file round trip through WhatsApp. **Prove it on a real device early.**

### 9.4 The fourth gate, which has no issue: what *devida cautela* means per output

`CLAUDE.md` §6.1 marks it. One concrete question was open and named in §6.4: **the base
name**. The export empties it for a withheld record; the console still renders it verbatim in
cards, tooltips and the prayer wall, and both flagged records carry a base that names a place.
Redacting it everywhere is a **second rule** and it belongs to this gate — **do not invent it
surface by surface.**

**BE-04 answered the server half of it, once, and that is the opposite of surface by surface.**
Every shape that leaves coordination withholds the base, because the rule is applied in one
validator that every such shape inherits — so there is no surface holding a pen. The reasoning
is the issue's own: withholding `Egypt` while printing `YWAM Egypt` one column over redacts
nothing, so a file that carries the base carries the country, and when the rule cannot be
decided the fail-closed answer is the one to take. **What is still the gate's** is the
console's own rendering of its coordination surfaces — cards, tooltips, the record — which is
presentation, and which the server neither sees nor should decide. If the client answers that
the base may travel, the change is one line in `BASE_FIELDS` rather than a sweep of consumers,
which is the property that made deciding now cheap enough to do.

> **GATE-04 answered the per-role half (Karina 22/sep, Daniel 23/sep), and OBT-528 built it.**
> The base is hidden from everything that leaves and from every reader who is not coordination;
> so are the country and the place; and the withheld notice is coordination's. The console's
> cards and record are no longer the gate's to render: the server sends each reader what it may
> read, and says which it sent (`readAs`). §6.4 carries the table.

> **Answered for the ETEN report on 28/sep/2026: the `projectId` may travel on its line.** BE-11
> had left it as a question, because a Shemá id is `<language>-<place>` (§6.4). The rule on the
> place is unchanged — the region where the country would be, no base, no contact, and a recorded
> report that keeps the region and never the country. **To confirm, and not decided here:** the
> answer was about the id, and for a flagged project the id — like the language name GATE-04
> (1.5) already lets through — can itself name the place, which the recorded report then keeps.
> **Both closed:** the id by OBT-552 (1/out/2026), the language name by OBT-560 (2/out/2026) — a
> flagged project's line carries the name coordination registered, or the region key (§6.4).

### 9.5 The fifth gate, which has no issue either: **which countries are sensitive** — open, and BE-16 is running fail-closed against it

> Added by BE-16 ([OBT-405](https://linear.app/shema-obt/issue/OBT-405)). The gate was always
> there — OBT-405's own text says *get the list from the client, in writing* — and it had no
> section of its own, which is how a pending client answer becomes a value somebody assumes.

**The list has not arrived.** Until it does, the 127 imported records carry
`sensitive_country = true` — **all of them** — because the rule OBT-405's DoD states is
*an unrecognised country is sensitive until confirmed*, and a list nobody has written
recognises nothing.

What the gate costs, and what it does not:

| | |
|---|---|
| **Costs nothing in schema** | The column is BE-02's and it is a boolean. The answer changes 127 rows, not one line of DDL. |
| **Costs nothing in code** | `scripts/import_shema_projects.py` takes the list as `--countries <path>`, a JSON file **outside this repository**. The day it arrives is a re-run, not a change. |
| **Costs the product its map, meanwhile** | Every record is withheld, so §6.4's redaction applies to all of them: the Atlas plots 127 region centroids, cards show a region in place of a country, and the withheld count is the whole collection. That is the intended reading of a pending gate and not a bug to work around — **do not clear flags to make a screen look right.** |

**The file the client's answer becomes**, so the shape is decided before the answer is:

```json
{"confirmed_on": "…", "confirmed_by": "…",
 "countries": {"Brazil": "not-sensitive", "Egypt": "sensitive"}}
```

Keys are the **export's own spellings** (§6.1's map is keyed the same way), and the verdicts
are spelled out rather than `true`/`false` so a truncated file fails loudly instead of reading
as a country cleared for publication. **A country the file does not name is unrecognised, and
unrecognised is sensitive** — so the answer has to be complete, and the import's report lists
every country the export names for exactly that reason.

**Two one-way rules the gate does not get to override**, both of them BE-16's and both argued
in that script's docstring. The export may **raise** the flag and may never lower it —
**one of the two records the export marks** `Confidential` **is in Mexico**, where seven other
records are `Unrestricted`, so a list keyed by country cannot express what that record already
states — and which record it is belongs in the import's report, which lives outside the
repository, not in a design document. And
clearing a flag needs `--allow-lowering` on top of `--apply`: raising protects and lowering
exposes, so only one of the two directions is allowed to happen by momentum.

**And a third rule, which is about people rather than about the gate.** The reconcile
re-derives `region_key` only while `location` still holds what was imported, and it lowers a
flag only while `sensitivity` — the free text beside the flag, writable on
`ShemaProjectUpdate` — still holds what was imported. Same question in both places: *has a
person been in the column this value is read from?* What the question cannot reach is
`sensitive_country` itself, because a boolean keeps no provenance and a coordinator's `true`
is the import's `true`; that is §10's question 12, and it belongs to the write path.

---

## 10. Open questions, each with the issue that owns it

Deliberately not answered here: each has an owner with evidence this issue does not have.

| # | Question | Owner |
|---|---|---|
| 1 | ~~Whether `team`/`ywamBase` and `sensitivity`/`sensitive_country` stay as two columns each.~~ **Answered by BE-02, in opposite directions, because the pairs are not the same shape.** `team` and `ywamBase` are **one column**: they are one concept in two languages, identical on all 127 records, and collapsing removes the drift instead of policing it. `sensitivity` and `sensitive_country` **stay two**, with the boolean authoritative: the text is a free-text export column that agrees with the flag by accident of the data, so collapsing would delete evidence. **BE-16 departs from one half-sentence of that answer:** BE-02 expected the import to *derive the flag from the text*, and it does not — §9.5's client list is where the flag comes from, and the export's text and boolean may only **raise** it. The columns and their ownership are unchanged; what changed is that the export is never read as permission. | ~~BE-02~~ **closed**, amended by BE-16 |
| 2 | ~~Whether `region_key` is stored as a maintained derived column or computed per query.~~ **Answered by BE-02: stored, maintained, indexed — and deliberately not a generated column,** because the derivation is a lookup over 25 country strings kept in Python and expressing it in DDL would be a second copy of a map whose whole value is that there is one. | ~~BE-02~~ **closed** |
| 3 | ~~The Shemá `app_url` for `seed_apps_roles.py`, and the matching `cors_origins` entry.~~ ~~**Answered by BE-03: `https://shema.shemaywam.com`, and the same value added to `cors_origins`.**~~ **Superseded by OBT-567 (6/oct/2026): the hostname never got a DNS record, and the seed and the installed row now carry `https://project-management-ecosystem-f7ssqjozfq-uc.a.run.app` — the Cloud Run address the PME answers on — by the user's decision that no `shema.shemaywam.com` is planned; `20261006_shema567` is the UPDATE, guarded by the old value. `cors_origins` was left to the core (the deployed PME proxies `/api` through its own nginx, so CORS never applied to it). The PME still has no `/reset-password` route, so the link reaches a real host and no page — the PME's screen, not this module's.** BE-03's reasoning, kept as history: there was no deployment to read — the console is wave 1, with no deploy workflow, no environment file beyond `VITE_API_PROXY_TARGET`, and no host named in either repository — so this follows the eight rows already in `SEED_APPS`, every one of them the product's name lowercased with no separators. Leaving it empty was the alternative and is worse: `request_password_reset` then builds the reset link from `http://localhost:5173` in production, which is the silent failure §2.3 warns about, while a conventional hostname that turns out wrong fails on the first click and is a one-row UPDATE to correct. | ~~BE-03~~ **closed** |
| 4 | ~~Whether `GET /api/shema/session` falls back to `users.display_name` for `globalStrategist` (retired by OBT-572; the `admin` is the seatless role now), which has no org-chart seat (§6.3).~~ **Answered by BE-03: yes**, and generalised to one rule — the seat is read when the role has one, the scope names exactly one region and the seat is filled; everything else falls back. §6.3 carries the argument. | ~~BE-03~~ **closed** |
| 5 | ~~Whether the intercessor network belongs to BE-09 or BE-13 — FE-44 §9.6 and the issue titles disagree (§1.3 C3).~~ **Answered by BE-13: the network is BE-13's**, because INT-10 is blocked by OBT-402 and not by OBT-398 and OBT-402's whole Context section is about that table. The frozen paths did not move. §1.3 C3 carries the argument. | ~~BE-09 / BE-13~~ **closed** |
| 6 | Whether a `NeedItem` gets a server-side id. It has none today; a derived notification identifies one by `(project, category, submittedAt)`. A real id would be better and would change the shape, which is why it is named rather than done quietly. | **BE-08** (FE-44 §12.5) |
| 7 | ~~Whether `approvedUnits` is migrated as-is, as zero, or flagged unverified (§9.1).~~ **Answered by BE-16: as-is, with `approved_units_unverified` set on every migrated record.** Zero would have discarded the only number there is, and as-is alone would have credited approvals nobody made; the flag says the number came from the export rather than from an approval, which is true of all 127 and needs no second rule for the 105 where it is zero anyway. **BE-11 reads it to tell a migrated count from a typed one**, and the write path that lets somebody approve a chapter for real is the one that clears it. | ~~BE-16~~ **closed** |
| 8 | The three privacy questions the intercessor network cannot ship without. **The first — what consent was given and how it is evidenced — is answered by BE-13**, as `shema_intercessor_consents`: a row per person per context, with a non-empty `basis`, and a create that cannot store a person without one. ~~The other two are still owed and neither is engineering's: how someone outside the platform asks to be removed when they cannot log in, and what happens to a contact nobody has used in a year.~~ **Answered by the client on 22/sep and built by OBT-531** (§6.4's OBT-531 note): an exit link with no login, and a review after a year. **The residual:** a person who withheld `directory` consent cannot be reviewed on any screen — they are counted (`withheldReviewDueCount`), and what to do with them is the client's to say. | **BE-13** (first), **OBT-531** (the other two; the residual is the client's) |
| 9 | Whether drafts move to the server. `localStorage` today, which means a coordinator who fills half a record and opens another browser has lost it. A real cost; no issue owns it. | unowned (FE-44 §12.7) |
| 10 | Whether `permissions`/`role_permissions` should ever be wired into the guards — a repository-wide question the sibling also declined (§4.10). | unowned, repository-wide |
| 11 | Fixing `env.py` so `alembic revision --autogenerate` stops seeing zero tables — repository-wide, touching eight applications' migration workflow ([`docs/resource_requests.md`](resource_requests.md) §8.1). | unowned, repository-wide |
| 12 | Whether `sensitive_country` records **who** raised it. Today it does not, and the import cannot tell a flag a coordinator ticked from the `true` it wrote itself fail-closed — so a hand-raised flag is cleared by the next `--apply --allow-lowering`. BE-16 gates the lowering on the one column that can answer (`sensitivity`, compared against `source`) and names every lowering in its report, which narrows the hole without closing it. Closing it is a write-path decision — an audit column, a `sensitive_country_source`, or a rule that the import never lowers what it did not insert — and it is not a migration script's to take, least of all on a model and a migration ten sibling branches already build on. | **BE-03** (§4.2's write path), with **BE-02** if it costs a column |
| 13 | ~~Whether the health assessment moves to the bimonthly meeting (GATE-02's open half).~~ **Answered by the client on 28/set/2026: yes, it feeds `bimestral_pi_campo`**, which is where FE-49 already read it; nothing on the server held it. **Still open, and not as a pending question: who the *pessoas-ponte* of `trimestral_pi_pontes` are.** The client does not have that information yet and asked for the meeting to work without specific names — which it already does here: the server stores no attendee, and a log is the meeting, the region, the day and the notes. When the list exists, it changes nothing here unless it changes a cadence or the set — one edit in `app/utils/shema_meetings.py` — or puts `resourceCircle` among the bridge people, which would open that meeting's log to it (`_meeting_log.py`). | **the client** (the definition), FE-49 (where it lands) |

---

## 11. What changes in the B1 issues

Every issue from BE-02 to BE-16 gets a `## Design (BE-01)` section appended to its
description, naming what this document changes for it. Nothing is deleted. The recurring
items, so they are stated once:

- **The module is `shema`, the prefix is `/api/shema`, the app key is `shema`**, and the four
  role keys are `coordinator`, `obtLab`, `resourceCircle` (§2.1, §2.3; `globalStrategist` until OBT-572).
- **Do not touch `app/main.py`.** The anchor is mounted; include your router in
  `app/api/shema/__init__.py`, on a line of its own (§3.2).
- **Create your own model file** under the `shema_` prefix; do not grow BE-02's (§2.2).
- **Read the migration head in your own worktree before writing a revision** (§7.1).
- Every issue that emits data depends on **BE-04's three owners** being in place first (§6.4).

Four of these get more than a note, recorded here because they are boundary changes rather
than reminders:

- **BE-02** inherits `shema_projects` as its own table with **no FK to `projects` and no
  `language_id`** (§4.3), the eleven aggregates of §5, and §7.4's two absences that an ORM
  default would erase.
- **BE-03** inherits §6.1's `shema_user_regions` instead of an `organizations` mapping, and
  §6.3's session endpoint.
- **BE-05** inherits §6.5's parity requirement and the vendoring that proves it, and returns an
  envelope rather than `Project[]` — the one edit this module owes the frozen contract. §6.5's
  *What BE-05 built* carries the argument.
- **BE-09 and BE-13** get the same boundary written into both descriptions, and **neither is
  handed the aggregate**: FE-44 §9.6 puts the intercessor routes on BE-09's screen, the
  Linear title *"BE-13 · Equipe e intercessores"* (OBT-402) claims them, and one aggregate
  with two owners is the defect. The edit says *settle it before either writes the table*, on
  OBT-398 and OBT-402 alike — **this document records the conflict rather than choosing for
  the two issues** (§1.3 C3, §10 item 5). What is not contested, and is on both: the network
  never joins a role in either direction, and the three privacy questions of §10 item 8
  follow it wherever it lands (§5.7).

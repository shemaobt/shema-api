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
autorização e geração do Pulso"* (OBT-398). §4.9 and §5.3 decide the seam; §11 records it as
an issue edit rather than leaving two owners.

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
| Role keys | **`globalStrategist`, `coordinator`, `obtLab`, `resourceCircle`** |
| Seeded by | `scripts/seed_apps_roles.py`'s `SEED_APPS` and `APP_ROLES_OVERRIDE` — BE-03 |
| Named in code | `app/api/shema/_deps.py` and nowhere else in the module |

The role keys are the frontend's own ids verbatim, which is the precedent
`resource-request-form` set with `equipe` / `mesa` / `gestor` / `lider` and the reason
`seed_apps_roles.py`'s docstring already gives: *"the four keys are the role ids of the
frontend's `capabilities.ts` verbatim, not a translation of them."* Here the ids are
camelCase (`SessionRole` in `src/types/role.ts`) while most of this repository's role keys
are snake_case. **Keep the camelCase.** `GET /api/shema/session` (§6.4) must answer a
`SessionRole` the frontend can use as a key; a translation table between two spellings of
one vocabulary is a second place to be wrong, and it would be read on every request.

`role_key` is `String(100)` free text scoped per app (`uq_roles_app_role_key`), so nothing
in the platform objects.

**`app_url` is Open · BE-03.** `seed_apps_roles.py`'s docstring records that the column is
not decoration — `request_password_reset` builds `{app_url}/reset-password?token=…` from it,
and a wrong value breaks password recovery silently. The console's hostname is named nowhere
in either repository: `app/core/config.py`'s CORS list carries `tripod-console`,
`oralcollector`, `translationhelper`, `annotationstudio` and `soundnecklace`, and no Shemá
entry. BE-03 reads the real hostname off the deployment rather than guessing, and adds it to
`cors_origins` in the same change.

### 2.4 What it shares — **Decided**

The whole authentication spine, and only through `app/core/access_control.py` and
`app/services/authorization/`: `users`, `apps`, `roles`, `user_app_roles`, `access_requests`,
`access_invites`, `refresh_tokens`, `password_reset_tokens`.

**This module's services never query those tables directly.** The guards are the interface;
a service that reaches for `user_app_roles` has reimplemented `require_role` badly. When the
module needs the join from the other end — *who holds this role* — it asks
`authorization_service.list_role_holders`, which the sibling added for exactly that and whose
docstring states the rule.

The **one** thing this module owns about identity is the region dimension of §6.1, which the
platform has no column for.

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

Two shared-by-accident surfaces are worth naming because they are one import away:
`app/services/notifications/` (§4.6 — call it as it is, do not change its signature) and
`app/services/oral_collector/gcs_utils.py` (§4.6 — the sibling already reuses it with its own
bucket, which is the precedent, not a trespass).

---

## 3. Module layout

### 3.1 The table

| Path | Owner | Holds |
|---|---|---|
| `app/api/shema/__init__.py` | **BE-01** | The module router, mounted once in `app/main.py` under `/api/shema`. Aggregates the sub-routers, one `include_router` line each. |
| `app/api/shema/_deps.py` | BE-03 | `APP_KEY`, `Db`, `CurrentUser`, the four role aliases, and §6.2's region-scope dependency. The app key is named here and nowhere else in the module. |
| `app/api/shema/projects.py` | BE-05, BE-06 | The collection read, the record read, `POST`, `PATCH`. |
| `app/api/shema/health_assessments.py` | BE-07 | `POST`/`GET /projects/{id}/health-assessments`. |
| `app/api/shema/prayer.py` | BE-09 | The wall and the intercessor network. |
| `app/api/shema/meetings.py` | BE-10 | Definitions and the log. |
| `app/api/shema/eten.py` | BE-11 | Report and the credit ledger. |
| `app/api/shema/forms.py` | BE-12 | Submissions, the Pulse artifact, intake links, and the two **unauthenticated** intake routes. |
| `app/api/shema/regions.py` | BE-13 | The org chart and its audit trail. |
| `app/api/shema/transfer.py` | BE-14 | Export and import. |
| `app/api/shema/notifications.py` | BE-15 | The derived panel, preferences, read state. |
| `app/api/shema/session.py` | BE-03 | `GET /api/shema/session` — §6.4. |
| `app/services/shema/` | BE-03…BE-16 | **All** logic and **all** queries. One operation per file with an `__init__.py` re-export — the newer house style (`app/services/access_request/`, `project/`, `auth/`, `resource_request/`), not the grouped `*_service.py` of `annotation_studio/`. |
| `app/services/shema/_scope.py` | BE-03 | Which projects a caller reaches, from role **and** region. The `app/services/resource_request/_scope.py` precedent, with §6.1's second axis. |
| `app/services/shema/_redaction.py` | BE-04 | The sensitive-country owners: the location display and the map placement. §6.5. |
| `app/services/shema/_consent.py` | BE-04 | `reaches_prayer_wall` — the **only** reader of the three prayer columns. §6.5. |
| `app/services/shema/_media_sharing.py` | BE-04 | `can_share_media` — authorization × audience × the sensitive flag. §6.5. |
| `app/utils/shema_derivations.py` | BE-05 | FE-44 §7's nine pure functions of `(record, now)`. **Not** in the service package — see below. |
| `app/models/shema.py`, `app/models/shema_*.py` | BE-02 …, per §2.2 | **Pydantic** request/response models. `ConfigDict(from_attributes=True)` on read models; separate `Create` / `Update` / `Response`. |
| `app/db/models/shema.py`, `app/db/models/shema_*.py` | BE-02 authors, each issue grows its own | **SQLAlchemy** tables. Must be re-exported from `app/db/models/__init__.py` — [`docs/resource_requests.md`](resource_requests.md) §8.1. |
| `alembic/versions/20260NNN_shemaNN_*.py` | BE-02 onward | Migrations. Single head, clean `downgrade -1`. §7.1. |
| `tests/test_shema/` | all | Extend; do not replace. `test_mount.py` is BE-01's. |
| `http/shema*.http` | BE-03 onward | Request examples, as the siblings keep them. |

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
| **Validation of the four required fields** | Pydantic models reject a payload before a service is called (FE-44 §5.1.1). | Re-checks nothing Pydantic already refuses; owns the cross-record rules (a duplicate slug is a `ConflictError`). |
| **Redaction (sensitive country)** | Nothing. A router may not decide what leaves. | `_redaction.py`, called by every service that builds a *leaving* shape. §6.5. |
| **Consent (prayer)** | Nothing. | `_consent.py` is the only reader of the three prayer columns; `list_prayer_requests` is the only query that applies the gate. §6.5. |
| **Media authorization** | Nothing. | `_media_sharing.py`, plus the signed-URL adapter of §4.6. |
| **Derivations** | Nothing. | Services call `app/utils/shema_derivations.py`; response models may import it too (§3.1). |
| **Errors** | Maps a business exception onto a status, or lets the global handlers do it. | Raises `NotFoundError` / `ConflictError` / `ValidationError` / `AuthorizationError` from `app/core/exceptions.py`. **Never imports `HTTPException`.** |
| **The intake link (unauthenticated)** | The two `/intake/{token}` routes carry no auth dependency — the one deliberate hole, and it is a router-level fact. | `verify_intake_token` is the guard: a service function, so the rule holds for any future caller of it. §6.6. |

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
`/logout`, `GET /api/auth/me`. The only Shemá-specific session read is §6.4's
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
   default. The Shemá record's id is **the export's slug** (`afrikaans-kaaps`,
   `purepecha-de-capacuaro`), frozen by FE-44 §5.1 as the address every screen, URL and saved
   view already carries, and BE-16 must not mint new ones.

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
- **No Shemá detail table.** `notification_meaning_map_details` is one product's, and a Shemá
  one would have no reader until something deep-links.
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
| 5.1 | **Project record** | `shema_projects` | BE-02 (schema), BE-06 (lifecycle) | The primary key is the **export slug**, not a minted uuid. Only four fields are required to save — `language_name`, `bridge_language`, `team`, `objective` — and **nothing else is `NOT NULL`**: 27 of the export's 55 columns are empty on all 127 records. No `translated <= total` constraint: three real records violate it. |
| 5.2 | **Progress and its history** | `shema_progress_history` (+ the aggregates on the record) | BE-02, BE-06 | The history entry is **produced by the server**, never accepted from the client — the previous values are the server's own read before the write. An entry is appended **only if an aggregate changed**, and it snapshots the three unit tables. Roll up **only** the tables that can express counts. Stamp the actor's **local** day. |
| 5.3 | **Health assessment** | `shema_health_assessments` | BE-02, BE-07 | **Its own aggregate.** The flat fields on the record are a *projection of the newest entry*, never a second truth; append and re-project in one step, and carry a pre-history record into the history before appending. The **per-dimension note is the data**; the running note is derived from it at write time. `""` is not `boa`. |
| 5.4 | **Needs** | `shema_needs` | BE-02, BE-08 | They **travel with the project** — edited on record tabs, saved by the record's `PATCH`. No separate needs endpoint in wave 1; adding one gives `needsItems` a second owner. Four states, not three: `dropped` leaves the open list without deleting the history a region is judged by. |
| 5.5 | **Media and materials** | `shema_media_items`, `shema_materials` | BE-02, BE-04 (the rule), BE-06 (the write) | **The default is not authorized** — only an explicit `granted = true` counts, so an undecided item behaves as a refused one. Every decision carries who and when, as a **snapshot that must not follow a rename**. **Replacing the artifact resets the decision to undecided.** The row stores a storage **key**, never a URL (§4.6). |
| 5.6 | **Prayer** | *(none for the wall)* | BE-09 | **The wall is derived, never stored**, which is what makes withdrawal free: moving a request back to `coordenacao` removes it from the next query with no cleanup step. The three columns live on the record; `_consent.py` is their only reader. If BE-09 ever stores requests, a withdrawn one is **deleted from that store**, never flagged and retained. |
| 5.7 | **Intercessor network** | `shema_intercessors` | BE-02, BE-09 *or* BE-13 — §1.3 C3 | **Never joined to roles, in either direction.** Country is ISO 3166-1 alpha-2, never prose. At least one usable channel or the record is **refused**. **Removal erases** — no tombstone, no `removed` flag, the contact absent from storage. |
| 5.8 | **Org chart** | `shema_region_teams`, `shema_role_changes` | BE-02, BE-13 | **The single source of who holds which role where**, with four consumers, all by reference. No other model stores a role-holder's name. A team change is a write **with an audit row**, not a silent update, and the name in the audit row is a snapshot that must not follow a rename. |
| 5.9 | **Meetings** | `shema_meeting_log` (+ `shema_meeting_definitions` only if GATE-02 says so) | BE-02, BE-10 | Unique per `(meeting, scope, period)` — a second log for the same period **replaces** the first. The server derives `period` from the date and the cadence, never from the client. **Whether the definitions are a table at all is Open · GATE-02** (§9.2). |
| 5.10 | **Notification preferences and read state** | `shema_notification_prefs`, `shema_notification_reads` | BE-02, BE-15 | The panel's entries are **derived from the projects**, so their ids are not rows. The read state is its own small table keyed by `(user, derived id)` — which FE-44 §5.8's stable-id rule is what makes safe. **Route by role and region *before* capping at 30**; capping first lets one region evict another recipient's entries. |
| 5.11 | **ETEN ledger** | `shema_eten_credits` | BE-02, BE-11 | A stored `manual` entry **overrides** the computed value; `calculated` marks what the rule produced. **A year with no data is not a year of zero credits.** Do not seed. The rule is **Open · GATE-01** (§9.1). |
| 5.12 | **Forms and intake** | `shema_submissions`, `shema_intake_links` | BE-02, BE-12 | The import is **idempotent and transactional** — a double import is a no-op. The submission is archived **byte-identically**. **Only the Pulse is archivable.** The leader link grants the intake form and nothing else, and it expires. Format is **Open · GATE-03** (§9.3). |
| 5.13 | **Region scope grant** | `shema_user_regions` | BE-03 | §6.1. The one thing this module owns about identity. Empty means global. |

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
`globalStrategist`, and any account the client wants unscoped. The grant itself stays
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
  region may write it; there is no third answer in the product.

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
GET /api/shema/session -> {role: SessionRole, regionScope: RegionKey[] | null, name: string | null}
```

`GET /api/auth/my-roles` cannot answer this, because the grant has no region. The three parts
come from three places and **none of them is a new store**: `role` from
`authorization_service.list_roles(db, user.id, "shema")`; `regionScope` from
`shema_user_regions` (`null` = global); and **`name` resolved from the org chart** (§5.8) —
it is not a user profile field, and renaming a role-holder renames who the session says you
are.

`globalStrategist` is a role key with no org-chart seat (the chart's three roles are per
region). FE-44 §12.2 leaves `GLOBAL_STRATEGIST_NAME` as the frontend's one remaining
hardcoded name. **Open · BE-03:** whether `name` for that role falls back to
`users.display_name`. Either answer is cheap; picking silently is what is not.

### 6.4 Seam C — privacy, and why it is three owners and not one — **Decided; BE-04 builds**

FE-44 §8 is written as server requirements and `CLAUDE.md` §6.1/§6.2 as invariants. The
scheduling is already right: BE-04 lands **before anything that emits data**. What this
document adds is where the rules live, because *"enforced in the service layer"* is not yet a
file.

**Three owners, each the sole reader of what it guards:**

| File | Owns | The rule |
|---|---|---|
| `app/services/shema/_redaction.py` | `sensitive_country` | The location is replaced by the **region name** — the withheld **marker**, never an empty string, so the redaction travels in the shape and a renderer downstream cannot leak what the payload does not hold. Coordinates become the region centroid. **The base name goes with the location** in any file that leaves: both flagged records carry a base that names a place (`YWAM Egypt`, `YWAM Morelia`), so withholding `Egypt` while printing `YWAM Egypt` one column over redacts nothing. |
| `app/services/shema/_consent.py` | `prayer_requests`, `prayer_visibility`, `prayer_requests_audio` | **The only reader of those three columns**, and one query applies the gate. The column is **nullable and NULL means `coordenacao`** — do not default it to `rede` and do not backfill it. It is a **visibility level, not a published boolean**: a team that has not consented to being shared still reaches the people who follow up. |
| `app/services/shema/_media_sharing.py` | `authorization` on media and materials | Composes, most restrictive wins: an authorized item reaches `coordenacao`; the same item on a sensitive project **never** reaches `publico`. |

**The split that keeps this from over-redacting.** A project **read** by someone allowed to
open it is a *coordination* surface and carries the truth — hiding the country from its own
author is data loss, not privacy. Every shape that **leaves** coordination carries the
redaction in its own Pydantic model: the prayer request, the ETEN snapshot, the notification
entry and the exported project each hold a `location_withheld` flag rather than a bare
string. **Redact in the payload on every path that leaves; never on the record read.**

**The check that makes it a rule rather than an intention.** FE-44's frontend has a scan test
that fails the build if any shipped file outside the record's own editing surfaces reads the
raw prayer columns. **BE-04 owns the same test here**, and this repository already has the
shape for it:
`tests/test_resource_requests/test_access.py::test_the_app_key_is_named_once_in_the_module`
globs a directory and fails on a literal. `tests/test_shema/test_privacy_owners.py` globs
`app/services/shema/*.py` and `app/api/shema/*.py` and fails when a file that is not the
named owner references one of the guarded columns. A rule applied per endpoint is a rule the
next endpoint forgets; a glob is not.

**The acceptance test the delivery plan already names:** an unauthorized prayer request is
absent from **all four** output paths — the wall, exports, the ETEN report and notifications.

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

### 6.6 Seam E — the unauthenticated intake — **Decided**

`GET /api/shema/intake/{token}` and `POST /api/shema/intake/{token}` are the only routes in
this module with no `Authorization` requirement, by FE-44 §9.0. Three rules:

- **The token is the whole guard**, so the guard is a **service function**
  (`verify_intake_token`) and not a router condition — the rule then holds for any future
  caller, which is the same argument §6.4 makes for the consent gate.
- **It grants the intake form and nothing else.** No console, no project data, and it
  expires. It is not a session and it mints no token pair.
- The token is stored **hashed**, following every other token in this repository —
  `refresh_tokens`, `password_reset_tokens` and `access_invites` all store a `String(64)`
  `token_hash` and let the raw value leave only once.

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

### 9.2 GATE-02 — the Rhythm meeting set ([OBT-388](https://linear.app/shema-obt/issue/OBT-388))

**Blocks BE-10.** The expensive question is **whether the meeting set differs by region** —
a data-model fork, not a detail. Today `MeetingLogEntry.scopeKey` carries a region or
`"global"` while the *definitions* are global. A per-region set means the definition itself is
scoped, which changes the table **and** the readiness computation. **Do not build either shape
until the gate answers** — which is why §5.9 makes `shema_meeting_definitions` conditional and
`shema_meeting_log` unconditional.

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

> The offline artifact is this project's highest technical risk: an unknown Android phone, no
> connectivity, and a file round trip through WhatsApp. **Prove it on a real device early.**

### 9.4 The fourth gate, which has no issue: what *devida cautela* means per output

`CLAUDE.md` §6.1 marks it. One concrete question is already open and named in §6.4: **the base
name**. The export empties it for a withheld record; the console still renders it verbatim in
cards, tooltips and the prayer wall, and both flagged records carry a base that names a place.
Redacting it everywhere is a **second rule** and it belongs to this gate — **do not invent it
surface by surface.**

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
`zapoteco-de-santiago-lachirigi` is `Confidential` in **Mexico**, where seven other records are
`Unrestricted`, so a list keyed by country cannot express what that record already states. And
clearing a flag needs `--allow-lowering` on top of `--apply`: raising protects and lowering
exposes, so only one of the two directions is allowed to happen by momentum.

---

## 10. Open questions, each with the issue that owns it

Deliberately not answered here: each has an owner with evidence this issue does not have.

| # | Question | Owner |
|---|---|---|
| 1 | ~~Whether `team`/`ywamBase` and `sensitivity`/`sensitive_country` stay as two columns each.~~ **Answered by BE-02, in opposite directions, because the pairs are not the same shape.** `team` and `ywamBase` are **one column**: they are one concept in two languages, identical on all 127 records, and collapsing removes the drift instead of policing it. `sensitivity` and `sensitive_country` **stay two**, with the boolean authoritative: the text is a free-text export column that agrees with the flag by accident of the data, so collapsing would delete evidence. **BE-16 departs from one half-sentence of that answer:** BE-02 expected the import to *derive the flag from the text*, and it does not — §9.5's client list is where the flag comes from, and the export's text and boolean may only **raise** it. The columns and their ownership are unchanged; what changed is that the export is never read as permission. | ~~BE-02~~ **closed**, amended by BE-16 |
| 2 | ~~Whether `region_key` is stored as a maintained derived column or computed per query.~~ **Answered by BE-02: stored, maintained, indexed — and deliberately not a generated column,** because the derivation is a lookup over 25 country strings kept in Python and expressing it in DDL would be a second copy of a map whose whole value is that there is one. | ~~BE-02~~ **closed** |
| 3 | The Shemá `app_url` for `seed_apps_roles.py`, and the matching `cors_origins` entry. Read it off the deployment (§2.3). | **BE-03** |
| 4 | Whether `GET /api/shema/session` falls back to `users.display_name` for `globalStrategist`, which has no org-chart seat (§6.3). | **BE-03** |
| 5 | Whether the intercessor network belongs to BE-09 or BE-13 — FE-44 §9.6 and the issue titles disagree (§1.3 C3). | **BE-09 / BE-13**, settled by §11's issue edit |
| 6 | Whether a `NeedItem` gets a server-side id. It has none today; a derived notification identifies one by `(project, category, submittedAt)`. A real id would be better and would change the shape, which is why it is named rather than done quietly. | **BE-08** (FE-44 §12.5) |
| 7 | ~~Whether `approvedUnits` is migrated as-is, as zero, or flagged unverified (§9.1).~~ **Answered by BE-16: as-is, with `approved_units_unverified` set on every migrated record.** Zero would have discarded the only number there is, and as-is alone would have credited approvals nobody made; the flag says the number came from the export rather than from an approval, which is true of all 127 and needs no second rule for the 105 where it is zero anyway. **BE-11 reads it to tell a migrated count from a typed one**, and the write path that lets somebody approve a chapter for real is the one that clears it. | ~~BE-16~~ **closed** |
| 8 | The three privacy questions the intercessor network cannot ship without: what consent was given and how it is evidenced; how someone outside the platform asks to be removed when they cannot log in; what happens to a contact nobody has used in a year. **Shipping the storage before answering them is how silent retention starts.** | **BE-09**, and they are not engineering questions |
| 9 | Whether drafts move to the server. `localStorage` today, which means a coordinator who fills half a record and opens another browser has lost it. A real cost; no issue owns it. | unowned (FE-44 §12.7) |
| 10 | Whether `permissions`/`role_permissions` should ever be wired into the guards — a repository-wide question the sibling also declined (§4.10). | unowned, repository-wide |
| 11 | Fixing `env.py` so `alembic revision --autogenerate` stops seeing zero tables — repository-wide, touching eight applications' migration workflow ([`docs/resource_requests.md`](resource_requests.md) §8.1). | unowned, repository-wide |

---

## 11. What changes in the B1 issues

Every issue from BE-02 to BE-16 gets a `## Design (BE-01)` section appended to its
description, naming what this document changes for it. Nothing is deleted. The recurring
items, so they are stated once:

- **The module is `shema`, the prefix is `/api/shema`, the app key is `shema`**, and the four
  role keys are `globalStrategist`, `coordinator`, `obtLab`, `resourceCircle` (§2.1, §2.3).
- **Do not touch `app/main.py`.** The anchor is mounted; include your router in
  `app/api/shema/__init__.py`, on a line of its own (§3.2).
- **Create your own model file** under the `shema_` prefix; do not grow BE-02's (§2.2).
- **Read the migration head in your own worktree before writing a revision** (§7.1).
- Every issue that emits data depends on **BE-04's three owners** being in place first (§6.4).

Two issues get more than a note, and both are recorded here because they are boundary
changes rather than reminders:

- **BE-02** inherits `shema_projects` as its own table with **no FK to `projects` and no
  `language_id`** (§4.3), the eleven aggregates of §5, and §7.4's two absences that an ORM
  default would erase.
- **BE-03** inherits §6.1's `shema_user_regions` instead of an `organizations` mapping, and
  §6.3's session endpoint.

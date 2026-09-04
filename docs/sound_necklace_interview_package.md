# The Sound Necklace interview package

**Status:** dormant since the 2026-09-01 scope cut (ENG-690). Written against `main` at
`c68bf5e`.
**Audience:** whoever builds the system that hosts the interview next. It is written so
you do **not** have to read the code to decide whether this package is what you want.
**Inputs:** [`CLAUDE.md`](../CLAUDE.md) — where this document and it disagree about how
this repository is written, `CLAUDE.md` wins and this one has rotted.

---

## 0. What happened, and what "dormant" means here

The Colar de Sons — the SPA that consumes this API — had its scope cut by the owner on
2026-09-01. It now ends at the segmentation into scenes and phrases: no interview, no
report, no artifact of any kind. Cuts keep being saved by the autosave exactly as before,
and another system will consume them.

The interview comes back later, **in another flow, in another system**. This package is
what that system inherits.

Nothing was deleted for the cut. No code, no route, no table, no row. What changed is only
this:

| Dormant means | Dormant does **not** mean |
|---|---|
| No client calls these routes | The routes are switched off |
| No new rows arrive in the two tables | The tables were dropped, or any row removed |
| Every module carries a `DORMANT since the 2026-09-01 scope cut` header | The code is deprecated or scheduled for deletion |

The routes are still mounted in `app/api/sound_necklace/__init__.py`, still authenticated,
still fenced by the session lock, and still answer exactly as they did the day before the
cut. `tests/test_sound_necklace/` still exercises all of it on every pull request, and
`tests/test_sound_necklace/test_contract.py` fails if any of the nine operations below
stops appearing in the emitted OpenAPI schema. That test is the thing standing between
"asleep" and "quietly removed by a later cleanup".

**The one thing missing to use this elsewhere is a client.** See §6.

---

## 1. What the package does, end to end

One storyteller answers one question out loud. That is the unit.

```
  a facilitator records an answer in the SPA
        │
        │  PUT /sessions/{id}/resources?path=respostas/…/<k>.webm      (raw WebM/Opus bytes)
        ▼
  sn_voice_answers ─────────────────────────────────► the object, in the private bucket
        │
        │  POST /sessions/{id}/transcriptions {language}   → 202, and an Inngest event
        ▼
  the batch job (app/inngest/sn_transcription.py), off the API process
        │
        ├─ 1. transcribe, verbatim, in the language it was spoken   (platform/stt)
        ├─ 2. take the speech disfluency out of it                  (platform/disfluency)
        └─ 3. if that is not English, translate                     (platform/translation)
        ▼
  sn_answer_transcripts, status=ready — A DRAFT. Nothing downstream may read it yet.
        │
        │  GET /sessions/{id}/transcriptions   ← the client polls this
        ▼
  a human reads the draft on screen, corrects it, and confirms it
        │
        │  PUT /sessions/{id}/transcriptions/{resource_path} {transcript_source, generation}
        ▼
  the same row, rewritten: the human's text, and the English RE-DERIVED from it
        │
        ▼
  the client composes its artifacts from the confirmed text, and posts them
        │
        │  POST /sessions/{id}/artifacts   (multipart, three files, opaque bytes)
        ▼
  sn_artifacts + the objects in the bucket, byte-identical to what was uploaded
```

Three properties fall out of that shape, and they are the reason it is worth reusing
rather than rewriting:

- **Idempotent.** A draft already `ready` is never made again, so a reloaded screen costs
  nothing at the provider. `force` is the re-record case and is the only thing that
  discards work.
- **Resumable.** The per-answer rows *are* the job's state; there is no job table and no
  `running` status. A worker that dies leaves `pending` rows, and the next trigger picks
  them up.
- **Partial-failure-proof.** One dead answer is one `failed` row carrying its own reason.
  It is never a failed job and never a 500 — a single bad recording must not hold a whole
  session shut.

---

## 2. The rules that came with it, and are not negotiable at the API level

These are not implementation details. They are the reason the design is shaped this way,
and a reimplementation that drops them is not this package.

### 2.1 A transcription is a **draft** until a human confirms it

`sn_answer_transcripts` is advisory. Nothing the models wrote is ever merged into an
artifact by this API. The draft is a *suggestion about* the recording; the recording is the
evidence. That is why the text lives in its own table rather than on the answer row — a
`force` throws the suggestion away and never touches the evidence.

This is also the constraint that keeps the whole path inside [`CLAUDE.md`
§9](../CLAUDE.md): every model step on the answer path runs **before** a facilitator reads
and confirms the sentence on screen, so nothing a model wrote reaches an artifact
unreviewed. Moving the confirmation later — or making the artifact read the draft directly
— breaks exactly that property. It is not a refactor to make casually.

Two columns, not one, for the same reason. `transcript_verbatim` is what speech-to-text
returned before the disfluency cleanup touched it; `transcript_source` is the cleaned text,
which is the one shown and the one confirmed. Keeping both is what makes the model's
removals inspectable — a human cannot be the last word on a sentence they were never shown.

> Once a human has confirmed a row, the gap between the two columns is the cleaner's
> removals **and** the human's edits at once, and no column records which is which.
> Rendering that diff as "what the model removed" after a confirm attributes a
> facilitator's own corrections to a model. Equality between the two columns has three
> possible causes (the cleanup fell back, it found nothing to remove, or a human confirmed
> text that matched) and cannot tell them apart on its own.

### 2.2 Bulk confirmation is one human attesting to N drafts — never an automatic pass

**There is no bulk endpoint, and there must not be one.** The API confirms exactly one
answer per call, and each call carries the `generation` the client last read for *that*
answer, which makes the confirm a compare-and-swap.

"Confirm every transcript" is therefore N individual acts, made by a person who was shown
what they were accepting and clicked through a dialog that says so. An endpoint that
confirmed a whole session in one statement would look like the same feature and would not
be: it would flip drafts to confirmed with no human having read a single one, and there
would be nothing on the rows afterwards to tell the two apart.

The compare-and-swap is what enforces this. A facilitator whose draft was re-transcribed
underneath them is refused (`409 CONFLICT`) rather than allowed to write an edit of text
that no longer exists — because what they hold is a human's edit of superseded text, and
merging that blind is how a correction lands on the wrong answer.

### 2.3 The English is never the client's to send

The confirm body carries only the spoken-language text. The English is re-derived
server-side, inside the request, from what the human just confirmed. This is the entire
reason the confirm is a route at all rather than a plain field write: the report reads
`translation_en`, so a correction the client applied on its own would leave the corrected
Portuguese standing next to the English of the sentence it replaced — which reads as a
translation and is not one. Both fields are written in one statement, so the pair can never
be half-updated.

### 2.4 The bytes are opaque, in both directions

Voice answers and artifacts are moved, never parsed. Artifacts travel as raw multipart
bytes on upload and are served straight from storage by redirect on download — the API
never proxies them, because a proxy would have to choose an encoding and any choice is a
chance to be wrong. A parsed-then-reserialized artifact is a broken one even while it still
looks like perfectly valid JSON, and the downstream pipeline diffs these files byte for
byte.

### 2.5 Every reach for a recording is recorded; making one is not

Issuing a signed URL for a voice answer writes a `voice_url_issued` row, and the commit is
what returns the URL — nothing hands out a link without a row naming who got it. Recording
an answer writes no audit row on purpose: reaching for a voice already recorded is the
facilitator action the audit rules ask about, and logging the listener at work is the
surveillance they forbid.

The event names all say `ISSUED`, which is the whole of what this API can honestly claim: a
signed URL may be used once, ten times, shared, or never opened, and the API never witnesses
it. `artifact_uploaded` is the only event here that claims a transfer, and those bytes
really do come through the API.

---

## 3. The HTTP surface

All nine operations sit under `/api/sound-necklace`, require a Sound Necklace role
(`app/api/sound_necklace/_deps.py`), and check project membership on the session.

### 3.1 Voice answers — `app/api/sound_necklace/resources.py`

`path` is a query parameter everywhere and is validated against a closed allowlist
(`RESOURCE_PATH_PATTERN` in `app/models/sound_necklace.py`), which is what lets it be
trusted verbatim as the object-name suffix — no traversal, no free-form key:

```
respostas/level1/<key>.webm
respostas/level2/PT<n>/<key>.webm
respostas/level3/P<n>/<key>.webm
```

| Operation | Body in | Body out |
|---|---|---|
| `PUT /sessions/{session_id}/resources?path=…` | raw `audio/webm` bytes | `201 {path, size}` |
| `GET /sessions/{session_id}/resources` | — | `{resources: [{path, size}]}` |
| `GET /sessions/{session_id}/resources/url?path=…` | — | `{url}` |
| `DELETE /sessions/{session_id}/resources?path=…` | — | `204` |

- The upload replaces any previous take in place: the storage key is a pure function of
  session and path, so a re-record lands on the same object and updates the one row.
- `413` above `MAX_VOICE_ANSWER_BYTES` (10 MiB), checked from the body before anything
  reaches the bucket; `422` for a path that does not match the allowlist. Two statuses so a
  client can tell "too big" from "wrong path".
- The signed URL expires in `DOWNLOAD_URL_EXPIRY_MINUTES` (15) and writes the audit row.
- Deleting a path that was never recorded is a no-op, not an error. The object is deleted
  before the row, deliberately: if the commit then fails, what survives is a row pointing
  at a missing object — a playback that 404s until a retry heals it. For audio under LGPD
  that is the safe direction to fail; the reverse would leave the recording in the bucket
  with nothing left to reach it.

### 3.2 Transcription — `app/api/sound_necklace/transcriptions.py`

| Operation | Body in | Body out |
|---|---|---|
| `POST /sessions/{session_id}/transcriptions` | `{language, force?, paths?}` | `202 TranscriptionProgress` |
| `GET /sessions/{session_id}/transcriptions` | — | `TranscriptionProgress` |
| `PUT /sessions/{session_id}/transcriptions/{resource_path}` | `{transcript_source, generation}` | `AnswerTranscript` |

```jsonc
// TranscriptionProgress — the same body from the trigger and from the poll, so the
// trigger's reply is already the first frame of progress. "done" is pending === 0.
{
  "total": 12, "ready": 9, "failed": 1, "pending": 2,
  "answers": [ /* AnswerTranscript */ ]
}

// AnswerTranscript
{
  "path": "respostas/level2/PT3/nome.webm",
  "status": "pending" | "ready" | "failed",
  "transcript_verbatim": "…",   // before the disfluency cleanup; null until ready
  "transcript_source":   "…",   // the text to show and to confirm
  "translation_en":      "…",   // English whatever the interview language was
  "error": null,                // this answer's own failure; never the job's
  "generation": 3               // required — the compare-and-swap counter
}
```

- `language` is a BCP-47 locale and is the client's to state: the session row does not
  carry one, and only the client knows which language the questions were asked in. It is
  the transcriber's hint and the switch that decides whether a translation is needed at all.
- `force` re-transcribes; `paths` narrows it to the answers named. Omitting `paths` means
  the whole session, which is what a re-opened report still asks for. Naming the
  re-recorded answer is what keeps one repeated take from costing a session of
  transcriptions.
- The `POST` only enqueues. The pass itself runs in Inngest, off this process, so a deploy
  mid-session does not strand it, and the provider key never has to leave the server.
- The confirm is **synchronous** instead, because it is one answer's worth of work and the
  person who typed it is waiting on the result.
- The confirm's `409` carries a `code` and the client must tell three cases apart:
  `SESSION_LOCKED` (somebody else is editing — go to review mode),
  `SESSION_LOCK_CHANGED` (the lease refused the write and then lapsed — just retry) and
  `CONFLICT` (the draft was rewritten under you — only re-reading helps; a retry sends the
  same superseded generation and loses again).

### 3.3 Artifacts — `app/api/sound_necklace/artifacts.py`

| Operation | Body in | Body out |
|---|---|---|
| `POST /sessions/{session_id}/artifacts` | multipart: `manifest`, `anchoring`, `report` | `201 [{kind, size, crc32c, sha256}]` |
| `GET /sessions/{session_id}/artifacts/{kind}` | — | `307` to a signed URL |

All three files are **required in one request**. There is no partial upload, which is why
this pair went dormant whole: the client that stopped producing a report stopped being able
to call the route at all. Completing a session (`POST /sessions/{id}/complete`) does not
depend on it — that route is part of the live surface and stays there.

`kind` is the handle; the stored filenames are frozen by the product spec and stay
Portuguese, because the downstream pipeline reads them by name:

| kind | filename | content type |
|---|---|---|
| `manifest` | `manifesto-contas.json` | `application/json` |
| `anchoring` | `retorno-ancoragem.json` | `application/json` |
| `report` | `relatorio-mapeamento.md` | `text/markdown; charset=utf-8` |

`crc32c` is the checksum GCS itself validated on the way in — a corrupt upload is rejected
by storage and the object is never created. `sha256` is ours, so the audit trail does not
depend on trusting the storage provider. The storage key is content-addressed (the sha256
is in the path), so a re-upload never overwrites: a failure partway through three
overwrites would otherwise leave the bucket holding a triple that never coexisted while the
database still described the old one.

### 3.4 The batch job — `app/inngest/sn_transcription.py`

```
fn_id       transcribe-session-answers
trigger     sn/transcription.requested          payload: {session_id}
concurrency key=event.data.session_id, limit=1
retries     3
```

The concurrency key is what makes it safe to trigger twice: one run per session at a time,
across every instance. Without it two runs would read the same `pending` rows and pay the
provider twice for the same answer. The payload carries the session id and nothing else —
the work to do is whatever is `pending` when the run starts, so a replayed event never
redoes a draft and never carries a stale copy of one.

There is no `on_failure` hook, on purpose: a failure that reaches that level is
infrastructure — the database or the bucket — never one answer's. Per-answer failures are
already `failed` rows, and a retry simply re-reads whatever is still `pending`.

---

## 4. The tables

Both are still in place and still migrated. They stop receiving new rows; **no row was
deleted and none should be.** Production data is out of scope for the cut.

### `sn_voice_answers`

| Column | Type | Note |
|---|---|---|
| `session_id`, `resource_path` | PK | one file per question; re-recording replaces in place |
| `storage_key` | `varchar(512)` | the object in `sound-necklace-private` |
| `size`, `content_type` | | `audio/webm` |
| `created_at`, `updated_at` | | |

The bytes are not here — the row is the queryable pointer. The listing is what tells a
screen which questions already have an answer, which is why the answers are a table and not
just a bucket prefix: a prefix listing is an extra round trip and cannot be joined or
scoped in one query. FK to `sn_sessions` is `ON DELETE CASCADE`.

### `sn_answer_transcripts`

| Column | Type | Note |
|---|---|---|
| `session_id`, `resource_path` | PK | composite FK to `sn_voice_answers`, `ON DELETE CASCADE` |
| `status` | `pending` \| `ready` \| `failed` | these rows *are* the job's state |
| `language` | `varchar(16)` | the interview language, as the trigger sent it |
| `generation` | `int` | the compare-and-swap counter |
| `transcript_verbatim` | `text` | before the disfluency cleanup |
| `transcript_source` | `text` | what is shown, and what a human confirms |
| `translation_en` | `text` | English whatever the interview language was |
| `error` | `text` | this answer's own failure |
| `created_at`, `updated_at` | | |

There is no `running` status by design: a claimed-but-unfinished state survives a crashed
worker as a row nothing will ever move again, and the cure (a sweeper, a heartbeat column)
costs more than the disease. Delete or re-record an answer and its draft goes with it,
with no cleanup code to forget.

`sn_artifacts` also stops receiving rows while the client produces no artifacts, but it is
listed here as the package's storage rather than as one of its two tables: it is written by
the artifact routes above and read by nothing else.

> **A note for a Postgres reader.** The three status/kind enums are real Postgres types
> (`sn_transcript_status_enum`, `sn_artifact_kind_enum`). The test suite runs on SQLite,
> where enums are invisible — adding a value needs an `ALTER TYPE` in a migration, and
> forgetting it breaks in production while every test stays green.

---

## 5. What is shared, and what is the package's own

**Its own** — the twelve modules that carry the `DORMANT` header, and nothing else:

```
app/api/sound_necklace/       transcriptions.py  resources.py  artifacts.py
app/inngest/                  sn_transcription.py
app/services/sound_necklace/  transcribe_answers.py   retranslate_answer.py
                              store_voice_answer.py   delete_voice_answer.py
                              list_voice_answers.py   voice_answer_url.py
                              store_artifacts.py      artifact_download_url.py
```

**Shared, and out of this package's reach.** These have other consumers today, verified by
grep on 2026-09-01. Cutting the Colar's client frees none of them, and it does not free the
vendor key either:

| Module | Who else uses it |
|---|---|
| `app/services/platform/stt.py` | `app/api/platform/stt.py` (a live public route), `services/internalization_room/questions.py` |
| `app/services/platform/tts.py` | `app/api/platform/tts.py`, two routers and two services in `internalization_room`, `services/translation_helper/synthesize_speech.py` |
| `app/services/platform/disfluency.py` | `app/api/platform/stt.py` |
| `app/services/platform/voices.py` | `platform/tts`, `platform/stt`, `platform/translation`, `platform/disfluency` |
| `app/services/oral_collector/gcs_utils.py` | every product in this repository that touches a bucket |
| `app/services/sound_necklace/lock_fence.py`, `record_audit_event.py`, `get_session.py`, `constants.py` | the live Colar surface — sessions, autosave, audio, consent, audit, locks |

There are also two further ElevenLabs clients copied elsewhere
(`services/project_health/voice/elevenlabs_client.py`,
`services/translation_helper/transcribe_audio.py`) that do not go through `platform/` at
all. They are named here only so nobody counts the vendor's callers by reading
`platform/`.

> **One finding, recorded and not acted on.** `app/services/platform/translation.py` has
> exactly two importers — `transcribe_answers.py` and `retranslate_answer.py` — both inside
> this package. It is therefore the one module under `platform/` that has no caller left
> after the cut. It was deliberately **not** touched: `platform/` is shared ground and this
> slice does not write there. Whoever picks the package up should know it is effectively
> part of the package's dependency surface, not a general-purpose service with other users.

### The rest of the Colar's API is alive

Sessions, autosave, audio listing, acoustemes, consent, audit, locks and project settings
are untouched and still in daily use — that is where the cuts keep being saved, which is
the whole point of the scope cut. Do not read this document as covering them.

---

## 6. What is missing to use this elsewhere: the client

Everything the server needs is here and works. What does not exist is anything calling it.
A system that wants to host the interview has to bring:

1. **A recorder and an uploader.** Something that produces one WebM/Opus file per question
   and `PUT`s it at a path matching `RESOURCE_PATH_PATTERN`. The path shape is currently
   the Colar's question taxonomy (`level1` / `level2/PT<n>` / `level3/P<n>`); a different
   taxonomy means widening that allowlist in `app/models/sound_necklace.py`, and it is the
   one place where this package is coupled to the product it came from.
2. **A poller.** `POST` once, then `GET` until `pending` is 0. There is no push, no
   websocket and no `done` flag — `pending === 0` is the flag. A `failed` answer is shown
   as failed and does not block the rest.
3. **A screen where a person reads each draft and confirms it.** This is the part that
   cannot be automated away without changing what the package is (§2.1, §2.2). It must show
   the text before it is accepted, and it must send back the `generation` it read.
4. **Whatever composes the artifacts**, if the new system wants the artifact routes at all.
   The API stores three opaque files and gives them back byte-identical; it has never known
   what is in them.
5. **A session.** All of this hangs off an `sn_sessions` row and its project, and reuses
   the Colar's roles and its advisory editor lock. A system outside the Colar either
   creates sessions the same way or needs that coupling looked at first — it is the largest
   piece of work in reusing this package, and it is not addressed here.

What it does **not** have to bring: the provider key, any transcription or translation
logic, the idempotency, the retry policy, or the audit trail. Those are the parts that were
expensive to get right.

---

## 7. Where to look next

| You want | Read |
|---|---|
| Whether the routes are still mounted | `tests/test_sound_necklace/test_contract.py` |
| How a draft behaves under `force` and failure | `tests/test_sound_necklace/test_transcriptions.py` |
| What the confirm guarantees | `tests/test_sound_necklace/test_retranslate.py` |
| Byte-identity of the artifacts | `tests/test_sound_necklace/test_artifacts.py` |
| The job's concurrency and retries | `tests/test_sn_transcription.py` |
| Why the model steps on this path are limited to three | [`CLAUDE.md` §9](../CLAUDE.md) |

---
status: accepted
date: 2026-09-30
---

# A resend under one Idempotency-Key replays the answer that settled it, and nothing else

A telling sent to the chunk door, or a **Correction**, whose answer is lost on a weak link is sent again by the tablet, and the room counted it twice: a second stretch, or one more telling of a stretch already retold. Takes were already safe by their audio hash and turns by `turn_id`; these two doors had nothing.

Decided: the two doors read an optional `Idempotency-Key` header, and one generic table keyed by (key, route) holds the request's hash, the answer's status and body, and the moment the key was claimed. No foreign keys, like the room's other tables.

- No header: the door behaves exactly as before.
- The first request under a key writes a claim row and commits it **before** any work, on a session of its own, so a second Cloud Run instance sees it. The claim is never part of the door's own transaction.
- Same key, same hash, answer settled: the stored status and body are answered again and nothing is written.
- Same key, another hash: 422 `IDEMPOTENCY_KEY_REUSED`, checked before anything else.
- Same key, first request still running: 409 `IDEMPOTENCY_KEY_IN_FLIGHT`.
- **Only an answer that settled the request is stored**: a 2xx, or a 4xx other than 429. A 5xx, a 429, an unhandled error or a cancelled request deletes the claim, so the tablet's resend (ADR 0040: a transcriber down is resent) is handled anew instead of replaying a failure for a day.
- A claim with no answer after 300 s, Cloud Run's request timeout, was abandoned by an instance that died before it could delete it; the next request under that key takes it over. The late owner, if it ever finishes, can neither overwrite nor delete the taker's row.
- A key older than 24 h is forgotten on the next read and the request is new. Nothing sweeps the table.
- The hash covers the path parameters, the form fields and the bytes of the audio, never the multipart boundary, so the same key on another session or stretch is a 422, never a replay.

The rule lives in one service; the doors reach it through a route class that wraps them, because a refusal becomes a status and a body only in the exception handlers, which run inside the route's ASGI app and never in the route function. The answer is stored before it is sent, so a tablet that saw it can always have it again.

Rejected: an in-process registry like the turn's, because it does not hold across instances; storing every first answer, because a 502 would be replayed for 24 h; a per-route field, because the same rule will reach other doors.

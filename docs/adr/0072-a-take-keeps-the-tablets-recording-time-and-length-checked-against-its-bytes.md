---
status: accepted
date: 2026-10-19
---

# A take keeps the tablet's recording time, and its length checked against its bytes

In her app every take carries its fingerprint, size, duration and the time it was recorded, read
off the recording device's own clock (`src/draft/store.ts:54-87` at her freeze 18fa7c4). Ours
kept no duration and served the upload time as the recording time, which is hours late when the
tablet's queue drains. And two uploads of the same bytes at once under two content types wrote
two rows, after which every resend of those bytes failed.

Decided (ENG-1273):

- The keep door and the scene rehearsal door take three optional form fields: `recorded_at`
  (an ISO-8601 instant with its offset; one without is FastAPI's 422), `duration_ms` and
  `sha256`. A take or scene rehearsal keeps them in `recorded_at` and `duration_ms`.
- The server still hashes and measures the bytes. A `sha256` that is not theirs answers 422
  `TAKE_FINGERPRINT_DIFFERS`; a `duration_ms` more than 100 ms from ffprobe's length answers 422
  `TAKE_DURATION_DIFFERS`; nothing is stored either way. Within 100 ms the tablet's value is
  kept as sent. The slack is the rounding of two readers of one file, never a different sound.
  When ffprobe cannot read the bytes within 3 s, the tablet's value is kept unchecked, or none.
- The **Recording time** is the tablet's for a take recorded on it, and the server's for a
  joined part (her ruling of 24 September), for a part spliced by a re-recorded sentence and for
  a take sent with no time. It is written once and never moved: a resend answers with the row
  already kept.
- A joined part's tablet time measures the **Clock offset** instead: tablet minus server at
  storing, kept on `device_clock_offset_ms` only at five minutes or more (her
  `CLOCK_SKEW_NOTE_MS`), served on the consultant's read alone. The tablet stamps that time when
  it builds each send, so the offset measures a clock and not a queue's delay.
- A partial unique index on `(session_id, kind, sha256)`, skipping the declared parts' empty
  hash, makes one session hold its bytes once. The first row wins; an upload that loses the race
  answers with it.
- The packet's takes carry `duration_ms` and the recording time; `schema_version` is v0.8.

Rejected: **the server correcting a mismatched value**, because the tablet would believe a take
described by numbers that are not its own; **trusting the tablet's sha256 without hashing**,
because the checksums describe the stored bytes, not the promised ones; **measuring the offset
from the time minted with the recording**, because that says how old the recording is as much
as how wrong the clock is (her `clockSkew.ts`).

Consequences: a passage approved before the deploy and approved again after mints its next
version, as every schema bump did. A tablet that sends a length it did not read from the file
loses the take, since its queue gives up a coded refusal for good: the tablet sends one only for
WAV. Takes stored before carry their upload time and no length. The listening rule still reads
the length the tablet reports with each listen (ADR 0070); the stored one is for Refine and the
consultant.

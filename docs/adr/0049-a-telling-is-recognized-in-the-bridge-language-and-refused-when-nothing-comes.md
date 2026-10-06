---
status: accepted
date: 2026-10-06
---

# A telling is recognized in the bridge language within fifteen seconds, and refused when nothing comes

**Supersedes in part [ADR 0040](0040-a-telling-with-no-words-is-refused-and-is-never-a-stretch.md).**
Its refusal of a telling with no words stands, and so does keeping the retro take. Two of its
clauses end here: "an outage stays a 502 the tablet sends again", and "the replace route's
empty re-recording still counts in place".

The two telling doors, the chunk door and the replace door, let the transcriber guess the
language, so a Portuguese telling came back as phonetic Spanish, and let it take up to two
minutes. Her own app has always sent the session's language and stopped waiting after fifteen
seconds, and answered "nothing heard" for any failure.

Decided:

- **The bridge language is sent, never guessed.** Both doors recognize a telling in the
  session's `language` (`pt` or `en`), sent to the transcriber as `language_code`. A caller
  that passes no language, such as the translation helper, still detects, unchanged.
- **The recognizer gets fifteen seconds.** The bound lives in `heard`, the only hearing the
  two doors use.
- **No words, a failure and the bound read the same.** An empty or annotation-only transcript,
  a transcriber failure (an outage, a 5xx, an unreachable host, a missing key) and a late answer
  are all "nothing made out". Both doors refuse the telling with 422 `WORDLESS_TELLING`, with
  **no spoken line**: `fixed_line` leaves the body, and the tablet shows its own line and asks
  for the stretch again. A defect of ours is still not swallowed.
- **The replace door refuses too, and counts nothing.** An empty Correction leaves the
  standing stretch as it was: same row, same transcript, same count of tellings, no hard-stretch
  mark. The in-place count retires with `count_an_empty_telling`, and
  `SegmentsResponse.captured` goes with it, since the replace door can no longer answer
  `captured: false`.
- The retro take is still stored before the hearing and stays stored on every refusal.

A refused telling settles under its idempotency key like any 422, so a resend is answered the
same; a new telling is a new key.

Rejected: keeping the 502 for an outage. The tablet cannot tell it from a dropped network and
resends the same recording, where the refusal tells the team to say it again. The cost is that
an outage no longer reaches the warning count; nothing counts on these doors, by choice.

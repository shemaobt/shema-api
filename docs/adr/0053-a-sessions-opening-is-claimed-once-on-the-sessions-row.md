---
status: accepted
date: 2026-10-06
---

# A session's opening is claimed once on the session's row

The turn door replayed a stored answer only by `turn_id`, and its in-flight registry joins a
request only to another one in the same process with the same turn id. Two tablets asking a new
session for its opening carry different turn ids, so each asked the Guide and each voiced a
line. The second line was dropped from the record, but its tablet still heard it. A team turn
that arrived while the opening was being drafted ran at once on an empty conversation. Either
it landed first and the opening was dropped, or the opening landed first and the team turn lost
the version guard. In her app the opening is claimed once with a write-once lease
(`src/session/leases.ts`). ENG-1451 brings that rule to the server.

Decided by the Definer with Henok on 2026-10-06 (Q14 and Q15 recorded on the ticket):

- The no-audio request on a session with no messages claims the opening before any Guide
  call, prepared line or synthesis. The claim is two nullable columns on `ir_sessions`: the
  turn id the holder's answer will be stored under, and the time of the claim. One conditional
  `UPDATE … WHERE` writes them, only while no live claim stands. It is committed on its own. A
  request without a turn id claims under the id its answer will carry, so a claim always names
  an answer that will be stored. The holder stores that answer in the opening's own commit.
- The claim is not the team's activity. It leaves `version` and `updated_at` as they were.
- A request that loses the claim drafts nothing. It looks once a second (her
  `KICKOFF_POLL_MS`) for the answer stored under the claimed turn id, up to the turn bound,
  each time on a session of its own. If the answer is found, it answers with it, under its own
  turn id. If the claim is gone or the bound passes, it answers the error of a turn that did
  not answer, and writes nothing. The tablet's next request claims anew (Q15, her 409).
- A holder that ends without an opening releases its claim. The release is guarded on its own
  turn id, so a late holder never clears the claim of a request that took over (ADR 0043's
  rule). The error then propagates unchanged.
- A claim older than the turn bound plus 30 s (her `KICKOFF_LEASE_TTL_MS`, 330 s against
  `maxDuration` 300) belongs to a request the deployment has already killed. It counts as no
  claim. The next request takes it over in the same conditional update.
- A team turn with audio, on a session with no messages and a live claim, waits until the
  claimed answer is stored, until the claim is released, or until 90 s after the claim (her
  `KICKOFF_WAIT_MS`, the setting `internalization_room_opening_wait_ms`). Then it reads the
  session again and runs on the conversation that now holds the opening. Its own turn bound
  starts after the wait (Q14). Cloud Run's `--timeout=300` is the request's whole life, so a turn
  that waited and then ran long can be cut by the deployment before its own bound. That is
  accepted: the wait is at most 90 s, and a turn legitimately runs to about 56 s. Transcription
  runs during the wait. A wait that ends without an opening runs on the empty conversation, and
  the late opening is then dropped, as before.
- `hand_over` moves a prepared line only onto a session with no messages. The open door returns
  the team's resumed session (ADR 0045), and a line parked there is never read. The panorama
  keeps its copy, as it does for the other three refusals.

Rejected:

- A claim table keyed by session (ADR 0043's shape). The team turn has to check the claim on
  every turn, and on the row it is read off the session already loaded, with no extra query.
- `SELECT … FOR UPDATE`. It does nothing on SQLite, where the suite runs. Held across the Guide,
  it would pin a pooled connection for up to the whole turn bound, against the door's own
  release of the connection before the model call.
- The in-process registry `answer_once` keeps. The service runs on Cloud Run with no
  `--max-instances`, so two tablets can reach two instances that never see each other's
  registry. The registry would be correct only while the service is held to one instance.

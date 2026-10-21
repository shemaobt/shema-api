---
status: accepted
date: 2026-10-21
---

# Every turn of a session takes the turn claim, and a wait past 90 s is a collision

ADR 0053 claimed a session's opening on its row. Team turns took no claim. Two turns sent to one
session at nearly the same moment each read the session and ran the Guide, and the later one to
land was refused by `_land`'s version guard with `CONFLICT`, so that tablet called a person for
a turn it had every right to send. Four holes in the opening claim stood beside it. A
request still waiting on a claim whose holder had died polled until its own deadline, then
answered 502. The release matched the turn id only, so a stale holder cleared the claim of a
resend that had taken it over under the same id. Nothing cleared the claim after the opening
landed. A resend of a turn id on another instance that missed the stored answer at the door
ran the Guide again and appended a second exchange. In her app the second turn moves after the
other reply, or is refused quietly when the server cannot tell (ENG-1392).

Decided by the Definer with Henok on 2026-10-19 and 2026-10-21, and with the Orchestrator on
2026-10-21 (recorded on the ticket):

- ADR 0053's claim becomes the **Turn claim**, the same two columns and the same conditional
  `UPDATE`. Every turn that writes the conversation takes it: the opening, a team turn and a
  scene rehearsal's «terminei». Asking for the last line again takes none. The claim is
  taken under the turn id the answer will be stored by, minted for a tablet that sent none,
  so every claimed answer is stored under the claim's id.
- Turns are answered in the order they arrived. The claim is taken on arrival, while the
  team's words are still being heard, so a long recording sent first is answered before a
  short one sent after it, and the second reply reads the first. The ticket's acceptance asks
  for exactly that. A claim is therefore held through its own transcription, and a waiter
  hears its words during the wait. (The Orchestrator first had the words heard before the
  claim; send-back 1 withdrew it, because the shorter recording then went first.)
- The request that wins reads the session again before the Guide, so it runs on the
  conversation with every reply that landed before it. Then it looks for an answer already
  stored under its own turn id. A run of the same turn on another instance may have landed
  between the door's own look and the claim, and the stored answer is then the reply. No test
  can stop a request inside that window, so this look has no witness of its own.
- A claim whose answer is already stored under its turn id is no claim, as one older than the
  turn bound plus 30 s is not. That is what ends a claim on success: the answer is stored in
  the turn's own commit, so a waiter sees the reply and the free claim in the same instant.
  An older instance never cleared its opening's claim, and a deploy leaves one on every
  session opened in the minutes before it; read this way it holds nobody up.
- A request that loses the claim loses it one of three ways:
  - A request for the opening answers the holder's stored answer, as ADR 0053 has it.
  - A request under the holder's own turn id is a resend on another instance. It answers that
    turn's stored answer, never running the Guide twice, or a turn that did not answer when
    its own bound passes.
  - Any other turn waits for the holder's reply, then claims again. Its wait ends at the
    first claim it saw plus 90 s (`internalization_room_opening_wait_ms`, her
    `KICKOFF_WAIT_MS`), however many holders follow one another. Past that it is refused
    `TURN_COLLISION`, 409, with nothing stored and nothing voiced: the server cannot place it.
    A turn waiting on the opening keeps ADR 0053's rule instead and runs on the conversation
    as it stands (the Definer, 2026-10-21). It takes the claim from the opening first, so the
    turns after it wait on a turn of the team, never on the late opening, which is then
    dropped from the record. Which holder is the opening is decided by the claim, with no new
    column: a holder first seen on a session still empty claimed it for the opening, because
    no turn of the team writes a message without first taking the claim.
- A request that waited gets its whole turn bound from the moment it wins (ADR 0053, Q14).
- When the waited-on turn fails, its claim is released and the waiter runs on the
  conversation as it stands. A claim that dies while it is waited on is claimed again.
- A holder that ends without an answer releases its claim, guarded on its turn id and its
  claim time, as the scene send's release is (ADR 0063). A stale holder therefore never frees
  a claim a resend took over under the same id.
- The verdict round and the release take no claim. `_land`'s version guard stays the backstop
  for them and for an older instance during a deploy.
- The columns and the setting keep the opening's names.
- No statement of the app waits on Postgres for ever. Every transaction of the app's engine
  sets `lock_timeout` to 30 s and `statement_timeout` to 1 min. 30 s is inside the 90 s
  wait and past a back-translation frase uploaded on a slow link, which holds the session's
  row through two uploads to the bucket (the Orchestrator, 2026-10-21). 1 min is a starting
  value: the longest statement in production was not measured. Production reaches Neon
  through its pooler, which hands the server connection to another client between transactions and
  keeps nothing a connection was started with, so the two are set per transaction with
  `set_config(…, true)`, in one `SELECT` when the transaction begins (Henok, 2026-10-21). On
  a local Postgres that round trip measured 0.05 to 0.07 ms a transaction, the medians of
  two sets of three runs of 500; on Neon it is one more network round trip a
  transaction. A row lock held elsewhere refused the app's `UPDATE` at 30.0 s. SQLite runs
  none of it, and Alembic's own engine is untouched: a migration may legitimately run long.
  The migrations job checks it against its own Postgres.

Rejected:

- A quiet refusal of every concurrent turn (Henok, 2026-10-19). The second tablet's turn would
  be lost every time two tablets speak close together, where waiting places it.
- `SELECT … FOR UPDATE`, for ADR 0053's reasons.
- Renaming the columns. It is a migration on a database six apps share, and during the deploy
  the older instances still read the old names.
- A wait bound counted per holder. Behind a chain of holders it has no end, and the tablet gives
  up on its turn at 305 s.
- The two waits as startup parameters of the connection. The pooler does not carry them.
- `ALTER ROLE … SET` for the two waits. It reaches every app that connects as that role.
- Clearing the claim in the turn's own commit. It covers no claim an older instance left, and
  it reaches every draft of the turn door and the scene door for what one more condition on
  the claim's update does.
- Hearing the team before claiming. A claim is then never held through a transcription,
  but the turn that is heard first goes first, and a short recording sent second is answered
  before a long one sent first.

Consequences:

- A team turn behind another team turn on a session still empty is taken for one behind the
  opening, and at the bound takes the claim and runs instead of being refused. A tablet asks
  for the opening first, so that session is rare.
- A turn running past 90 s has the other tablets' turns refused until it lands, fails or dies.
  A turn legitimately runs to about 56 s. A holder killed with its instance is such a turn:
  its claim stands until it is dead, 330 s after it was taken, and every other turn that
  arrives more than 90 s after it is refused at once.
- A release that is itself refused, a lock held past 30 s, replaces the turn's own error and
  leaves the claim standing until it is dead, with the same effect.
- A turn sent without a turn id now leaves an `ir_turns` row under the minted id.
- After a turn, the claim's columns still name it. Only the claim reads them.
- Probes that must go red: team turns skipping the claim (the turn and scene cases); the bound
  counted from arrival; running instead of refusing at the bound; no re-read after winning;
  hearing before claiming; without the stored-answer condition on the claim,
  the case of two turns at nearly the same moment; the release on the turn id only; no dead
  check while waiting; a resend treated as another tablet's turn; the refusal's handler
  unregistered; the per-transaction waits unregistered (the migrations job's check).
- Every user of the app's engine, scripts included, now has a statement cut at 1 min.

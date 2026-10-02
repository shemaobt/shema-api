---
status: accepted
date: 2026-10-02
---

# The open door returns the team's latest session of a pericope and language, created once

The room's open door minted a new session on every open, unless the tablet remembered one. A
second tablet, a reinstall or a lost local memory started the team over, two tablets on one
pericope never saw each other's conversation, and two tablets could both play the Panorama
opening. ENG-1236 makes the server the authority: every open returns the session it holds for
that team, pericope and language, whatever its state, and creates one only when none exists,
however many opens arrive at once.

Decided with the Orchestrator under Henok's standing rule on 2026-10-02:

- "Only when none exists" is the database's promise, not a read before the write. A pointer
  table keyed by team, pericope and language names the session the door returns. An open that
  finds no pointer mints its session and claims the key in the same transaction with
  `INSERT … ON CONFLICT DO NOTHING`, then reads the key again. An open that lost the claim
  deletes the row it minted before anything is committed and returns the winner's session, so
  no orphan is left. The row is deleted rather than the transaction rolled back, because a
  rollback expires every row the request already read.
- The pointer is its own table, not a unique index on `ir_sessions`. Teams already hold several
  sessions of one pericope from before this rule, and those stay in history: an index would
  have to delete or rewrite them first. The migration backfills each key with the latest
  session the team entered (the **Entered** rule: a turn, a take or a halt), by `updated_at`,
  then `created_at`, then `id`, and with the latest of any kind only when it entered none. The
  old door minted a session on every relaunch that the tablet then left empty, so the newest
  row of a key is often a launch nobody entered; pointing at it would hand the team an empty
  conversation for good.
- A key with no pointer but with stored sessions claims the latest of them, by the same rule,
  instead of minting. That covers a key the backfill left without a pointer, when a server
  still running the old door writes its first session during the rollout. A key the backfill
  already pointed keeps its pointer.
- No foreign key from the pointer to the session, as on every room table (ADR 0006).
- A caller with no team, on the shared room key, is minted a session on every open as before:
  without a team there is nothing to resume. The text seam and the test builders keep minting.
- The Panorama follows the same rule. A team that chooses to hear it again is returned the
  Panorama session it already has; replaying it belongs to ENG-1280. The opening is prepared
  only by the open that created the session.
- A resumed session is returned as it stands, except the panorama mark: an open that came from
  the Panorama sets `after_panorama` on the session it lands on. Without that, a pericope opened
  before the Panorama would never count the Panorama as heard, and it would play at every
  launch.

Rejected: a unique constraint on `ir_sessions` (above), and an advisory lock or
`SELECT … FOR UPDATE` around the open, which the repository uses nowhere and which a unique key
makes unnecessary.

---
status: accepted
date: 2026-10-06
---

# Every Guide turn keeps every Validator attempt in the conversation

A turn drafts up to `MAX_REDRAFTS + 1` times, and the loop kept only the last draft, the last
verdict and a count. Only a fail-safe stored them. A consultant reading a turn back (ENG-1332,
served by ENG-1199) could not see what the Guide first drafted, what the Validator refused and
why, or what it corrected. ENG-1200 keeps all of it.

Decided by the Orchestrator on 2026-10-06, from Marcia's `src/turn/turnLoop.ts`:

- Every guide entry in `IRSession.messages` from a turn that asked the Validator, the Guide's or the Speaker's, carries
  `attempts`, oldest first, one per draft the Guide produced. The column is JSON, so there is no
  migration.
- An attempt holds `attempt` (1-based), `draft`, `issues` (each only the Validator's `problem`, `claim`
  and `explanation`, as text; none when the reply could not be read), `verdict` (absent when no reply could be read), `corrected`
  (only on `correct`) and `note`, the attempt note (only when the room has something to say).
- The attempt note is the room's, never the Validator's, and fixed English: one for a reply that could
  not be read. An ordinary attempt has none. A draft that came back empty never reaches the
  Validator, and is kept as an attempt with its empty draft and nothing else. This is Marcia's rule (`src/turn/turnLoop.ts`: the harness writes the note,
  only when something went wrong, and her Validator returns none).
- Every outcome keeps its attempts: pass, correction, redraft, fail-safe. The fail-safe is not an
  attempt of its own; it is already on the turn (`outcome`, `category`, `fixed_line`).
- The fail-safe entry's `issues` are narrowed the same way: problem, claim and explanation as text,
  where it used to store the Validator's rows whole. A reply with a bare `NaN` or an extra field
  broke Postgres `json` at commit, and a turn that had passed would have failed. The narrowing is
  intended; `draft` and `verdict` there are as before.
- Turns stored before this change are not back-filled. Nothing reads `redrafts` or the old
  fail-safe `draft`, `verdict` and `issues` into attempts, so an entry without `attempts` is a
  turn that kept none.
- A prepared opening keeps its attempts too: they wait on the panorama's row beside the line
  (`prepared_attempts`, one nullable JSON column), move with it on hand-over, and are stored
  on the opening when the line is taken.
- Nothing about what is drafted, judged or spoken changes. The extra keys never reach a model
  prompt (the Validator is shown `text` only) and no tablet-reachable route or model carries them.

Rejected:

- A table of attempts. The consultant reads them with the turn, never alone, and the entry
  already holds the turn's other facts.
- An attempt note written by the Validator. It would be one more field a model can get wrong, and the
  thing the note says is a fact the room knows and the Validator cannot.
- Rebuilding attempts for old turns from `redrafts`. The drafts they would need were never kept.

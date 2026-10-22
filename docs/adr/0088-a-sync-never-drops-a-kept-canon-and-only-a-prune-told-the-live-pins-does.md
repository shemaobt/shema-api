---
status: accepted
date: 2026-10-22
---

# A sync never drops a kept canon, and only a prune told the live pins does

ENG-1511 made the canon sync copy the canon a re-pin replaces to `canon/kept/<old pin>/`, so a
live session keeps reading the canon it opened with. The same sync then dropped every kept tree
whose pin it was not given with `--keep`, the one it had just made included. The scheduled run
passes no `--keep`, so the first re-pin after a deploy would have committed the new canon and no
kept tree, and every live session under the old pin would have been refused `CANON_NOT_KEPT`
(ENG-1753).

Decided:

- `--sync` keeps the pin it replaces and removes no kept tree. `--keep` is removed: with nothing
  to drop, there is nothing to keep.
- A kept tree leaves only through `--prune --live-pins <file>`, run by hand from an up-to-date
  main checkout. It keeps every pin the file names and the deployed pin, and removes every other
  kept tree. The workflow runs `--sync` only.
- The file is the saved body of `GET /api/internalization-room/facilitator/canon-pins`, which
  answers `{"pins": [...]}`: every distinct canon pin of a session no Zerar archived, sorted,
  with null pins left out. The ticket spells the path `/internalization-room/canon-pins`; the
  house puts every Desk read under `/facilitator`, and the role-gate audit requires it.
- The read is behind `ReaderUser` and is not scoped to the reader's teams. A prune told one
  team's pins would remove the canon another team's live session reads. The pins are commits of
  a public repository and the answer is the same for every reader.
- The prune refuses, exits 1 and removes nothing when it has no file, when the file is not that
  read's answer (unreadable, not JSON, no `pins` list, an entry that is not a full sha), and when
  a live pin names neither a kept tree nor the deployed pin. That last file came from another
  environment or from a checkout behind production, and pruning on it would delete what the
  operator meant to keep.
- The suite checks that every canon pin a test fixture's `PROVENANCE.json` names is the deployed
  pin or a kept canon.

Rejected:

- Prune inside `--sync` with `--keep`. The scheduled run passes none, which is the bug.
- Never prune. Every kept tree would stay in the repository and the image for good, which is
  ENG-1511's complaint.
- The workflow reads production's pins itself. The ticket rules out reading the database from
  CI. The deploy job already reads production to hold a deploy while a team session is open, so
  a deploy-time guard on live pins remains possible as its own ticket.
- Scope the read to the reader's teams. It would make a partial file look whole.

Consequences:

- Kept trees build up between prunes: the repository and the image grow by about one vendor copy
  per compiler move.
- A session archived by a Zerar may lose its canon at the next prune, and the consultant's by-id
  read of it then answers 409 `CANON_NOT_KEPT`.
- The operator's file is the only source of truth for the prune. A file from the wrong
  environment that names only pins the checkout holds passes every refusal; the prune's pull
  request is the review that catches it.

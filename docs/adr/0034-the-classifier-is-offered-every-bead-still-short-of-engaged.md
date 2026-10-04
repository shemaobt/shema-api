# The classifier is offered every bead still short of engaged

## Context

After every exchange the classifier is handed the beads a turn may move. ENG-784 built
that offer from Marcia's eligibility rule — the beads not yet engaged that are either
scene-less or in the current scene — and fed it a **Scene pointer** the room derives from
the ledger: the first scene whose beads are not all engaged.

Her rule takes a third branch we do not supply. In `src/coverage/tracker.ts` a bead is
eligible when it is not engaged and is scene-less, or in the current scene, **or when
there is no current scene at all**. `currentScene` is handed to the tracker, never
derived by it: the only callers of `setScene` are her scripted runs, where each turn of
the script declares the scene it is in. Her live app never calls it — a session is
created with `currentScene: null` and rehydrated and persisted with whatever it held — so
in a live session every bead short of engaged is offered on every turn. Her note beside
the rule says why the narrowing exists at all and how settled it is: *"per-scene scoping
is the safe bias; tightening scene-progression is field-test tuning, M6."*

Deriving the pointer from the ledger and returning it to the ledger closes a loop she
does not have. A bead short of `engaged` holds its scene; the scene holds the offer; and
the offer is the only way that bead — or any bead of any later scene — could ever move.
On the by-hand test of 22 September a silence of the first scene stayed merely mentioned,
the Guide worked through all four scenes, and not one bead of scenes two, three or four
was ever offered.

## Considered Options

**A scene-advance rule of our own** — a scene releasing the pointer once all its beads
are at least mentioned. Rejected: the ledger is hers, the progression is hers, and this
would be an engineering default standing in for a ruling she has not made. It is also the
tuning she named and deferred.

**Holding the fix for a letter to her.** Rejected as the first move: the room stays shut
meanwhile, and there is nothing to ask while our own input is the divergence. If a scene
progression is ever wanted, that question goes to her then.

**Leaving the narrowing and making `done` arrive sooner.** Rejected: the completion floor
asks every concrete bead `engaged` — her Hard Rule #2 — so a passage whose silence was
only mentioned is correctly unfinished, and the trap would remain for every later scene.

## Decision

**What a turn may move is every bead still short of `engaged`.** The settle stops
deriving a scene pointer and stops handing one to the classification; the offer is the
whole unresolved necklace, scene-less beads and every scene's alike, which is what her
tracker answers when no scene is set — and none ever is, in a live session.

The pointer itself does not change and keeps its three readers: the Guide's ledger block,
the scene written on a turn's record, and the scene a rehearsal invitation is read
against. It is information, never scope. `remaining_in_scene` goes with the narrowing.

## Consequences

A bead can no longer be frozen by a bead in front of it: a team that leaves a silence
merely mentioned in scene one keeps earning the beads of every scene they go on to tell.

What the floor asks does not move. A session still does not close until every concrete
bead is engaged, and a room whose team never takes up a silence stays open — which is the
rule. The team's way out of the room is the record entry, open for the whole session,
not the ledger agreeing that the conversation is over.

The offer widens what one model call may mark, and the discard of ids that were not
offered no longer catches a bead from a scene the team has not reached. That is the bias
Marcia named, and the one she ships with; ours is now the same.

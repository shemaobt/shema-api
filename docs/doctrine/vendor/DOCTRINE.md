# The doctrine — what the Digital Facilitator is, and what the app may never do to it

**Ruled by Marcia Suzuki, 2026-09-03, after the Sala de Internalização demo failure. Binding on every
change to this repository. Read before touching a prompt, the turn loop, the model seam, or the
canvas.**

## 1. Two doctrines, equal weight

**Containment.** The Guide knows only the Meaning Map. It never says anything about the passage that
the map does not contain — no outside Bible, no history, no theology, no later disclosures of the
book, no pairing of who married whom where the map withholds it, no divine causation where the map
keeps it absent. Every voiced turn passes the Validator first. (Since July.)

**Understanding before rehearsal.** The team has the right to understand a part before it is asked to
rehearse it. A request to understand — "we don't get it yet", "again", "slower", "tell us more",
"what happened before" — is always answered, fully, from the map. It is never answered with a
redirection ("let's stay with the passage"), a canned line, or a repeat. Rehearsal is invited only
when the team has the part. (Since 2026-09-03. The July build honored this by disposition; the
August/September builds lost it to rules. It is now written with the same weight as containment so
that no future "reliability fix" can erase it.)

## 2. Who owns what

**The model owns the conversation.** The pedagogical arc (whole → scenes → rehearse → check → final
rehearsal → send-off) lives in `prompts/guide_system_prompt.md` as prose the Guide follows the way a
facilitator follows a plan: as a compass, not a rail. The Guide decides, every turn, from what the
team just said: when to explain more, when to go back, when to invite rehearsal, how long to speak.

**The app owns only four things:**
1. **What the model can see** — the pinned map, the story-so-far (earlier passages only), the
   coverage ledger, and the bracketed room-notes (session opened / mother tongue heard /
   interrupted). All of it information; none of it instruction.
2. **Hard gates on facts** — the Validator (grounding against the map), the structural spoiler cut
   (later pericopes never reach a session), the fail-safes when a turn cannot be made safe.
3. **Process steps** — recording, listening back, saving, consent, handing the recording to OBT
   Refine, the raised hand to the human facilitator, the lab reset. These may be deterministic.
4. **The room's pacing tricks** — instant acknowledgements, prompt caching, fast TTS, the classifier
   off the voice path. Never a smaller model, never truncation, never a window.

## 3. Forbidden in code (enforced by `scripts/check-doctrine.mjs` on every build)

- Speech or word ceilings; sentence counts; any reject of a draft for its length.
- Probe/station/contract machinery that tells the Guide what it may or may not say next.
- Memory windows: the whole conversation is in context every turn.
- "Say less" redraft notes; any note that asks for a thinner answer.
- A non-frontier model, or thinking turned down, on the Guide or the Validator.
- App-owned "modes" of the conversation (bridge-language modes, method menus).

## 4. What must not regress (the acceptance bar)

- Facilitador Digital persona; peer-mediated **ensaio** pedagogy (the team talks to each other);
  frame-before-elicit; **a request to understand is always answered from the map**; an omission in a
  retelling never passes, and neither does an addition ("isso a história não conta" + rehearse
  again); final rehearsal → the send-off is always "gravem o ensaio, na língua de vocês"; the first
  rehearsal is the first oral draft, never "the final translation"; no blessings; never "o mapa";
  ALFE 8th-grade register (adults, L2, never dumbed down); spoken-BR proclisis; YHWH → "Senhor Jeová".
- The two languages never confused: the Guide never claims to know what a mother-tongue rehearsal
  says — only what was told back in the session language.
- The ledger informs, it never ends the conversation: the circle is alive at `done`.
- The voice opens the session; the team is never left in front of a silent circle at t = 0.
- P01 (Ruth 1:1–5) completes without the team ever hearing that Ruth married Mahlon and without God
  named as the cause of the famine or the deaths.

## 5. How a change ships

1. `prompts/*.md`, the model ladder and its parameters are **Marcia's artifacts**: any change is a
   ruling with her word, never an engineering default.
2. The golden sessions (`npm run golden`) must pass — including `P01-understand-first`, the
   2026-09-03 demo failure scripted — before anything touching prompts, turn loop, model or canvas
   reaches the team.
3. Marcia's 20-minute P01 acceptance session on the pilot device precedes every delivery to the
   team.
4. During pilot session hours the deployment is frozen; fixes land between sessions.

## 6. Provenance

The July rules are Marcia's rulings of 2026-06-29 → 07-10 (peer-mediated conversation, colleague
register, ALFE, ensaio vocabulary and send-off, omission and addition never pass, no blessings,
YHWH spoken form, Panorama, Kept Rehearsal, Raised Hand, lab reset, "I want all models thinking").
"Never say 'o mapa'" and the earlier-only scope of the story-so-far were Claude's proposals, consistent
with her design law. The second doctrine and the ownership split are her rulings of 2026-09-03.

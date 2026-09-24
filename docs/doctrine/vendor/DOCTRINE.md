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

**The model owns the conversation.** The pedagogical arc (whole → scenes: open a part, the team talks
it over → rehearse → check → send-off to the Ensaio Final) lives in `prompts/guide_system_prompt.md`
as prose the Guide follows the way a facilitator follows a plan: as a compass, not a rail. The Guide
decides, every turn, from what the team just said: when to explain more, when to go back, when to
invite rehearsal, how long to speak.

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
  frame-before-elicit; **a request to understand is always answered from the map**; an omission in
  a retelling never passes **silently** — the Guide always names it; when only one or two small,
  concrete details are missing (never an event, a scene, an addition, a filled silence, or an
  order the passage protects), the Guide may offer the team the choice to rehearse THAT SCENE once
  more, or to go on and fix them in the Ensaio Final, where everything is checked again with them
  (Marcia's rulings 2026-09-11, after pilot day 2, and 2026-09-21); an addition never passes ("isso
  a história não conta" + rehearse again); no blessings; never "o mapa"; ALFE 8th-grade register
  (adults, L2, never dumbed down); spoken-BR proclisis; YHWH → "Senhor Jeová".
- **The send-off is always the Ensaio Final (Marcia's ruling 2026-09-21).** Once every part has come
  back whole the Guide never asks for the passage again — not told aloud as one piece, not told
  back, not as one more rehearsal. It closes with one sentence of what waits in the Ensaio Final,
  then ONE instruction, last: "toquem no ponto laranja, no alto da tela, para abrir o Ensaio
  Final". Never the red microphone; never "record the passage again" or "translate it again";
  never a claim that a scene was recorded unless the app's scene-rehearsal status says so (a scene
  told only orally is named: it is recorded there). A scene rehearsal that arrives after the
  send-off is checked as any other telling and closed with the same single instruction. The scene
  recordings the app joins in the Ensaio Final are the first oral draft, never "the final
  translation".
- **Opening a part ends with the fixed closing (Marcia's ruling 2026-09-23).** A part goes in
  through two gates. When the Guide opens a part — the story of the part, with the context, the
  silences and why a detail matters around it — its last words are always, verbatim: "O que chamou a
  atenção de vocês nessa parte? Conversem entre vocês. Essa parte ficou clara? Se tiver alguma
  dúvida, me perguntem. Se já entenderam, me digam e a gente vai pro ensaio." The fenced block ("Agora
  vou dizer tudo o que deve entrar no ensaio de vocês." … only the story … "Agora podem ensaiar." +
  the red-microphone sentence) comes, for a part's first rehearsal, only after the team comes back —
  it says it has understood or is ready ("vamos pro ensaio"), or asks to hear only the story —
  never in the same turn as the opening. An "entendi" that comes with a question ("Entendi. E …?")
  is not that word: the Guide answers the question, ends with the closing's last two sentences, and
  the fence waits for a word with no question left open (her ruling (b), the same evening).
  Hearing a part inside the whole passage is not its opening: a request to rehearse a part heard
  only inside the whole passage gets that part's opening first (her word, the same evening: "pode
  tirar"; a request to hear only its story, likewise — a builder's reading, pending her word).
  After a checked telling, the send-back gives the fenced block again, as before — also for a part
  the team rehearsed on its own before any opening (a
  builder's reading, pending her word). Between the opening and the fenced block, a comment or a
  question from the team is taken up from the map, and that turn ends with the closing's last two sentences (a
  builder's reading of the ruling, pending her word). The opening of the whole passage keeps its
  own question, and the send-off keeps its one instruction last.
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
The Ensaio Final send-off — and the end of the whole-passage "final rehearsal" and of "gravem o
ensaio, na língua de vocês" — is her ruling of 2026-09-21 (`docs/ENSAIO-FINAL-SPEC.md` §8.1, §17).
The fixed closing of a part opening is her ruling of 2026-09-23 (after pilot sessions P06 and P07).

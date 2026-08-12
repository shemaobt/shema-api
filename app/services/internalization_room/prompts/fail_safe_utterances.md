# Fail-Safe Utterances & Recovery Policy

> **What this is.** A small, designed set of pre-approved spoken lines the Guide can fall back to when the normal turn loop can't safely produce a response — plus the policy for when and how to use them. These exist so that a validation failure, a model error, or a stuck moment **never** results in either (a) silence, or (b) voicing ungrounded content. The fail-safe is always grounded, because it says nothing about the passage's specific content beyond re-anchoring to the current scene.
>
> **Why it exists.** The turn loop (Guide → Validator) can fail: the Validator may return `regenerate` repeatedly, a model call may error, or a response may be unrepairable. The system must degrade gracefully. A fail-safe line buys a turn without ever breaking containment.
>
> **How to use it.** These are application-side strings, not a model call. Localize them per session language. Pick one according to the policy below. They are deliberately content-light so they are *always* safe to voice.

---

## When the fail-safe fires (policy)

The orchestration should fall back to a fail-safe line in these cases:

1. **Validator returns `regenerate` more than N times for the same turn.** (Spec suggests N=2.) After N failed redrafts, do not try again and do not voice any draft — voice a fail-safe and re-anchor.
2. **A model call errors or times out** (Guide, Validator, or STT produced nothing usable).
3. **The Guide's draft is empty, or the Validator can't parse it**, and a retry also fails.
4. **The team's utterance couldn't be transcribed** (silence, noise, unintelligible) — a gentle "didn't catch that" fail-safe.

In every case the principle is the same: **say something safe, keep the session alive, return control to the team or re-anchor to the current scene.** Never expose the failure mechanics to the team ("the validator rejected my answer" — never). Never apologize elaborately. Just continue warmly.

## How the fail-safe re-anchors

A fail-safe line should, where possible, **point back to the current scene** so the conversation has somewhere to go. The orchestration knows the current scene from session state, so it can append a safe scene-pointer drawn from the **scene's already-validated material** — the scene title or its plain "what happens" summary, which are map-grounded by construction. The fail-safe *fixed* lines below carry no passage content; the optional scene-pointer is the only content, and it comes straight from the map's scene label, so it stays grounded.

> **Important:** when appending a scene-pointer, use the scene's *title or communicative-purpose summary as it appears in the map* — not a freshly generated description. Do not let the failure path become a backdoor for ungrounded generation. If you can't produce a grounded scene-pointer, use a bare fail-safe line with no pointer.

---

## The utterances

Written here in English; **localize per session language** (Portuguese first, since the pilot team is Brazilian). Keep them warm, short, unhurried, and free of any specific passage claim. Vary them (don't repeat the same line twice running) so the session doesn't feel robotic.

### A. Repeated validation failure / unrepairable response
Use when the Guide couldn't produce a safe answer. Re-anchor to the current scene.

- "Let's pause there for a moment and look again at what's happening in this part of the passage."
- "I want us to stay close to the passage here. Let's go back to this scene together."
- "Let's take that gently. Tell me what you're seeing in this part of the story so far."
- "There's a lot here. Let's slow down and stay with this scene for a moment."

*(Append a grounded scene-pointer where available: "…— this is the part where [scene title from map]." Only append it when the scene title is in the session language — never mix languages in a voiced line.)*

### A-pt. (Português brasileiro)

- "Vamos parar um instante aqui e olhar de novo o que está acontecendo nesta parte da passagem."
- "Quero que a gente fique perto da passagem. Vamos voltar juntos a esta cena."
- "Vamos com calma. Me contem o que vocês estão vendo nesta parte da história até aqui."
- "Tem bastante coisa aqui. Vamos devagar e ficar mais um pouco nesta cena."

### B. The team's question is outside the map (the honest-silence path)
This is not strictly a *failure* — it's the designed boundary behavior, but it lives here because the orchestration may route to it when a question can't be answered from the map. (The Guide prompt also handles this inline; these are backups.)

- "That's a good question. This passage doesn't tell us that — it stays focused on what's right here in front of us. Let's stay with what the passage is showing us."
- "The passage is quiet about that. Let's look at what it does tell us in this part."

### C. The question is important but the map can't answer it (handoff to facilitator)
Use when a question matters and reaching outside the map would be the only way to answer — route to the human.

- "That's an important question, and it's exactly the kind to bring to your facilitator — someone who can take it further than this passage goes on its own."
- "That deserves a real answer, and it's beyond what this passage tells us. Let's set it aside to bring to your facilitator, and keep going here."

*(The UI's "this needs our facilitator" affordance should also be offered here; log the question — it's signal about what the map doesn't cover.)*

### D. Couldn't hear / transcription failed
Use when the team's audio didn't come through.

- "Sorry, I didn't quite catch that — could you say it again?"
- "I missed that. Tell me once more?"
- "The sound didn't come through — would you say that again?"

### D-pt. (Português brasileiro)

- "Desculpa, não consegui ouvir direito — podem repetir?"
- "Essa me escapou. Podem dizer de novo?"
- "O som não chegou bem — podem falar mais uma vez?"

### G. Confidently detected speech outside the bridge language
Use when automatic language detection is highly confident that the team has just practiced in
another language. Affirm the practice, state the Guide's boundary, and request a telling-back in
the bridge language. Never feed the uncertain transcript to the Guide as if it were bridge speech.

- "Good — you tried it in your own language. I can't check those words directly. Now, could someone tell me in English what you said?"

### G-pt. (Português brasileiro)

- "Que bom — vocês experimentaram na língua de vocês. Eu não consigo conferir essas palavras diretamente. Agora, alguém pode me contar em português o que vocês disseram?"

### F. Instant acknowledgements (played the moment the team finishes speaking)
Not a failure path — the *pacing* path. Each real turn takes several seconds of honest work
(transcribe → draft → validate → voice). So the instant the team stops talking, the app voices one
of these tiny pre-approved lines, then the thoughtful reply follows. Content-free by construction
(no passage claim is possible), pre-synthesized and cached, rotated so it never feels mechanical.

- "Mm-hm."
- "Okay."
- "Mmm — let me think about that for a moment."
- "Right."

### F-pt. (Português brasileiro)

- "Hmm."
- "Certo."
- "Deixa eu pensar um instante."
- "Tá."

### E. Hard stop (repeated failures across multiple turns)
If fail-safes fire repeatedly across several consecutive turns (e.g. 3+), something is wrong (a bad map load, an outage). Don't loop forever. Degrade to a graceful pause and surface the facilitator handoff.

- "Let's take a short pause here. This might be a good moment to bring in your facilitator, and we can pick this up again together."

The orchestration should also flag this state for review (it usually means a map-load or service problem, not a content problem).

---

## Failure logging (don't skip this)

Every fail-safe firing should be logged with: the pericope, the scene, the team utterance, the Guide draft (if any), the Validator verdict + issues (if any), and which fail-safe category fired. Reasons:

- **Repeated `regenerate` on the same content** points to either a Guide-prompt weakness or a genuinely hard spot in the map — both worth your review.
- **Frequent category-B/C firings** (questions outside the map) are **high-value signal**: they tell you exactly what teams want to know that the maps don't yet cover. This feeds map improvement, and it's the kind of evidence the OBT Table will value.
- **Category-E firings** indicate infrastructure problems.

The failure path is not just a safety net — it's an instrument that tells you where the maps and prompts need to grow.

---

## A note on philosophy

The fail-safe embodies the whole tool's stance in miniature: when the system cannot be sure it is grounded, it says *less*, stays warm, and hands control back — rather than risking an ungrounded word reaching a team that will carry it into Scripture. Saying "let's look again at this part of the passage" forever would be a poor tool, but it would never be an *unsafe* one. The goal of the rest of the system is to make the fail-safe rarely needed; the goal of the fail-safe is to make its rare firings harmless.

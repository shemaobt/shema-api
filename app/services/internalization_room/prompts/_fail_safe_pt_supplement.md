# Fail-Safe Utterances — Portuguese supplement

The underscore marks this as ours, not one of the project's authored prompts. It carries two
kinds of thing.

First, the `-pt` blocks the authored file does not ship. It has them for sections A, D, F and G
but not for B, C and E — and the room speaks Portuguese, so without these the Facilitator would
switch to English at exactly the worst moment: a question the map cannot answer, a handoff, a
hard stop.

Second, section H, which the authored file has no counterpart for in any language, because the
situation it names did not exist when that file was written.

Translated from the authored English, matching the register of the existing `-pt` blocks:
warm, short sentences, `vocês`, spoken pronoun placement. Reviewed and approved by Marcia
(2026-08-10), along with the offline notice the app carries as an audio asset.

⚠ One choice here is not mechanical. The English says "your facilitator", meaning the team's
**human** facilitator (the Guide prompt spells it out: "their human facilitator or
consultant"). But the app introduces itself as *o Facilitador Digital*, so a bare "o
facilitador" could read as the app telling the team to ask the app. Rendered as "o facilitador
de vocês" to lean human. If that still reads ambiguously in the field, the alternative is to
drop the term entirely: "a pessoa que acompanha vocês".

### B-pt. (Português brasileiro)

- "Boa pergunta. Isso a passagem não conta — ela fica no que está bem aqui na nossa frente. Vamos ficar com o que ela está mostrando."
- "A passagem fica quieta sobre isso. Vamos olhar o que ela conta nesta parte."

### C-pt. (Português brasileiro)

- "Essa pergunta é importante, e é bem do tipo de levar ao facilitador de vocês — alguém que pode ir mais longe do que esta passagem vai sozinha."
- "Isso merece uma resposta de verdade, e vai além do que esta passagem conta. Vamos guardar para levar ao facilitador de vocês, e seguir por aqui."

### E-pt. (Português brasileiro)

- "Vamos fazer uma pausa curta aqui. Pode ser um bom momento para chamar o facilitador de vocês, e a gente retoma isso junto."

## H. A stretch is still waiting to be told back

**Not authored by the project. Approved by Henok as written, 2026-08-29.**

**This one is spoken, not shipped.** Every other family here is played from audio inside the
app, because a fail-safe has to work when nothing else does — no network, no model. H is not a
fail-safe: the gate fires with the server answering normally, before the analyst is called, and
the verdict a few lines later in the same endpoint is already synthesized. So the room says this
one out loud, and no app release stands between the team and hearing it.

Not a failure. Nothing broke and nothing was misheard: the team has a stretch they have not
explained yet, and the analyst may not read a subset, because its prompt defines "missing" as
*an element that appears in no stretch*. Reading half the work would raise findings about a hole
the team is on their way to filling.

**None of these names a number.** The gate fires whenever any final stretch is waiting, and
nothing stops a team from re-recording two stretches before pressing `terminei` — measured: two
can wait at once. These are fixed audio and can never carry a count, so a line that says "one
stretch" would simply be false as often as not.

The D family is the one to avoid here, and it is the tempting one because it sits eight lines
away in the same endpoint. It says *"I could not hear you properly — could you say it again?"*,
which is false (the room heard everything) and points at the wrong action (repeating what was
already told, rather than telling what was not).

### H.

- "There's still part of the passage for you to tell me. Let's finish that first, and then I'll check it all together."
- "There's still some you haven't told me. Tell me that, and then I'll look at the whole passage."
- "There's still a bit left to tell. When you're done, I'll check it all at once."

### H-pt. (Português brasileiro)

- "Ainda falta parte da passagem para vocês me contarem. Vamos terminar isso primeiro, e depois eu confiro tudo junto."
- "Ainda tem pedaço que vocês não me contaram. Me contem, e aí eu olho a passagem inteira."
- "Ainda falta contar um pouco. Quando vocês terminarem, eu confiro tudo de uma vez."

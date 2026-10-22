# What the voice says

Every line the room voices — a Guide turn, the Panorama, the check, the opening, the D lines
for a lost sound — crosses one function before it reaches the voice engine, and that function
rewrites the text in four steps, always in this order:

1. **Formatting marks off, every word kept.** `**bold**`, `*italic*`, `_italic_`, `` `code` ``,
   `[text](url)`, heading marks and list bullets go; a bullet or heading line is read as its own
   sentence; lines join with one space and whitespace runs collapse, since a voice hears no line
   break and no double space. An underscore inside a word (`snake_case`) and a `#` glued to a
   word (`C#`) stay.
2. **Canon codes removed and the seam mended.** `B3`, `PL_ISRAEL`, `[[B3-Naomi]]` and an all-caps
   name joined by underscores (`THE_LAND_AFFLICTED_BY_FAMINE`) are never voiced, in any language.
   The mend reaches only the seam a removed code left: each removal is marked, and every rule
   reads the marks beside that seam, so a mark the code did not leave — a dialogue dash, an
   ellipsis — is never touched. A list of codes goes with its commas and its "e" or "and", and a
   range (`B3 a B5`, `B3 to B5`, `B1–B5`, `B3 - B5`) goes whole; a joiner goes with a code only
   between two codes, so in a mixed list the survivors keep the joiner they had between them
   (`Noemi, B3 e Rute` → "Noemi e Rute") and no word is ever taken. A code that
   opened a sentence or a clause — after a full stop, a colon, a dash, an opening quote or
   bracket — leaves no mark where it stood (`As cenas:` + `- B3: Noemi volta` → "As cenas: Noemi
   volta."); a colon in the middle of a sentence stays, so a question it introduces is still
   cut. A dash pair around a code keeps its pair. A `FIG_` or `CB_` link is named only by its
   slug, so it is voiced as the slug's words (`[[FIG_0013-Bread-house-in-Famine]]` → "Bread
   house in Famine"), in English, as the maps write them.
3. **Every question stands alone.** A sentence that ends as a question is cut at its last colon,
   semicolon or dash outside quotes and parentheses, so the question gets its own tune
   ("Noemi pergunta: onde você trabalhou?" → "Noemi pergunta. Onde você trabalhou?"). A
   separator between digits (`10:30`, `Rute 1:5`, `1–5`) is not one, a pair of dashes is a
   parenthetical, and a comma never cuts.
4. **The divine name, spoken.** "YHWH" becomes the session language's spoken form.

Steps 1, 3 and 4 are Marcia's, ruled on pilot day 1 (2026-09-09), in her order; her tests are
ported one for one. Step 2 is ours, and it sits between her first and second steps for two reasons: a code
inside formatting marks is bare only once the marks are gone, and the seam a removed code leaves
must be mended before the question split reads it. The divine name runs last, so a code whose
slug is "YHWH" is removed before the name is rewritten. In English that order leaves "the LORD"
lowercase after a cut; the voice does not hear the case.

Each step is deterministic, idempotent and never drops, reorders or invents a word: only marks,
sentence boundaries, the canon codes and the joiners between two codes move, and a test holds
every seam to it. That is why the Validator judges the Guide's draft as written —
the words it judges are the words the team hears. Only what is voiced changes; the stored turn
keeps the Guide's own form for the facilitator view and the dossier. A clip is keyed by the text
the voice receives, so a line these rewrites change is synthesised once more the first time it
is asked for.

## Known limits

Each is pinned by a test, so a change to it is seen, not because it is the wanted answer.

- A straight single quote is not a span, since it is also the apostrophe (hers).
- A head that is itself a question still gets a period: "O que vocês acham. Bom ou ruim?"
  (hers; changing it is Marcia's call).
- An unbalanced double quote stops every later cut, the safe direction (hers).
- A plain line with no terminal punctuation gets no period, so a soft-wrapped sentence is not
  given a false stop (hers).
- An asterisk is never read as part of a word, so a multiplication loses it: "2*2" → "22"
  (hers).
- An article before the divine name is not removed: "The YHWH-given land." → "The the
  LORD-given land." (ours).
- A sentence a code opened starts lowercase once the code and its mark are gone: "Noemi volta.
  B3: o que Rute diz?" → "Noemi volta. o que Rute diz?" (ours; the voice hears no case).
- A preposition or a noun the code completed is left with nothing after it, since no word is
  invented and none is dropped: "In B3 and B4, Naomi weeps." → "In, Naomi weeps.";
  "(cenas B1–B5)" → "(cenas)" (ours).
- A joiner between a word and a code is the word's, so it stays wherever the code goes (ours):
  at the end of a list, "Noemi, Rute e B3." → "Noemi, Rute e."; opening a sentence or a
  bracket, "B3, B4 e Noemi choram." → "e Noemi choram." and "Rute fica (B3, B4 e Noemi)." →
  "Rute fica (e Noemi)."; on both sides of a code, "Noemi e B3 e Rute saem." → "Noemi e e Rute
  saem." and "Go to B3 to see it." → "Go to to see it."; and the code's comma between two
  joiners stays with them, "Noemi e B3, e Rute." → "Noemi e, e Rute."

## The divine-name table

The table is Marcia's, not invented here. It exists only for the two languages her own rebuilt
prompts already rule on:

| Language | Spoken as |
|---|---|
| `pt` | Senhor Jeová |
| `en` | the LORD |

Source, in the prompts this tree ships: `app/services/internalization_room/prompts/guide_system_prompt.md:251`
("The divine name. The map writes it as YHWH — four letters no one can pronounce…") and
`app/services/internalization_room/prompts/validator_system_prompt.md:86` ("Faithful rendering
into the session language… 'Senhor Jeová' / 'o SENHOR' (Portuguese) or 'the LORD' (English)").
Both files are hers byte for byte at her freeze (`docs/doctrine/FREEZE_PIN`), so the same two
rules sit at the same lines in her repository, `Tripod-Internalization`. A language outside
this table — Spanish included — keeps the bare letters rather than guessing at a form the pilot
does not speak; the other three steps still run.

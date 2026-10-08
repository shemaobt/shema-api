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
   A list of codes goes with its commas and its "e"; a link takes the colon that introduced its
   name, and a code that opens a line leaves no colon behind. A `FIG_` or `CB_` link is named only
   by its slug, so it is voiced as the slug's words (`[[FIG_0013-Bread-house-in-Famine]]` →
   "Bread house in Famine"), in English, as the maps write them.
3. **Every question stands alone.** A sentence that ends as a question is cut at its last colon,
   semicolon or dash outside quotes and parentheses, so the question gets its own tune
   ("Noemi pergunta: onde você trabalhou?" → "Noemi pergunta. Onde você trabalhou?"). A
   separator between digits (`10:30`, `Rute 1:5`, `1–5`) is not one, a pair of dashes is a
   parenthetical, and a comma never cuts.
4. **The divine name, spoken.** "YHWH" becomes the session language's spoken form.

Steps 1, 3 and 4 are Marcia's, ruled on pilot day 1 (2026-09-09), in her order; her tests are
ported one for one, her known limits included (a straight single quote is not a span; a head
that is itself a question still gets a period; an unbalanced double quote stops every later
cut). Step 2 is ours, and it sits between her first and second steps for two reasons: a code
inside formatting marks is bare only once the marks are gone, and the seam a removed code leaves
must be mended before the question split reads it. The divine name runs last, so a code whose
slug is "YHWH" is removed before the name is rewritten. In English that order leaves "the LORD"
lowercase after a cut; the voice does not hear the case.

Each step is deterministic, idempotent and never drops, reorders or invents a word: only marks
and sentence boundaries move. That is why the Validator judges the Guide's draft as written —
the words it judges are the words the team hears. Only what is voiced changes; the stored turn
keeps the Guide's own form for the facilitator view and the dossier. A clip is keyed by the text
the voice receives, so a line these rewrites change is synthesised once more the first time it
is asked for.

## The divine-name table

The table is Marcia's, not invented here. It exists only for the two languages her own rebuilt
prompts already rule on:

| Language | Spoken as |
|---|---|
| `pt` | Senhor Jeová |
| `en` | the LORD |

Source, in the prompts this tree ships: the Guide's system prompt ("The divine name. The map
writes it as YHWH — four letters no one can pronounce…") and the Validator's ("Faithful
rendering into the session language… 'Senhor Jeová' / 'o SENHOR' (Portuguese) or 'the LORD'
(English)"). The same two rules sit in her repository, `Tripod-Internalization` on
`fia/pilot-2026-09`. A language outside this table — Spanish included — keeps the bare letters
rather than guessing at a form the pilot does not speak; the other three steps still run.

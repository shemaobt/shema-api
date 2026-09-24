# Made speakable: marks, folded questions, and the divine name

`app/services/internalization_room/speakable.py` runs three deterministic steps ahead of
every call into the platform's speech synthesis: formatting marks off, a question folded
into a statement's tail split into its own sentence, and the tetragrammaton rendered
pronounceable. All three port Marcia's own transform in `Tripod-Internalization`'s
`src/audio/speakable.ts` and her rulings of pilot day one, 2026-09-09 — the marks and
question steps case for case, the divine name table with our own language handling (her
`failSafeLang` fallback chain is not ported). The persisted transcript is untouched: only
the text handed to the voice changes, so the facilitator view keeps the map's own wording.

## Formatting marks and folded questions

`strip_markdown` drops `**bold**`, headings, bullet lists, links, code marks and the rest of
her handled set, word for word — a bullet or heading line becomes its own sentence.
`standalone_questions` cuts a sentence at its last colon, semicolon, dash or spaced hyphen
outside any quote or parenthesis when it ends in a question, so the question is no longer
read as a flat statement. Both run for every language the room speaks. The exact cases,
including the ones Marcia pins as known limits rather than fixes, are in
`tests/test_internalization_room_speakable.py`.

## The divine name

The maps and the Guide write the tetragrammaton as the four consonants "YHWH", and a voice
engine reads letters it cannot pronounce — a name spelled instead of spoken, in the middle of
the turn the map most depends on. This step is a deterministic, word-boundary substitution,
so any "YHWH" that reaches it — validated line, corrected draft, or a story-so-far quote —
is voiced as a name.

The table is Marcia's, not invented here. It exists only for the two languages her own
rebuilt prompts already rule on:

| Language | Spoken as |
|---|---|
| `pt` | Senhor Jeová |
| `en` | the LORD |

Source, in the prompts this tree ships: `app/services/internalization_room/prompts/guide_system_prompt.md:153`
("The divine name. The map writes it as YHWH — four letters no one can pronounce…") and
`app/services/internalization_room/prompts/validator_system_prompt.md:87` ("Faithful rendering
into the session language… 'Senhor Jeová' / 'o SENHOR' (Portuguese) or 'the LORD' (English)").
The same two rules sit in her repository, `Tripod-Internalization` on `fia/pilot-2026-09`, at
`prompts/guide_system_prompt.md:163` and `prompts/validator_system_prompt.md:73`. A language
outside this table — Spanish included — reaches this step with its marks already stripped
and its questions already split, and leaves it with the bare letters "YHWH" untouched,
rather than guessing at a spoken form the pilot does not rule on. This is a record of what
was implemented, not a request to approve an invented form.

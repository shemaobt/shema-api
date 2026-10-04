# The divine name, spoken

The maps and the Guide write the tetragrammaton as the four consonants "YHWH", and a voice
engine reads letters it cannot pronounce — a name spelled instead of spoken, in the middle of
the turn the map most depends on. `app/services/internalization_room/speakable.py` runs a
deterministic, word-boundary substitution ahead of every call into the platform's speech
synthesis, so any "YHWH" that reaches it — validated line, corrected draft, or a
story-so-far quote — is voiced as a name.

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
`prompts/guide_system_prompt.md:163` and `prompts/validator_system_prompt.md:73`. A language outside this table — Spanish included — reaches the platform unchanged
rather than guessing at a form the pilot does not speak. This is a record of what was
implemented, not a request to approve an invented form.

The persisted transcript is untouched: only the text handed to the voice changes, so the
facilitator view keeps the map's own wording.

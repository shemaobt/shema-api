---
status: accepted
date: 2026-09-16
---

# The Speaker names a **Part** by its position, its scene title and the frases it carries

The room is wordless. A verdict that sends the team back to record a part again has only the
spoken name to send them with, and a take carries nothing sayable: `take_id` is generated and
the number the tablet put on it has no name attached. *"Gravem de novo a parte 3"* over a
rehearsal of five parts asks a team to work out which one, and the cost of getting it wrong is
a re-recording of the wrong scene.

Decided: every finding that reaches the Speaker carries an address, built from three things
and nothing else — the **Frase number** the analyst gave and the team heard, the part's
**position among the session's current parts**, and the scene's own title from the
element-label catalogue. The title is said only when the rehearsal has exactly as many current
parts as the passage has scenes *and* the catalogue holds that title in the session's language;
otherwise the number and the frases stand alone. A part with no number is *a gravação inteira*
and gets no scene and no range. The address rides in the findings block, never in a closing.

**The position, not the stored number.** The tablet numbers its parts from one and the text
seam declares them from zero, and both mean the same first part. Reading the stored `ordinal`
would hand a seam session *a parte 0*, and a falsy-zero test would hand them the whole
recording.

**The numbers are the reading's, not a version's.** On the verdict path nothing frozen exists:
`segments_block` numbers the telling-back from one on every reading and the analyst answers a
position in that list. The **Frase number** frozen on a **Version** is the packet's, and the
two must not be confused — what the address says is what the team just heard the voice say.

**The count is the only guard there is.** The room directs the team to record the passage whole
or scene by scene and nothing enforces it, so a team that merged scenes 1 and 2 and split
scene 3 has four parts over three scenes and part 2 is not scene 2. The frase range therefore
stays even when the title is said: a misaligned title is recoverable when the team is also told
which frases the part carries.

Rejected: **the scene name as the part's identity** (Marcia's app can do it because her
recording screen records under the scene names; the server holds no join from a part to a
scene, and `label_pt` is null for ten of the fourteen passages). **The bare number**, which is
what the team cannot act on and the reason this ticket exists. **A closing slot per language**:
the closings are constants with one `{session_language}` slot and the Speaker is told no
address anywhere else, so the address belongs where the findings are.

**The whole address follows the session's language, the word *frase* included.** The findings
block is not an instruction to the Speaker: it is content in the language of the session — the
analyst's note already arrives in it — and the Speaker echoes what is there, so an English turn
says *sentence 5 — part 2 — …*. A Portuguese word inside a turn spoken in English invites the
very echo her rule against a voiced line in two languages exists to prevent. The **Frase
number** entry of `CONTEXT.md` names the concept and the spellings it has on the wire, not the
word said to a team in another language. Marcia's golden check `names_frase` matches the
literal *frase N* and her scripts are in Portuguese, so it goes on matching there; the day a
golden run happens in English, the check adapts rather than the room speaking Portuguese to a
team that does not read it.

**A holed catalogue costs the title, never the room.** `labelled_elements` raises
`ElementLabelsBroken` on a catalogue of ours being wrong, and everywhere else that is a 500 —
right on the screens that exist to show labels, wrong here: before this rule the verdict never
read the catalogue at all, and a team's session dying over a decoration is a worse failure than
a verdict that names the part by its number, which the team can still act on. The one exception
is caught around the one call and logged with its traceback, because a data fault nobody is
told about is how it stays there. The branch is one more *no title*, like the count that
disagrees and the language with no label.

Consequence: no title ever crosses languages — an English title never appears in a Portuguese
session and the reverse — because a voiced line that mixes two languages is the one thing her
fail-safe rule forbids, and a passage nobody has translated gets the number instead.

## Who holds the containment rule

*A test fails if a part name reaches the Speaker that is not the catalogue label, the part
number or the frase numbers* is held by the cases of
`tests/test_ir_the_speaker_names_the_part.py`, one per branch the label function can emit, each
asserting the whole address by equality against `labelled_elements()` and the numbers the
fixture told — never against a title written into the test:

| Branch | Case |
| --- | --- |
| the whole recording | `test_a_rehearsal_told_whole_is_the_whole_recording` |
| title and range, pt | `test_a_finding_on_part_two_of_a_three_scene_passage_names_the_scene` |
| title and range, en | `test_an_english_session_names_the_part_in_english` |
| number and range, the counts disagree | `test_a_four_part_rehearsal_names_the_part_by_number_alone` |
| number and range, no title in that language | `test_a_passage_without_portuguese_titles_names_the_number_alone` |
| one frase | `test_a_part_with_one_frase_says_the_frase`, `test_the_seam_declares_parts_from_one` |
| the position, not the stored ordinal | `test_the_seam_declares_parts_from_one` |
| a missing with no address: frase, no part | `test_a_missing_without_an_address_names_no_part` |
| a row from before `chunk` existed: no frase slot | `test_a_finding_from_before_the_frase_number_existed_leaves_that_slot_out` |
| a stretch whose part is no longer one | `test_a_finding_on_a_part_that_is_no_longer_one_names_the_frase_alone` |

A sweep over those same inputs checking each address against a regex of permitted shapes was
written first and removed: over one input, equality with the catalogue's own answer is strictly
stronger than a pattern, and the pattern was loose exactly where the rule is tight. What it was
hiding is the row with no `chunk`, which no case held until it came out.

## What no test here can hold

**That the Speaker actually says the address.** Every case holds that the address reached a
prompt slot — the Speaker's, the Validator's, the Correction check's. None holds that the
voice names the part, and none can: the Speaker's template is Marcia's artefact and is not
edited here, and it nowhere describes the shape of a finding line or tells the Speaker that the
bracket is an address it may say. What answers that question is the golden run
(`scripts/bt_golden_runner.py`, real model calls), which is Henok's gate and the Orchestrator's,
and the *Test by hand* block of the pull request.

One thing to watch there: the address hands the Speaker *das frases X a Y*, plural, which her
`one_frase_per_turn` check never matches — its pattern is `frase\s+\d+` and *frases* has no
space after *frase*. The label itself can therefore never trip it. What can is the model's own
wording repeating two frase numbers in one turn, and no test of this slice reaches that.

**That the Correction check can resolve the frase it is given.** Its prompt carries the two
tellings as raw transcripts and no numbered list, so *frase N* is an address that reader cannot
look up. It travels anyway, because it is the finding's own text and removing it there would
make one finding read two ways to two readers of the same stretch.

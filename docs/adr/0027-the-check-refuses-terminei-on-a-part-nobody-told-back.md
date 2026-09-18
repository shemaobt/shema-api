---
status: accepted
date: 2026-09-18
---

# The check refuses *terminei* on a part nobody told back, and names it

ADR 0026 taught the release gate to read the current parts beside the stretches, and wrote its
own gap into its consequences: the verdict's untold errand, `first_untold`, still walked stretch
rows only. So a team sent back by the release and a team sent back by the check were told about
different things, and the difference was not cosmetic. A **Part** recorded again arrives carrying
nobody's words — the stretches of the recording it replaced went with that recording (ADR 0023) —
and it is invisible to both errands the check had: `first_untold` finds a reading that is whole,
and the listening is asked of the takes the surviving stretches name, which the fresh one is not
among. The analyst read the other parts, answered clean, `checked` went true and the passage left
the wheel for good. Only the approval then refused it, as `untold_part`, with no force — a
facilitator called to look at a hole the team could have filled themselves, on a passage the room
had already told them was conferida.

Decided: the check asks the same question the release asks, at *terminei*, before the analyst and
before the listening. The current parts (`current_parts`) that no standing stretch is a slice of
(`untold_parts`) refuse the press: the room speaks the H family and the answer names them on
`untold_take_ids`, its own field beside `untold_segment_id` and `unheard_take_ids`. It is the
untold errand said over different ground, so it spends what that errand spends — the same lines,
the same turn of the waiting ladder, kept — and it asks nobody: no reading, no line in the
conversation. One errand per press: a session owing both an untold stretch and an untold part
hears about the stretch first and about the part on the next press, because the room answers the
question the team is standing closest to while the release lists both codes at once.

**Its own field, never a borrowed one.** The verdict's refusal fields are one per errand, and the
app decides by the field and never by what is missing from the body. `unheard_take_ids` would send
the team to press play on a recording they owe an explanation of; `untold_segment_id` would send
them looking for a stretch that does not exist, and the tablet resolves that one against the
stretches it already holds. The ticket fixed the sibling shape for that reason, and the tablet's
own reaction to the new field is a slice of its own: today's build parses unknown keys away, so
the refusal is honest on the wire before any app reads it.

**Between the stretch and the listening**, the order the release already lists the three in. A
part nobody told is owed a telling before it is owed a playing: sent to play a clip first, the
team would answer the smaller question and come back to the same refusal. And the question is the
takes' to answer rather than the stretches' — which recording is current is the number the tablet
sent — while what was heard of it stays a fact of the report, exactly where ADR 0023 and ADR 0026
left it.

Rejected: **refusing only at the release**, which is what this replaces — the passage reads
conferida, the team is sent home, and a person is called for material they can supply themselves.
**Folding the part into `untold_segment_id`**, for the address that does not exist. **Reusing
`unheard_take_ids`**, for the errand it would send them on. **A payload the Definer decides
later**, when the ticket had already fixed the shape the two sibling fields carry.

Consequence, decided knowing it. The restart route
`POST /sessions/{id}/back-translation/restart`, its response model and
`begin_back_translation_again` are retired with this: the tablet removed its only caller
(ENG-723), the Desk and the text seam never reached it, and the whole-session verb answered a
gesture the room no longer offers — what a team re-records is the unit they rehearsed (ADR 0025),
and the part they re-record is answered by the upload under its number. A rehearsal told whole and
recorded again retires nothing, because that verb reads the number and an unnumbered take carries
none; the telling the team already gave stands on a recording that is no longer the part, and this
decision is what refuses that session at the check.

Two more consequences, decided knowing them. **The D family stops answering any session a team
reaches.** A rehearsal recorded and nothing told back is a current part with no stretch, so it is
this refusal now and not *"I could not make anything out, can you tell me again?"* — which was the
false half of that answer anyway, because nothing was said for the room to fail to hear. D still
answers a session holding no rehearsal take at all, and that is the whole of what it answers.
**A row the old per-stretch correction left behind stops the check as well as the release.** ADR
0026 records that such a fragment is a part of its own that no stretch names, that it refuses the
release as `untold_part` and that no force lifts it; the same reading here means the passage
cannot be conferred either. It is the same row read by the same rule, and whether the field still
holds such a session is the question ADR 0026 already left open.

`SCHEMA_VERSION` does not move, no key of the packet changes and the release gate is untouched:
what changed is that a passage the gate would refuse can no longer be conferred first.

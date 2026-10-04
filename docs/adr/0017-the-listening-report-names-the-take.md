---
status: accepted
date: 2026-09-11
---

# The listening report names the take it was played from, and the gate answers which parts fail

A rehearsal is recorded in parts, and the team listens to one part at a time. The report the
tablet sends says so: one entry per part, naming the take it was played from, with the spans in
**that take's own milliseconds** and that take's own length. Marcia keys the same record per
clip; her `clipKey` is our `take_id` and her `heardByClip` is our `played_by_take`.

`playback_confirms_rehearsal` asks the covering question once per current part and returns the
take ids that fail, sorted. Empty means heard. An entry covers its part when its spans reach the
end of that part's own length within `PLAYBACK_TOLERANCE_MS` at each edge and between spans;
entries for takes the stretches no longer name are ignored, because they are about audio no
stretch is a slice of any more. The release blocker reads only whether the list is empty, and
keeps its name.

The tolerance stays an absolute 750 ms rather than Marcia's 95 % per clip. She argued against
her own number on 2026-09-08: five percent of a four-minute part is twelve seconds, which can
hide a whole frase, and a percentage is generous in proportion to length. The rule is the
method — the whole recording heard before the voice says anything is missing — not the
arithmetic.

Two alternatives were rejected. The first is the shape ENG-640 gave sessions in flight: one flat
span list and one total over the glued passage, with the subject stamped by the server from the
stretches. It cannot say which part is unheard, and it throws every part's listening away the
moment one part is recorded again, because the one number it carries is about a passage that has
stopped existing. The second is importing her 95 %, rejected for the reason she gave.

A flat report is still accepted from tablets in the field and still stored, because it is the
record of what that build reported — and it is evidence of nothing. The gate never consults it,
nor the server-stamped `played_take_ids` beside it. **Nothing is migrated**: a session in flight
is refused until the team plays its rehearsal through again on the new build, which is the same
reading ENG-640 already gave those rows and the one the release argues from — a report we cannot
tie to a recording is not evidence about any recording. No build is in a store yet, so nobody in
the field is stranded by it.

The state is a JSON column, so this is a pydantic change and no migration. The packet carries
`played_by_take` where it carried the two flat fields, and its schema version moves to v0.5: a
consumer diffing the two versions finds two keys gone and one arrived, rather than finding the
old ones still there and no longer meaning what they said (ADR 0014).

The archived attempts under `superseded_attempts` are the exception, and keep both shapes. They
are the record of what an older build reported about a recording that no longer exists, and the
report cannot be restated per part after the fact — there is nothing left to key it to. A
consumer reads them as history, never as evidence, which is what they were when they were
written.

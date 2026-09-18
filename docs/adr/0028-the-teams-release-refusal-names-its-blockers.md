---
status: accepted
date: 2026-09-18
---

# The team's release refusal is an answer that names its blockers, not a 409

The team's approval route answered a refused release the way every other conflict does: a 409
with a sentence built from the gate's codes, joined by commas, in `detail`. The tablet's own
client throws `ReleaseRefused` on that status and reads nothing else, so the team learned that
something was wrong and never which door was shut — the same hole ENG-889 closed at *terminei*
and ADR 0027 closed again for the untold part, and the release route was the one place the room
still answered a refusal as an error instead of a field.

Decided: `POST /sessions/{id}/release` answers 200 always. A mint carries `version`,
`release_id`, `package_sha256`, `approved_at` and an empty `blockers`; a refusal carries
`blockers` — the gate's codes, in the gate's own order, `InternalizationReleaseBlocked.blockers`
verbatim — with `version` and the rest null. A session naming no project answers
`blockers: ["no_project"]`, a literal at the route rather than a code out of the gate, because
`ReleaseWithoutProject` is refused before the gate is ever asked and the fact is the route's own.
For the three blockers with a door on the tablet — `untold_part`, `playback_did_not_cover_the_clip`,
`untold_stretch` — the answer also names the ground, on the same fields *terminei* already
answers with (ADR 0027): `untold_take_ids`, `unheard_take_ids`, `untold_segment_id`. Each is
filled only for the blocker that owns it and empty otherwise, so the app decides by the field and
never by what is missing from the body (ENG-889's rule, asked here of the release). The ground is
derived in the route after the refusal is caught, from the same service helpers the finish route
reads its own answer from (`final_segments`, `current_parts`, `rehearsed_parts`, `untold_parts`,
`unheard_parts`, `first_untold`), and not by widening `compose_internalization_release`'s return
type: the gate owes codes (ADR 0026), and the ground is the errand's, asked fresh.

The route gets its own response model, `TeamReleaseResponse`. `ReleaseResponse` and
`ForcedReleaseResponse` are untouched: an optional `version` or a `blockers` field on
`ReleaseResponse` would leak into the Desk's force response, which inherits it, and the Desk
reads neither field.

The Desk's three routes keep their 409 with the whole list, unchanged: a facilitator is a person
reading a sentence, not an app deciding by a field, and Marcia's own gate there — the live packet,
the read by version, the force — has no client that throws on the status the way the tablet does.

This reverses ADR 0026's rejection of "a payload naming the take," for the team's route alone,
on the reason that turned out false: that decision reasoned the Desk greps clean for every code
today, which is true and beside the point — the Desk was never the client this payload is for.
The tablet is, and a version-less 200 it cannot yet read as a refusal is exactly why this must not
reach `main` before ENG-956 puts the reading on the device (the deploy note travels with the PR,
not with this record).

Rejected: keeping the 409 with a JSON body carrying the same fields, which answers the letter of
"a field, not a sentence" and not the spirit of it — the tablet's client throws on the status
before it ever reads the body, so a 409 teaches the app nothing regardless of what rides inside
it. Making `version` optional on `ReleaseResponse` instead of a new model, rejected for the reason
above: the Desk's force response inherits it. A blocker carried as an object with its ground
inside, one shape merging the code and the address: rejected because the codes are the gate's and
the ground is the errand's, which is the same split ADR 0027 already drew at *terminei* — a
blocker that carried both would be answering two different questions on one key.

Consequence, measured and not assumed: recording a **Part** again resets `checked` to false on
its own (the passage the team is standing on changed), so a session refused for `untold_part`
this way answers `blockers: ["telling_back_not_checked", "untold_part"]` rather than the one code
alone — the same pairing `test_a_clean_reading_of_the_other_parts_does_not_release_the_untold_part`
already measures at the service level. A session whose telling-back was retired wholesale answers
`["no_telling_back", "untold_part"]` for the reason ADR 0026 already gives: every part such a
session holds stands with nothing told on it. Neither pairing is a defect of this change; both are
the gate saying, honestly, that more than one thing is wrong at once.

`SCHEMA_VERSION` does not move and no key of the packet changes: what changed is the shape of the
answer a refusal wears on the team's own route, and only there.

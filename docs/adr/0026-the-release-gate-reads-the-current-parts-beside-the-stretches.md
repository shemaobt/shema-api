---
status: accepted
date: 2026-09-17
---

# The release gate reads the current parts beside the stretches

Every gate the room had over the team's own words was derived from the stretches: `untold_stretch`
refuses a **Release** whose reading carries a unit with nothing said on it, `first_untold` sends the
team to the earliest of them, and the listening asks which recordings the stretches are slices of.
That was the whole of it because, until a part could be recorded on its own, a recording with no
stretch was a recording nobody had started telling back at all — and `no_telling_back` said so.

Recording a **Part** again broke the coincidence. The upload under that part's number retires the
stretches of the recording it replaces and nothing else (ADR 0023), so the fresh recording stands as
the part, carrying nobody's words, with no stretch anywhere pointing at it. `untold_stretch` sees a
reading that is whole, the listening sees the parts the surviving stretches name, `first_untold`
finds nothing — and the **Packet** goes on carrying that recording in `rehearsal_takes`, because one
take per number, the newest, is what the packet says the rehearsal is. A clean reading of the other
parts was then enough to mint a release, on the team's own route, whose packet carried a scene
nobody explained.

Decided: `compose_internalization_release` reads the current parts — `current_parts(takes)`, already
in hand for `rehearsal_takes` and `recording_grain` — beside the stretches, and a part no standing
stretch is a slice of is untold ground and refuses the release as `untold_part`. Once, whatever the
number of such parts, because a blocker is an errand and the errand is the same one. It is **not**
in `FORCEABLE_BLOCKERS`: the glossary calls an untold stretch material and not a dispute, and a
recording nobody told back is the same material — there is nothing in it for a person to look at and
disagree with. It coexists with `no_telling_back` rather than hiding behind it, and both are true of
a session that never started.

**The listening gate stays derived from the stretches**, exactly where ADR 0023 left it, and the two
questions are why. Which recording is current is a fact of the takes: the number the tablet sent and
the order the room reads it in answer it completely. What was heard of that recording is a fact of
the report, and the takes cannot answer it — `created_at` is when an upload landed, the outbox
drains whenever the link comes back, and the rehearsal that arrives last is sometimes the one the
team abandoned. This decision asks the takes only the question they can answer.

Rejected: **folding the part into `untold_stretch`**, which would send the facilitator looking for a
stretch that does not exist. **A payload naming the take**, which no client would read — the Desk
greps clean for every code — and which the ticket did not ask for: a blocker is what the gate owes,
not a contract. **Deriving the listening gate from the takes** so the two would share a source, for
the reason above (ADR 0023 rejected it once and it stays rejected).

A row the old per-stretch correction left behind is refused by this, and unliftably. That
correction kept its fragment as a rehearsal take carrying no number, and the **Rebuild** re-pointed
the stretch at the assembled file instead — so in a session told in parts the fragment is the only
take with no number, which makes it a part of its own with no stretch naming it. ADR 0023 records
that as a cosmetic gap, the fragment listed in the packet beside the real parts; under this
decision it stops the release, and no force lifts it. It is the honest reading of the row — it is
ground the team recorded and nobody told back — and it is written here because ADR 0025 promised
those rows would travel by the same rule as any take, and this is that rule turning out to have
teeth. Whether any such session is still unreleased is a question for the field and not for the
gate.

The text seam does not reach this gate, and it was asked. It declares a part per clip of her draft
and captures a frase on a clip only when a round arrives, so a declared clip nobody told is exactly
the shape this refuses — but a seam session names no project, `approve_release` refuses a
project-less session before it composes anything, and both facilitator routes resolve a session by
the team that owns it. Neither golden runner calls a release door. A release door opened onto the
seam would have to answer this question before it opened.

Consequences, decided knowing them. A session whose telling-back was started over now carries
`untold_part` beside `no_telling_back`, because every part it holds stands with nothing told on it;
that is the same hole read honestly. The verdict's untold errand, `first_untold`, still speaks only
of stretches, so a team sent back by the release gate and a team sent back by the check were told
about different things — out of scope here, named as a finding, and closed by ADR 0027, which asks
this same question at `terminei` and names the parts there. `SCHEMA_VERSION` does not move
and no key of the packet changes: what changed is which sessions are refused.

The release cases used to be assembled on a stretch naming a recording no row carried, which the
room itself refuses (`rehearsal_take_of`); the gate above reads that fiction as exactly what it is,
so the harness now names the session's own take. That is a test-only change and it is recorded here
because it is why a green suite before this decision is not evidence about it.

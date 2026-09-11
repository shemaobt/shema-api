---
status: accepted
date: 2026-09-11
---

# An open finding or an unheard part refuses the **Release**, and only the facilitator forces one

ENG-584 removed the blocker that refused a release while the telling-back carried an open
finding, on the argument that carrying the questions to Refine was the one outcome the room
had to be able to reach. Marcia closed that on 2026-09-07: her whole gate, now — no open
finding and the whole recording heard, or no approval; only the facilitator's code forces.
Her reason is the one the code carries from here: a disputed finding is one of three things,
the map wrong (rare and valuable), the team not understanding, or the recogniser failing, and
only the first deserves to go on. With a button the other two would reach Refine and the
community would hear as approved what the check itself had marked. ADR 0014 wrote the
numbered row and deferred this decision by name.

Decided: the blocker `telling_back_not_checked` returns beside the playback blocker, after
`telling_back_never_analysed`, which keeps precedence. A facilitator forces through a route
of their own, `POST /facilitator/sessions/{session_id}/release`, whose body must say
`force: true` and which exists for that act alone; without the flag it refuses with
`nothing_to_force`. The force waives exactly the two blockers of her gate — the open finding
and the unheard part — and no other: consent, coverage, rehearsal audio, a telling-back, its
reading, an untold stretch and the panorama are missing material, not a dispute. The forced
release is a **Forced release**: the row records who forced it, when, and the findings open
at that moment, because a forced approval that shows only in the server log is the failure
she named in her own stack. The team's route never reads `force`; approval stays the team's
act and forcing the facilitator's, which is what her moving `force:true` off the team code
means in an architecture where the two credentials are two routes. ADR 0014's rule holds
under force: an unchanged packet returns the release that already exists.

Rejected: a force that waives every blocker (more than she asked, and a packet with no base);
one route for both roles with the flag gated by credential, as in her app (two authentication
schemes in one route where ours are already two routes); a facilitator route that also
approves under the common gate (a second approval path she never described); and any team
exit — a button or a spoken route — that carries the questions to Refine, which is the
decision she took on 2026-09-07 and told us to delete at will.

Consequences: the tests that pinned ENG-584 are inverted rather than deleted, so the reversal
stays visible in the diff; the docstring that argued for carrying the questions is rewritten
to say the gate, the raised hand and the three things a disputed finding can be; the packet
still says only `checked` and `findings`, and carrying the forced fields into it is the
`check` block of ENG-891; the Desk's force button lives in another repository.

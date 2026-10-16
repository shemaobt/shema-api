---
status: accepted
date: 2026-10-16
---

# A demo team's claim codes are spent by the server, and it never calls a person or releases

A store reviewer at Apple or Google is alone with the app. A tablet joins a team only when a
facilitator spends its claim code on the Desk (ADR 0057), so the reviewer never gets past the
code screen. Henok decided on 2026-10-13 that a **Demo team** spends its own codes. The Definer
ruled on 2026-10-16 that the spend happens in a browser page, and that the store binary carries
nothing for it (ENG-1629).

## Decision

- One team per environment is the demo team, named by its team id in
  `INTERNALIZATION_ROOM_DEMO_TEAM_ID`, never by its name. With the setting empty, or naming no
  team, there is no demo team and nothing changes.
- While there is a demo team, the server serves `GET /api/internalization-room/demo`, a plain
  English HTML form with no login, no script and no external asset. The reviewer types the code
  the tablet shows, and `POST` of the same URL (form field `code`) spends it on the demo team
  through `claim_device`, the spend under the Desk's claim: single use, expiry, the same write
  guard. The page reads the code as the tablet shows it: it keeps only the letters and digits
  the reviewer typed, in capitals, and puts the hyphen back when seven are left, so a space or a
  phone keyboard's dash in place of the hyphen still links. The tablet's next poll of `link` finds it spent and collects its own credential. With
  no demo team both answer 404.
- Every refusal is one answer: 400 with "That claim code is not valid.". The Desk names three
  refusals because its caller is an authenticated facilitator. This caller is anonymous, and
  telling a spent code from an unknown one would tell it which codes exist.
- The `POST` takes 10 codes a minute in all, in one bucket for every caller, through the house
  limiter. Not per address: the app trusts `X-Forwarded-For` from any host, so an address is
  whatever the caller writes, and a bucket per address would cost a guesser nothing.
- The demo team never calls a person. Each of its halts is attended by the server at once,
  with no one as `attended_by`: the session's blocking halt and its warning, and a tablet's halt
  with no session. The halt is still written and counted, so the room's history shows it.
- Nothing the demo team records reaches Refine. Every release door refuses it with the blocker
  `demo_team_never_releases`, raised before the gate, so no force waives it.
- This amends ADR 0057's "a claim code is only worth what a facilitator spends on it" for the
  demo team only. A facilitator may still spend any code on any team they facilitate, the demo
  team included.

## Rejected

- A reviewer build with a baked credential: a second binary to review and keep.
- Henok spending the code live during the review: the review happens on Apple's schedule.
- A hidden gesture on the tablet with a `demo` field on `POST /devices/code`, and a build-time
  flag: both put the switch into the binary real teams install. The page leaves the binary as
  it is.

## Consequences

- While configured, anyone who finds the page can link a tablet to the demo team and run the
  voice at our cost.
- Worse, anyone who guesses a live code of a real team's tablet still waiting for its
  facilitator links that tablet to the demo team. The limit is a toll, not a ceiling: its bucket
  lives in each instance's memory, so N instances take N times 10 codes a minute. So the setting
  is on only during a store review window, and unset after it. A facilitator unlinks a stray
  tablet from the Desk as usual.
- Anyone who fills the bucket locks the page for everyone, the reviewer included, until the
  minute passes. The reviewer is told 429 and types the code again later.
- The tablet's refused approval raises a halt, which the server attends at once, so the
  reviewer's room resumes.
- The demo team is an ordinary team: the Desk lists it under its own name, and Zerar cleans it.

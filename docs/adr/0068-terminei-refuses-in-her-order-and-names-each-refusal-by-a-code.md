---
status: accepted; amended 19 Oct 2026 by ENG-1221 (FRASE_AWAITING voices her N-6 by position)
date: 2026-10-19
---

# *Terminei* refuses in her order, and names each refusal by a code

Her check (`bt/check/route.ts:64-78` at her freeze 18fa7c4) refuses a press in one order: a frase
awaiting its translation, then a part not yet heard, then — on a joined recording only — a stretch
no frase translates, then a passage with nothing translated at all. When its model cannot answer
it saves nothing and the screen offers the press again (`:90-97`). Ours refused an untold stretch
and then an untold part with H lines no file of hers carries (ADR 0027), heard only the parts some
stretch named, answered «nothing translated» with her D line as if the room had not heard, and
answered a model outage with a 502 the tablet reads as a lost connection.

Decided, as hers (ENG-1197):

- The order is hers: `FRASE_AWAITING`, `PART_UNHEARD`, `STRETCH_UNTRANSLATED`,
  `NOTHING_TRANSLATED`. Each is a value of `refusal` on the 200 answer, documented on
  `CheckRefusal`; the tablet turns it into her screen line. `STRETCH_UNTRANSLATED` is the door a
  joined recording will fill and is not sent yet.
- Two refusals are voiced, each as her line by position through `GET /fixed-lines`:
  `PART_UNHEARD` as her P-unheard (`fixed_line: "P2"`), and `FRASE_AWAITING` as her N-6
  (`fixed_line: "N5"`) when the frase awaiting is a re-recorded sentence (ENG-1221: «Ainda falta
  traduzir a frase que vocês regravaram.»; ENG-1197's order names N-6 for it). A frase awaiting
  for any other reason, `STRETCH_UNTRANSLATED` and `NOTHING_TRANSLATED` say nothing, as hers do.
  (Amended 19 Oct 2026 with ENG-1221's server half; the first text voiced `PART_UNHEARD` alone.)
- A part with nothing told over it is no refusal: the check runs and her analyst names what is
  missing. `untold_take_ids` leaves the answer and `untold_part` leaves the release gate.
- The listening is asked of every current part, told or not, at *terminei* and at the release,
  as hers asks it of every current take. Which parts are current is the takes' answer; what was
  heard of them is still the report's. This amends ADR 0026's rule that the listening stays on
  the stretches.
- The analyst, the Speaker or the verdict's voice unavailable answers `CHECK_UNAVAILABLE` and
  saves nothing; *terminei* again is the retry.

Supersedes ADR 0027; amends ADR 0026 and ADR 0028. Rejected: **a 409 or a 503 per refusal**, because the tablet reads every
5xx as the room being gone and counts every other refusal toward calling a person; **keeping the H
family**, which no line of hers says.

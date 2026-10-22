---
type: "sta-compilation-log"
pericope: "P08"
status: "valid"
pilot: "pilot-2"
---

# P08 — Ruth 3:1-5 — COMPILATION-LOG

```json
{
  "sta_id": "ruth_pericope_08_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Ruth 3:1-5",
  "pericope_id": "P08",
  "pericope_title": "Naomi's plan for rest; Ruth's total consent",
  "compiled_at": "2026-06-12",
  "review_status": {
    "meaning_map_status": "PARSED_BY_COMPILER",
    "sta_compilation_status": "MODEL_DRAFTED_REVIEWER_RULED",
    "community_verified": false,
    "translation_team_verified": false,
    "consultant_review_required": true,
    "production_use": false
  },
  "confidence_overall": "MEDIUM",
  "confidence_overall_note": "Judgment half machine-drafted (50/50 gaps, patch-only contract, 0 rejected), all four gates green, ruled by Marcia (bless with amendments). The high-risk register audit was hand-authored from the corrected P08 map under SC-0089 — Marcia's map standard of 2026-09-28 and her SC-0089 rulings of 2026-09-29 (see P08-D4, P08-D5); her merge word on the SC-0089 package is owed.",
  "compilation_decisions": [
    {
      "decision_id": "P08-D1",
      "decision": "Deterministically compiled a MEANING_COORDINATES skeleton from the approved Meaning Map.",
      "description": "Extracted header/classification, scene + entity IDs + presence, verse-ranges, significant_absence, communicative purpose, proposition anchors/scene-links/cross-refs, and Section-5 concept/figure flags. 50 judgment fields left as typed placeholders for Agent 3. No values invented (extract-only)."
    },
    {
      "decision_id": "P08-D2",
      "decision": "Judgment gaps filled by the SC-0063 drafter (Slice 4).",
      "description": "claude-opus-4-8 under pinned prompt fm-drafter-0.1.2; structured-output fills merged by the patch-only layer (46 applied · 4 note-only · 0 rejected · 0 unfilled). Provenance: _working/P08/drafts/run-2026-06-12T07-25-05-695Z/."
    },
    {
      "decision_id": "P08-D3",
      "decision": "Marcia ruled: bless with amendments (2026-06-12).",
      "description": "P02-gold action idiom applied — the 7 commanded instruction steps re-encoded as action DIRECTED + commanded_step content (imperative forms do not enter the past-tense action axis); P1 STATES_HOPED_FOR_CONDITION and P9 STATES_AS_TRUE kept as drafted; 6 vocabulary additions CONFIRMED for promotion."
    },
    {
      "decision_id": "P08-D4",
      "decision": "High-risk register built under SC-0089 (the P07–P14 register-completion program opened by SC-0085): Marcia's map standard of 2026-09-28 and her SC-0089 rulings of 2026-09-29.",
      "description": "Her word to begin (2026-09-28): «sim, pode começar pela P08 e P10». Drafted from the corrected P08 map under her approved map standard (padrao-do-mapa, 2026-09-28, item 16 included) and her SC-0089 rulings (2026-09-29, «(b), (b), (a), sim — pode seguir com as recomendações»); the English wording of the entries is the builder's rendering, from the SC-0089 survey draft as corrected by its cross-check. One ruling touches this register: D1 (b) — at 3:1–2 the team keeps the text's word and adds. A telling that keeps \"a resting place\" and adds marriage or a husband, as 1:9 said, is accepted without comment, and the map's Section 2.2 carries the 1:9 words ('each in the house of her husband') that allow it; one that puts marriage in place of \"a resting place\" is offered back gently (R2). A telling that calls Boaz \"redeemer\" at 3:2 fills the silence recorded under SC-0053 and is offered back gently with \"our kinsman\" (R10). D2 (3:15) and D3 (fixes in approved passages) lie outside this file. 13 entries replace the R1 skeleton, 9 do_not_decide (R2 the Scene 1 silences, R3 Ruth asks nothing, R4 the rest-word, R5 the three steps of 3:3, R6 the place of his feet, R7 Naomi's last words, R8 Ruth's answer, R10 'our kinsman', R11 the minor text points): every never-rule sits in a do_not_decide entry (the SC-0088 lesson), and R8 is do_not_decide as a whole. R13, which is not do_not_decide, carries no never-clause (its 'never in the map' taken out at the integration step, as in P10 R13). Never-lists read 'For the voice only, never to be said' (standard item 16); R2, R3 and R10 end with 'Do not announce … before the team tells (item 16)'. Kinds: STRUCTURAL_FRAMING_DEVICE (R1, R12), CROSS_PERICOPE_PAIRING_CLOSED_HERE (R4), FIGURE_FIRST_OCCURRENCE (R5, R6), CROSS_PERICOPE_PAIRING_FIRST_OCCURRENCE (R7, R8) and NAMING_SHIFT (R9, R10) from the approved high_risk_register_kind list; SIGNIFICANT_ABSENCE (R2, R3), TEXTUAL_CLARITY_FLAG (R11) and DISCOURSE_THREAD_ADVANCED (R13) as in SC-0087 and SC-0088 (not on the approved list). Carried-forward items land: P02 R9 (T3 — R4, R13); P05 R8, P07 R12, P09 R14 (T2 — R10, R13); P09 R9 (R7); P09 R5 (R8); P09 R16 and SC-0086 ruling 1 (R6); P09 R10 (FIG_0139, canon record only — R13); P09 R15 and P11 R10 (R2); the P10 ruling of 2026-09-24, the team's reading stays theirs (R4). The P07 FIG_0113 row (PENDING; Marcia 2026-08-31: resolve at P08's register) is resolved here: FIG_0113 has no site in 3:1–5 and closes at P07 (R13). Pair table: FIG_0120 (P02 → P08) VERIFIED, closing here on the CB_0014 flags; FIG_0121 VERIFIED as a single occurrence; FIG_0122 and FIG_0123 VERIFIED, opening here and closing at P09. Forward links to P09 and P10 live only in this register (R7, R8, R13) and the pair table, never in the map. The three gate signals (the real audit, high_risk_register_complete, and the map's sta-status) flip together in this change."
    },
    {
      "decision_id": "P08-D5",
      "decision": "Meaning Map + MEANING_COORDINATES corrected under the 2026-09-28 standard and ruling D1 (b); B2 removed from the MEANING_COORDINATES S1, PL_NAOMIS_DWELLING from S1 and S2; the Scene 2 heading follows 3:5 ('she said').",
      "description": "The SC-0089 survey edits for P08 applied as corrected by its cross-check, with the cross-check's missed items (map Section 1, Sections 2.1–2.4, Scenes 1–2 3A–3F and Significant Absences, Section 4 Proposition 8, Sections 5A–5B): no future in Section 2.1, which the later passages' story-so-far hears ('what will happen in the dark', 'a handoff', 'the secure home a married woman has' and 'the risk to a foreign widow alone at night' out); 3:1 is not told as the answer to 1:9 — the rest-word of 1:9 comes again; no danger, risk or anger the text does not give; no intent ('softer', 'stays unspoken'); no passage IDs or pointers ahead (P07, 3:11, 'the next pericope', the verse list of the night scenes); 'our kinsman' for מֹדַעְתָּנוּ (the transliteration 'moda' corrected); the steps in the text's words ('know the place', 'do not be known'); Section 1 drops 'There is no public moment and no ceremonial lift inside this talk.' (a denial the voice reads). Missed items: the Scene 2 B9 heading 'וַתֹּאמֶר / \"she said\"' with the referential form '\"she\" (3:5)' and 3E 'She says to her' (3:5 does not say Ruth's name); the Scene 1 B9 referential form '\"my daughter\" in Naomi's words (3:1)'; B3's roles 'the one who speaks — her question, Boaz, the night, the threshing floor, and every step' (Scene 1) and 'the one Ruth answers' (Scene 2); B13's relationship 'of the clan of Elimelech (2:1)'. Made at the integration step (the builder's reported survivors; standard items 1 and 2; no register quote cites these lines): Scene 1 3E 'speaks to her' (3:1 says 'said to her' and gives no name); B3's relationship 'Boaz is a kinsman of her husband (2:1)' (was 'kinswoman by marriage to Boaz'); B13's relationship 'the owner of the field where Ruth gleaned until the end of the harvests (2:3, 2:23)' (was 'the field-owner Ruth gleaned beside all season'); B9's Scene 1 role 'the one Naomi asks \"shall I not seek a resting place for you?\"' (was 'the one the rest is sought for': the question is kept a question). Ruling D1 (b): Section 2.2 carries the 1:9 words ('when she wished that YHWH would grant each daughter-in-law rest, each in the house of her husband'), and the Scene 1 Significant Absence reads 'Naomi says \"a resting place\". After \"lie down\" she says only: he will tell you what you shall do. The word redeemer (2:20) is not said here; Naomi calls Boaz \"our kinsman\".' Elements the text does not have (standard items 1 and 10): B2 Elimelech removed from the MEANING_COORDINATES S1 beings (3:1–4 does not mention him; he stays in B3's relationship line); PL_NAOMIS_DWELLING removed from S1 and S2 (3:1–5 names no place for the talk) — the map's Section 3B Scene 2 reads 'None: the text names no place in this scene.', and the MEANING_COORDINATES S2 places are null with a _note (the P13 form). The MEANING_COORDINATES' two scene purposes and significant absences equal the map's 3F and Significant Absence texts word for word; the register_overrides _note mirrors Section 1. Map frontmatter sta-status set to complete. Unchanged (seen; not voiced, or not in this ruling): the pericope title ('Naomi's plan for rest; Ruth's total consent', listed for a later title pass), the scene titles, the Level-1 values, slot names and role values, and the entity slugs inside the links (the voice and the Validator see only the code)."
    },
    {
      "decision_id": "P08-D6",
      "decision": "Marcia's rulings of 2026-09-29, after the team's session: the Scene 1 silence without 'a resting place', the 1:9 words at the rest-word, and R9 to the Validator.",
      "description": "Her words (2026-09-29, afternoon, after the team's session): «(a), (a), sim — pode seguir com as recomendações». (1) The live goldens of 2026-09-29 read the Scene 1 absence ('Naomi says \"a resting place\". …') as 'the story does not say what the rest is' and treated an added marriage as a filled silence, once retracting a correct acceptance. Option (a): the sentence 'Naomi says \"a resting place\".' leaves the Scene 1 Significant Absence (map = MEANING_COORDINATES), which now reads 'After \"lie down\" she says only: he will tell you what you shall do. The word redeemer (2:20) is not said here; Naomi calls Boaz \"our kinsman\".' (the reading of P08-D5 is superseded), and the 1:9 words sit at the rest-word itself: Section 3C Scene 1 CB_0014 '- Cross-ref: the rest-word of 1:9 comes again (1:9 menuchah, 3:1 manoach); at 1:9 Naomi wished each daughter-in-law rest, \"each in the house of her husband\"' (her Portuguese: «a mesma palavra de 1:9, quando Noemi desejou a cada nora descanso, 'cada uma na casa do seu marido'»). R2's applies_to and first sentence no longer call 'a resting place' a silence (it is the text's word, which the telling keeps); R2 and R4 quote the new lines. (3) «pode seguir com as recomendações»: R9 (a named Ruth accepted without comment) is do_not_decide, with 'For the voice only, never to be said: a remark that the text does not say her name, when a team names Ruth; a team that names Ruth is accepted without comment (item 16).'; do_not_decide is now R2–R11 (10). The English wording is the builder's rendering of her Portuguese."
    }
  ],
  "vocabulary_additions": {
    "proposition_kinds": [],
    "scene_kinds": [
      {
        "value": "CONSENT_SCENE",
        "source": "P08-FOR-MODEL · SC-0063 drafter run-2026-06-12T07-25-05-695Z (claude-opus-4-8 · fm-drafter-0.1.2) · ruled by Marcia 2026-06-12",
        "status": "CONFIRMED",
        "note": "One-line total assent closing the plan exchange; RATIFICATION_SCENE rejected for legal/sealing connotation."
      }
    ],
    "presence_values": [],
    "referential_forms": [],
    "other": [],
    "arc_elements": [
      {
        "value": "REST_SEEKING_INITIATIVE",
        "source": "P08-FOR-MODEL · SC-0063 drafter run-2026-06-12T07-25-05-695Z (claude-opus-4-8 · fm-drafter-0.1.2) · ruled by Marcia 2026-06-12",
        "status": "CONFIRMED",
        "note": "Naomi opens by seeking menucha/rest for Ruth (3:1)."
      },
      {
        "value": "NIGHT_PLAN_INSTRUCTION",
        "source": "P08-FOR-MODEL · SC-0063 drafter run-2026-06-12T07-25-05-695Z (claude-opus-4-8 · fm-drafter-0.1.2) · ruled by Marcia 2026-06-12",
        "status": "CONFIRMED",
        "note": "The worked step-by-step night plan (3:2-4)."
      },
      {
        "value": "INITIATIVE_HANDOFF",
        "source": "P08-FOR-MODEL · SC-0063 drafter run-2026-06-12T07-25-05-695Z (claude-opus-4-8 · fm-drafter-0.1.2) · ruled by Marcia 2026-06-12",
        "status": "CONFIRMED",
        "note": "The plan ends handing the next word to Boaz (3:4c)."
      },
      {
        "value": "TOTAL_CONSENT",
        "source": "P08-FOR-MODEL · SC-0063 drafter run-2026-06-12T07-25-05-695Z (claude-opus-4-8 · fm-drafter-0.1.2) · ruled by Marcia 2026-06-12",
        "status": "CONFIRMED",
        "note": "Ruth assents whole: all you say I will do (3:5)."
      }
    ],
    "role_in_scene_beings": [
      {
        "value": "PLANNER",
        "source": "P08-FOR-MODEL · SC-0063 drafter run-2026-06-12T07-25-05-695Z (claude-opus-4-8 · fm-drafter-0.1.2) · ruled by Marcia 2026-06-12",
        "status": "CONFIRMED",
        "note": "Naomi names the goal, the man, the night, and every step (S1)."
      }
    ]
  },
  "proposition_kind_slot_sets": [],
  "high_risk_register_audit": [
    {
      "id": "R1",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "Naomi's plan at 3:1–4 (P1–P8): the question, the name, the time and place, and the steps in the text's order",
      "note": "REQUIRED keep, in this order: Naomi's question — my daughter, shall I not seek a resting place for you, that it may be well with you? (3:1); and now, is not Boaz our kinsman, with whose young women you were? he is winnowing the barley at the threshing floor tonight (3:2); wash, anoint yourself, put your garments on you, and go down to the threshing floor; do not be known to the man until he has finished eating and drinking (3:3); when he lies down, know the place where he lies; go in, uncover the place of his feet, and lie down; and he will tell you what you shall do (3:4). The order of the steps is kept (item 1); a step told in another place in the order is offered back gently. One or two small steps missing, outside the first telling, are the team's choice (for example 'anoint yourself'). The question of 3:1 means that Naomi will seek the resting place: a telling that says it as a statement ('I will seek', 'I must seek a resting place for you') keeps the meaning and is accepted without comment; a telling that has Naomi say she will not seek it (the question lost, so it reads as a refusal) is offered back gently with the text's words. 'Is not Boaz our kinsman?' told as 'Boaz is our kinsman' is accepted without comment.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3E Scene 1 (the whole speech); Section 2.1 ('Naomi opens with a question that means she will seek it: my daughter, shall I not seek a resting place for you, that it may be well with you?'; 'Then the instructions, step by step'); Section 3F Scene 1 ('Naomi asks Ruth: shall I not seek a resting place for you, that it may be well with you?'; 'and gives the steps'); Section 2.3 ('Naomi's speech goes in small steady steps'); Section 4 Propositions 1–8"
    },
    {
      "id": "R2",
      "kind": "SIGNIFICANT_ABSENCE",
      "applies_to": "Scene 1 (3:1–4): Naomi's word 'a resting place', the text's word the telling keeps (ruling D1 (b)); the Scene 1 silences: nothing said after 'lie down' but 'he will tell you what you shall do'; the name of God not said; no reason given for the steps",
      "note": "Naomi says 'a resting place' (3:1): that is the text's word, which the telling keeps; it is not a silence. Silences kept as facts: after 'lie down' she says only that he will tell her what she shall do; Naomi gives no reason for any step; no one says the name of God in 3:1–5. For the voice only, never to be said: do not tell the plan as a marriage plan or say that Naomi wants a husband for Ruth; a team telling that keeps \"a resting place\" and adds marriage or a husband, as 1:9 said, is accepted without comment; one that puts marriage in place of \"a resting place\" is offered back gently. For the voice only, never to be said: do not say what the man will tell her, what Ruth is to ask, or what will happen at the threshing floor; bring in no danger, fear, shame or secrecy the text does not give ('risky', 'dangerous', 'if the man is angry'); do not explain why she must wash, anoint and dress, or why she must not be known to the man; bring in no custom or law the story does not cite; put no prayer and no act of God into Naomi's plan (item 4). Do not announce these silences before the team tells (item 16).",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Significant Absence in Scene 1 ('After \"lie down\" she says only: he will tell you what you shall do.'); Section 3C Scene 1 (CB_0014 'the rest-word of 1:9 comes again (1:9 menuchah, 3:1 manoach); at 1:9 Naomi wished each daughter-in-law rest, \"each in the house of her husband\"'); Section 2.1 ('what the plan leaves open: after \"lie down\", Naomi says only that he will tell her what to do.'); Section 2.2 ('when she wished that YHWH would grant each daughter-in-law rest, each in the house of her husband'); Section 2.3 ('each one plain, none explained'); Section 3C Scene 1 (CB_0042 'the text says only that Naomi tells Ruth to uncover it'); carried from P09 R15 and P11 R10 (the marriage is not told before 4:13); ruling D1 (b) of 2026-09-29"
    },
    {
      "id": "R3",
      "kind": "SIGNIFICANT_ABSENCE",
      "applies_to": "Scene 2 (3:5, P9): Ruth asks nothing; she answers in one line; the narrator does not say what she thinks or feels",
      "note": "Ruth asks nothing and answers in one line: all that you say I will do. The narrator does not say what she thinks or feels. A telling in which Ruth asks Naomi a question fills this silence: offer it back gently. 'Ruth said she would do everything', 'Ruth said yes to all of it' keep the meaning; accept without comment. For the voice only, never to be said: give Ruth no fear, doubt, eagerness or love; give her no reason (that she trusted, obeyed or wanted it); add no praise or blame for her answer. Do not announce this silence before the team tells (item 16).",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Significant Absence in Scene 2 ('Ruth asks nothing; she answers in one line. The narrator does not say what she thinks or feels.'); Section 3F Scene 2 ('Ruth answers Naomi in one line: all that you say I will do.'); Section 3A Scene 2 (B9 'the one who answers: all that you say I will do'); Section 4 Proposition 9"
    },
    {
      "id": "R4",
      "kind": "CROSS_PERICOPE_PAIRING_CLOSED_HERE",
      "applies_to": "FIG_0120 + CB_0014 at 3:1 (P1) — CLOSES here: the rest-word of 1:9 (menuchah; P02 P6, the P02 map's Proposition 5) comes again at 3:1 (manoach); T3 station (P02 R9)",
      "note": "PREFERRED keep-image: 'a resting place' (manoach) — the rest-word of 1:9, where Naomi wished that YHWH would grant each daughter-in-law rest (menuchah). Keep the same rest-word as at 1:9 where the language allows; a team rendering that keeps the idea of rest ('lugar de descanso') is correct without comment. The voice may say that the same word comes again. For the voice only, never to be said: do not say that 3:1 answers or fulfils the wish of 1:9, or that Naomi now does what she asked God to do; a team reading that it does (for example 'a oração de Noemi está se cumprindo') stays the team's reading — the voice does not confirm it and adds no link the map does not make (item 13).",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3C Scene 1 (CB_0014 '\"a resting place\" (manoach), a place of rest'; 'the rest-word of 1:9 comes again (1:9 menuchah, 3:1 manoach); at 1:9 Naomi wished each daughter-in-law rest, \"each in the house of her husband\"'); Section 2.2 ('Naomi's word for rest here (manoach) is the rest-word of 1:9 (menuchah), when she wished that YHWH would grant each daughter-in-law rest'); Section 2.4 ('The rest-word of 1:9 comes again here.'); Section 5A (CB_0014 'the rest-word of 1:9 comes again: \"a resting place\"'); Section 5B (FIG_0120 'the rest-word of 1:9 comes again at 3:1'); Section 4 Proposition 1; carried from P02 R9 (T3) and the P10 ruling of 2026-09-24 (the team's reading stays theirs)"
    },
    {
      "id": "R5",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0121 at 3:3a (P4): wash, anoint yourself, put your garments on you — then go down; O13",
      "note": "PREFERRED keep-image: the three steps in their order — wash, anoint yourself, put your garments on you — and then go down to the threshing floor. For the voice only, never to be said: do not call it a bride's preparation, a wedding custom or making herself beautiful for him, and give no reason for the three steps (the text gives none).",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 1 ('Wash, anoint yourself, put your garments on you, and go down to the floor.'); Section 3C Scene 1 (O13 'the third step: put your garments on you'); Section 5B (FIG_0121 'the wash–anoint–garments triple'); Section 4 Proposition 4"
    },
    {
      "id": "R6",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "CB_0042 'the place of his feet' (margelot) at 3:4b (P7); the lie-down steps at 3:4 (P6, P7); carried from P09 R16 and P09 ruling 1",
      "note": "REQUIRED keep: go in, uncover the place of his feet, and lie down — the three last steps, in this order. The voice may explain the word: margelot is the place of his feet. A telling that says only that she finds or looks for where his feet are has lost 'uncover': offer it back gently with the text's words. For the voice only, never to be said: do not decide what the uncovering and the lying down mean; add no touch, no word of love or desire, no verdict — neither that something will happen nor that nothing will (P09 R16); never 'fold the covering back', never 'while he sleeps' (P09 ruling 1).",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3C Scene 1 (CB_0042 'the place of his feet (margelot); the text says only that Naomi tells Ruth to uncover it'; 'the plan's last steps: go in, uncover the place of his feet, and lie down'); Section 3E Scene 1 ('go in, uncover the place of his feet, and lie down'); Section 5A (CB_0042 'the place of his feet; the same word comes again later in the story'); Section 4 Propositions 6 and 7; carried from P09 R16 and SC-0086 ruling 1"
    },
    {
      "id": "R7",
      "kind": "CROSS_PERICOPE_PAIRING_FIRST_OCCURRENCE",
      "applies_to": "FIG_0122 at 3:4c (P8) — opens; closes at P09 P18–P19 (FIG_0140, P09 R9)",
      "note": "REQUIRED keep: Naomi's last words, 'and he — he will tell you what you shall do', kept as Naomi's word about what the man will do, not as a thing told as done. For the voice only, never to be said: do not tell in this passage what the man will say or who will speak first at the threshing floor; never say that anyone hands over, passes or gains the initiative or authority (P09 R9). In the canon record FIG_0122 closes at P09 (3:13, FIG_0140); that link stays here and in the pair table only and is not part of P08's telling.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 1 ('And he — he will tell you what you shall do.'); Section 2.1 ('The plan ends: he will tell you what you shall do.'); Section 3F Scene 1 ('She ends: he will tell you what you shall do.'); Section 5B (FIG_0122 'Naomi's words: he will tell you what you shall do'); Section 4 Proposition 8 ('Who, Naomi says, will tell her?'); carried from P09 R9"
    },
    {
      "id": "R8",
      "kind": "CROSS_PERICOPE_PAIRING_FIRST_OCCURRENCE",
      "applies_to": "FIG_0123 at 3:5 (P9) — opens; closes at P09 P14 (FIG_0136, P09 R5)",
      "note": "PREFERRED keep-image: Ruth's one-line answer whole — all that you say I will do. The Hebrew reads 'all that you say to me' ('to me' is read, not written); with or without 'to me' is correct, accepted without comment. In the canon record the same words come back in Boaz's mouth at 3:11 (P09 R5, FIG_0136); that link stays here and in the pair table only and is not part of P08's telling. The map says only that the same words come again later in the story.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 2 ('She says to her: all that you say I will do.'); Section 5B (FIG_0123 'Ruth's words: all that you say I will do; the same words come again later in the story'); Section 3F Scene 2 ('Ruth answers Naomi in one line: all that you say I will do.'); Section 4 Proposition 9; carried from P09 R5"
    },
    {
      "id": "R9",
      "kind": "NAMING_SHIFT",
      "applies_to": "Naomi 'Naomi her mother-in-law' (P1); Ruth \"my daughter\" (P1) and \"she\" (P9); her name is not said in 3:1-5; Boaz 'Boaz our kinsman' (P2), then 'the man' (P5) and 'he' (P8)",
      "note": "PREFERRED: the narrator names Naomi with her kinship word, 'Naomi her mother-in-law'. Naomi calls Ruth \"my daughter\"; Ruth's name is not said in 3:1-5. Boaz is named once, 'Boaz our kinsman', then only 'the man' and 'he'. A telling that names Ruth or Boaz where the text does not keeps the meaning and is accepted without comment (item 11). For the voice only, never to be said: a remark that the text does not say her name, when a team names Ruth; a team that names Ruth is accepted without comment (item 16).",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3A Scene 1 (B3 'the narrator gives both the name and the kinship-word together — \"Naomi her mother-in-law\"'; B9 '\"my daughter\" in Naomi's words (3:1)'; B13 '\"Boaz our kinsman\" (מֹדַעְתָּנוּ, a family word) at v.2; then only \"the man\" at v.3 and \"he\" at v.4'); Section 3A Scene 2 (B9 'וַתֹּאמֶר / \"she said\"'; '- Referential form: \"she\" (3:5)'); Section 3E Scenes 1 and 2; Section 4 Propositions 1, 2, 5, 8 and 9"
    },
    {
      "id": "R10",
      "kind": "NAMING_SHIFT",
      "applies_to": "Boaz 'our kinsman' (מֹדַעְתָּנוּ) at 3:2 (P2): the family word; the redeemer word (2:20) not said in 3:1–5 (SC-0053's blessed non-flag of CB_0001; ruling D1 (b)); T2 station (P05 R8, P07 R12, P09 R14)",
      "note": "Naomi calls Boaz 'our kinsman' (מֹדַעְתָּנוּ), a family word; the word redeemer, which Naomi said at 2:20, is not said in 3:1–5. In a team telling, 'parente', 'relative', 'kinsman' or 'da nossa família' are correct here; accept them without comment — the rule that the redeemer is never 'kinsman' or 'relative' (P09 R14, P11 R15, P13 R2) is for the redeemer word (go'el), which this verse does not use (item 7). For the voice only, never to be said: do not call Boaz the redeemer in this passage; do not say that Naomi avoids, keeps back or softens the redeemer word, or why she says 'our kinsman'. A telling that calls Boaz \"redeemer\" at 3:2 fills the silence recorded here (SC-0053): offer it back gently with \"our kinsman\". Do not announce this silence before the team tells (item 16).",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3A Scene 1 (B13 '\"Boaz our kinsman\" (מֹדַעְתָּנוּ, a family word) at v.2'); Significant Absence in Scene 1 ('The word redeemer (2:20) is not said here; Naomi calls Boaz \"our kinsman\".'); Section 2.2 ('At 2:20 Naomi told Ruth that the man is near to them, one of their redeemers; here she calls Boaz \"our kinsman\" (מֹדַעְתָּנוּ), a family word.'); Section 4 Proposition 2; carried from P05 R8, P07 R12, P09 R14; SC-0053 group C; ruling D1 (b) of 2026-09-29"
    },
    {
      "id": "R11",
      "kind": "TEXTUAL_CLARITY_FLAG",
      "applies_to": "minor text points at 3:2 (P3), 3:3 (P4, P5), 3:4 (P6, P7) and 3:5 (P9)",
      "note": "Minor text points. (1) 3:3: the written Hebrew has 'your garment' (one), read 'your garments'; one garment or several are both correct. (2) 3:3 'go down' and 3:4 'lie down': the written Hebrew has forms that look like 'I will go down', 'I will lie down'; they are read 'you will go down', 'you will lie down'. The voice follows the map — Ruth goes down, Ruth lies down — and does not teach the written forms. (3) 3:3: 'do not be known to the man' and 'do not let the man know you are there' are both correct. (4) 3:4: 'know the place where he lies' means notice it or mark it; both are correct. (5) 3:2: 'tonight' is 'the night' in Hebrew — this night. (6) 3:5: see R8 ('to me' read, not written). All of these are accepted without comment; the voice does not teach the variants.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 1 ('put your garments on you, and go down to the floor'; 'Do not be known to the man until he has finished eating and drinking.'; 'When he lies down, know the place where he lies; go in, uncover the place of his feet, and lie down.'; 'Behold, he is winnowing the barley at the [[PL6-Threshing-Floor]] threshing floor tonight.'); Section 3C Scene 1 (O13 heading 'שִׂמְלֹתַיִךְ / \"your garments\"'); Section 3D Scene 1 ('\"tonight\" is in Naomi's words — the night of the winnowing'); Section 4 Propositions 3–7 and 9; checked against _spec/source/ruth/P08.json (BHSA 2021: ketiv שׂמלתך, וירדתי, ושׁכבתי; qere אֵלַי at 3:5)"
    },
    {
      "id": "R12",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "register: whole passage INFORMAL_CASUAL; Scenes 1 and 2 INTIMATE at scene level",
      "note": "The whole passage sits in INFORMAL_CASUAL. Both scenes are INTIMATE at scene level: the whole passage is a talk between Naomi and her daughter-in-law — Naomi's plan and Ruth's one-line answer. The narrator frames only the speech-openings at 3:1 and 3:5.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 1 Metadata multi-level register tagging ('The whole passage sits in INFORMAL_CASUAL. Both scenes shift to INTIMATE at scene level: the whole passage is a talk between Naomi and her daughter-in-law — Naomi's plan and Ruth's one-line answer.'; 'The narrator's voice frames only the speech-openings at v.1 and v.5.'); MEANING_COORDINATES register_overrides (scene_level S1 and S2 INTIMATE)"
    },
    {
      "id": "R13",
      "kind": "DISCOURSE_THREAD_ADVANCED",
      "applies_to": "T3 rest (P02 R9) and T2 line-and-redemption (P05 R8, P07 R12, P09 R14) at 3:1–5; canon-record forward links (FIG_0122 → P09, FIG_0123 → P09, CB_0042 → P09/P10, the lie-down word → P09); FIG_0113 not here",
      "note": "T3 (rest; opened at 1:9, P02 R9): the rest-word comes again at 3:1 (R4); the map recalls the 1:9 words 'each in the house of her husband' (Section 2.2), and the plan is not told as a marriage plan (R2; ruling D1 (b)). T2 (line and redemption): Naomi names Boaz 'our kinsman'; the redeemer word is not said (R10). Canon-record forward links, recorded only here and in the pair table: FIG_0122 closes at P09 3:13 (FIG_0140, P09 R9); FIG_0123 closes at P09 3:11 (FIG_0136, P09 R5); CB_0042 comes again at 3:7, 3:8 (P09) and 3:14 (P10); the lie-down word of 3:4 runs through the night (3:7, 3:8, 3:13; FIG_0139, P09 R10). FIG_0113 (the leftover after satiety, 2:18) has no site in 3:1–5 and is not flagged here; it closes at P07 (SC-0053 D2, SC-0056).",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 2.2 ('Naomi's word for rest here (manoach) is the rest-word of 1:9 (menuchah)'; 'each in the house of her husband'; 'here she calls Boaz \"our kinsman\" (מֹדַעְתָּנוּ), a family word'); Section 2.4 ('The rest-word of 1:9 comes again here.'); Section 5A (CB_0042 'the same word comes again later in the story'); Section 5B (FIG_0122, FIG_0123); carried from P02 R9, P05 R8, P07 R12, P09 R5, R9, R10, R14, R15, R16; the P07 FIG_0113 pair row (Marcia 2026-08-31: resolve at P08's register)"
    }
  ],
  "cross_pericope_pair_verification": {
    "pairs": [
      {
        "fig_id": "FIG_0120",
        "opens_at": "P02 P6 (1:9a Naomi's wish: rest, menuchah; the P02 map's Proposition 5; flagged there as CB_0014 only)",
        "closes_at": "P08 P1 (3:1 'a resting place', manoach; CB_0014 + FIG_0120)",
        "verification_status": "VERIFIED",
        "note": "Pair closed at this register (R4), on the CB_0014 flags at both ends: the P02 MEANING_COORDINATES flags CB_0014 at P6 (1:9a; the P02 map lists it at its Proposition 5), and the P08 MEANING_COORDINATES flags CB_0014 and FIG_0120 at P1 (3:1). The P02 map and MEANING_COORDINATES do not flag FIG_0120 itself, although the registry (vault note) lists opens-at P02 / closes-at P08; P02 is approved and is not changed here (known_limitations). Recorded as the same rest-word coming again, never as 3:1 answering or fulfilling 1:9 (R4)."
      },
      {
        "fig_id": "FIG_0121",
        "opens_at": "P08 P4 (3:3a wash, anoint yourself, put your garments on you)",
        "closes_at": "P08 P4 (single occurrence)",
        "verification_status": "VERIFIED",
        "note": "Single occurrence (R5): the P08 MEANING_COORDINATES flags FIG_0121 at P4 only. Registry frontmatter (vault note) confirms opens-at P08 / closes-at P08. The vault note's slug 'Bridal-Preparation-Triplet' and its intended-meaning ('bridal/ceremonial overtones') carry a reading R5 forbids; the voice and the Validator see only the code; alignment listed for the vault half."
      },
      {
        "fig_id": "FIG_0122",
        "opens_at": "P08 P8 (3:4c 'he will tell you what you shall do')",
        "closes_at": "P09 P18-P19 (3:13 the next step sent to the morning; FIG_0140)",
        "verification_status": "VERIFIED",
        "note": "Opening half of the pair closed at P09 (P09 R9), on the two maps and MEANING_COORDINATES: the P08 MEANING_COORDINATES flags FIG_0122 at P8, the P09 MEANING_COORDINATES flags FIG_0140 at P18 and P19. P08's register records the opening (R7). Registry frontmatter (vault note) confirms opens-at P08 / closes-at P09. Canon-record link only; in P08's telling the words stay Naomi's word about what the man will do (R7)."
      },
      {
        "fig_id": "FIG_0123",
        "opens_at": "P08 P9 (3:5 Ruth to Naomi, 'all that you say I will do')",
        "closes_at": "P09 P14 (3:11 Boaz to Ruth, 'all that you say I will do for you'; FIG_0136)",
        "verification_status": "VERIFIED",
        "note": "Opening half of the pair closed at P09 (P09 R5), on the two maps and MEANING_COORDINATES: the P08 MEANING_COORDINATES flags FIG_0123 at P9, the P09 MEANING_COORDINATES flags FIG_0123 and FIG_0136 at P14. P08's register records the opening (R8). Registry frontmatter (vault note) confirms opens-at P08 / closes-at P09. Canon-record link only; the P08 map says only that the same words come again later in the story."
      }
    ]
  },
  "validation_checklist": {
    "meaning_map_contains_only_story_content": true,
    "meaning_coordinates_contains_only_inference_signal": true,
    "every_proposition_has_cb_flags_and_figure_flags": true,
    "no_grammatical_frame_slot_names": true,
    "speech_act_present_on_all_component_records": true,
    "speech_act_values_used": [
      "DIRECTS_HEARER_NOT_TO_DO",
      "DIRECTS_HEARER_TO_DO",
      "STATES_AS_TRUE",
      "STATES_HOPED_FOR_CONDITION"
    ],
    "discourse_threads_tracked_in_audit_only": true,
    "known_limitations_tracked_in_audit_only": true,
    "high_risk_register_complete": true,
    "every_high_risk_entry_traces_to_meaning_map": true,
    "no_content_added_beyond_meaning_map": true,
    "registry_additions_extracted_to_bcd_delta": true,
    "no_reviewer_facing_prompts_in_compilation_log": true
  },
  "known_limitations": [
    "Judgment half machine-drafted under SC-0063 and ruled by the reviewer (bless with amendments, 2026-06-12).",
    "The high-risk register audit was hand-authored from the corrected P08 map under SC-0089: 13 entries (10 do_not_decide: R2–R11 — R9 since Marcia's word of 2026-09-29 after the team's session, P08-D6), each traced to the P08 map; the carried-forward items (P02 R9, P05 R8, P07 R12, P09 R5/R9/R10/R14/R15/R16, P11 R10) also cite their source registers (P08-D4). Marcia's merge word on the SC-0089 package is owed.",
    "Propositions stay at meaning-map granularity (9); P4 and P7 decompose in-slot via instruction_components per the granularity contract.",
    "Commanded steps are content (commanded_step), not action-axis values — Marcia idiom ruling 2026-06-12.",
    "Data gap, not changed here: the MEANING_COORDINATES P4 and P7 instruction_components carry only action DIRECTED + step_order (plus garment O13, destination PL6 and uncovered_place CB_0042); the step contents P08-D3 describes as commanded_step content (wash, anoint yourself, put your garments on you, go down; go in, uncover the place of his feet, lie down) are not in the MEANING_COORDINATES. For a later slice.",
    "Forward links out of P08 (FIG_0122 and FIG_0123 to P09; CB_0042 to P09 and P10; the lie-down word, FIG_0139, to P09) live only in this register (R7, R8, R13) and the pair table; the map carries none.",
    "FIG_0120's opening half: the registry (vault note) lists opens-at P02 / closes-at P08, but the P02 map and MEANING_COORDINATES flag only CB_0014 at 1:9 (MEANING_COORDINATES P6; the map's Proposition 5), not FIG_0120. The pair is verified on the CB_0014 flags at both ends; P02 is approved and is not changed here.",
    "Registry (vault note) data to align in the vault half: FIG_0121's slug 'Bridal-Preparation-Triplet' and intended-meaning ('bridal/ceremonial overtones') carry a reading R5 forbids; FIG_0120's surface-image ('rest as secure household-place for a married woman') carries the gloss the map no longer makes; FIG_0122's surface-image ('the speaker hands the next instruction to a third party') carries the handoff reading P09 R9 forbids; B13 and B16 appears-in lack P08, which the P08 map has; PL_NAOMIS_DWELLING appears-in lists P08, removed here; the CB_0001 note's P08 listing is residue (SC-0053: CB_0001 is not flagged at 3:2); FIG_0136 appears-in P08 is the pair anchor only.",
    "Three kinds in this register are not on the approved high_risk_register_kind list — SIGNIFICANT_ABSENCE (R2, R3), TEXTUAL_CLARITY_FLAG (R11) and DISCOURSE_THREAD_ADVANCED (R13); they are used as in SC-0087 and SC-0088 and join the register-kind call owed there.",
    "The MEANING_COORDINATES keep ruled values unchanged by SC-0089 and not voiced that carry readings the map no longer makes: arc_element INITIATIVE_HANDOFF and TOTAL_CONSENT, tone_element ANTICIPATORY, communicative_function WITHHOLDS, B3 role PLANNER; P8 proposition_kind HANDED with the slot future_speaker and speech_act STATES_AS_TRUE ('he will tell you' is Naomi's word about what the man will do); P9 speech_act STATES_AS_TRUE and assent_completeness TOTAL_NO_QUESTIONS; the referential_form token OUR_KINSMAN_MODA ('moda' is not the word of 3:2; the map reads מֹדַעְתָּנוּ, 'our kinsman'). Recorded for a future slot-name and value lint pass (like SC-0070).",
    "The vocabulary_additions notes (the dated 2026-06-12 ruling record) quote the map as it stood before SC-0089 (PLANNER 'Naomi names the goal, the man, the night, and every step', INITIATIVE_HANDOFF 'The plan ends handing the next word to Boaz', CONSENT_SCENE 'One-line total assent'); they are kept as history, not as current map text.",
    "The pericope title 'Naomi's plan for rest; Ruth's total consent' (map, MEANING_COORDINATES and this log) is seen and not changed under SC-0089; it is listed for a later title pass. Link slugs that carry a reading stay in canon for human readers, not changed here: CB_0014 Rest-Menucha, CB_0042 Uncover-Feet-Margelot, FIG_0120 Manoach-Rest-Place, FIG_0121 Bridal-Preparation-Triplet, FIG_0123 Absolute-Assent-Pattern; the voice and the Validator see only the code."
  ]
}
```

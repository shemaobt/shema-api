---
type: "sta-compilation-log"
pericope: "P10"
status: "valid"
pilot: "pilot-2"
---

# P10 — Ruth 3:14-18 — COMPILATION-LOG

```json
{
  "sta_id": "ruth_pericope_10_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Ruth 3:14-18",
  "pericope_id": "P10",
  "pericope_title": "The nameless dawn: six measures home, and sit still",
  "compiled_at": "2026-05-29",
  "review_status": {
    "meaning_map_status": "PARSED_BY_COMPILER",
    "sta_compilation_status": "MODEL_DRAFTED_REVIEWER_RULED",
    "community_verified": false,
    "translation_team_verified": false,
    "consultant_review_required": true,
    "production_use": false
  },
  "confidence_overall": "MEDIUM",
  "confidence_overall_note": "Judgment half machine-drafted (SC-0063, patch-only contract) and ruled by Marcia axis-by-axis under SC-0064 (§A–§E + arc_element). The graduated MEANING_COORDINATES validates block-clean with 0 convergent drift and is lint-clean. Mechanized log: vocabulary_additions are this pericope's ruled mints; the high-risk register audit was hand-authored from the corrected P10 map under Marcia's map standard of 2026-09-28 and her SC-0089 rulings of 2026-09-29 (see P10-D4, P10-D5).",
  "compilation_decisions": [
    {
      "decision_id": "P10-D1",
      "decision": "Deterministically compiled a MEANING_COORDINATES skeleton from the approved Meaning Map.",
      "description": "Extracted header/classification, scene + entity IDs + presence, verse-ranges, significant_absence, communicative purpose, proposition anchors/scene-links/cross-refs, and Section-5 concept/figure flags. 60 judgment fields left as typed placeholders for Agent 3. No values invented (extract-only)."
    },
    {
      "decision_id": "P10-D2",
      "decision": "Judgment gaps filled by the SC-0063 drafter (Slice 4).",
      "description": "claude-opus-4-8 under the pinned fm-drafter prompt; structured-output fills merged by the patch-only layer. Provenance: _working/P10/drafts/run-2026-06-12T15-09-36-789Z/."
    },
    {
      "decision_id": "P10-D3",
      "decision": "Ruled by Marcia under SC-0064 (the batch ruling), axis by axis.",
      "description": "§A–§E + the five §B axes (action+tone, proposition_kind, role_in_scene_being, scene_kind, arc_element) ruled across 2026-06-12→19; 4 vocabulary addition(s) CONFIRMED for promotion for this pericope (per-axis ruling-logs in _working/P10/P10-SC-0064-*-RULING-LOG.md). Renames/collapses applied to the MEANING_COORDINATES as recorded amendments where ruled."
    },
    {
      "decision_id": "P10-D4",
      "decision": "High-risk register built under SC-0089 (the P07–P14 register-completion program opened by SC-0085): Marcia's map standard of 2026-09-28 and her SC-0089 rulings of 2026-09-29.",
      "description": "Her word to begin (2026-09-28): «sim, pode começar pela P08 e P10». Her word on the standard (padrao-do-mapa, 2026-09-28): «(a), sim, pode seguir com as recomendações», item 16 included. Her SC-0089 rulings (2026-09-29): «(b), (b), (a), sim — pode seguir com as recomendações» — D1 (b), D2 (b), D3 (a), and every recommendation of the cross-check approved. The English wording of the entries is the builder's rendering, from the SC-0089 survey draft as corrected by its cross-check. 13 entries replace the R1 skeleton, 7 do_not_decide (R1 the Scene 1 silences, R2 the dawn and 'let it not be known', R4 the word 'empty' of 1:21 said again, R5 'who are you, my daughter?', R6 Naomi's closing words, R9 Ruth's report, R10 'and he went into the town'). Every never-rule is in a do_not_decide entry (the SC-0088 lesson); R7 is the canon record only ('Canon record: FIG_0156 opens here (3:18b) and closes at P11 P1 (4:1); VERIFIED in the P11 register (R11).'), and R13's canon-record sentence carries no never-clause. Ruling D2 (b) is in R10: the voice tells 'he goes into the town' (וַיָּבֹא, her SC-0056 reading), a team telling 'she went into the town' is offered back gently with the map's reading, as at 4:5 (P11 R13), and the voice never teaches the other reading. The survey's doubt on 'who are you, my daughter?' was settled by the cross-check (approved in her «pode seguir com as recomendações»): 'como foi, minha filha?' keeps the meaning and loses only the 3:9 echo — a nuance, named once, not sent back (her 2026-09-24 nuance ruling (b)); 'The text does not say what Naomi means by the question' lives only in R5, not in any absence. Cross-check corrections in the register: R1 gives the order as the reason ('those words come only in Ruth's report (3:17); told at the threshing floor, they move earlier in the telling') and carries the item-16 sentence; R9 keeps both sides of Boaz's condition. Never-lists read 'For the voice only, never to be said' (standard item 16). Kinds: STRUCTURAL_FRAMING_DEVICE (R2, R6, R9, R12), NAMING_SHIFT (R3), CROSS_PERICOPE_PAIRING_CLOSED_HERE (R4), FIGURE_FIRST_OCCURRENCE (R5, R8) and CROSS_PERICOPE_PAIRING_FIRST_OCCURRENCE (R7) from the approved high_risk_register_kind list; SIGNIFICANT_ABSENCE (R1), TEXTUAL_CLARITY_FLAG (R10, R11) and DISCOURSE_THREAD_ADVANCED (R13) as in SC-0087 and SC-0088 (not on the approved list). Carried-forward items land: P04 R5 (R4); P09 R9, R16 (R9; R16 also R2); P09 R10 (R8); P09 R13 (R3); P09 R14, P05 R8, P07 R12 (R13); P09 R15, P11 R10 (R6); P11 R11 and the P11 FIG_0156 row (R7). Pair table: FIG_0153 (P04 → P10) VERIFIED, closing here on CB_0044; FIG_0156 (P10 → P11) VERIFIED, mirrored from the P11 row; FIG_0150, FIG_0151, FIG_0152, FIG_0154 and FIG_0155 VERIFIED within the pericope; no flag and no row for FIG_0139 (closes at P09; its words recorded in R8) or FIG_0142 (no firing site in 3:14–18). The forward link to P11 lives only in this register (R7, R13) and the pair table, never in the map. The three Sala signals (the real audit, high_risk_register_complete, and the map's sta-status) flip together in this change."
    },
    {
      "decision_id": "P10-D5",
      "decision": "Meaning Map + MEANING_COORDINATES corrected under the 2026-09-28 standard; the Scene 2 title under ruling D3 (vi); B3 out of the MEANING_COORDINATES Scene 1, PL_NAOMIS_DWELLING out of Scene 2, CB_0024 out of the Scene 2 objects.",
      "description": "The standard applied to the map and the MEANING_COORDINATES together (the SC-0089 survey edits with every cross-check correction): no answer or reversal links ('answer the book's oldest wound', 'the structural turn from emptying to filling', 'the filling has begun') — the backward links go only through words the Hebrew repeats (reqam 1:21 / 3:17; 'who are you' 3:9 / 3:16; 'let it not be known' 3:3 / 3:14; 'until the morning' 3:13 / 3:14; margelot 3:4, 7, 8 / 3:14); no readings of the gift ('aimed at Naomi', 'for the house', 'evidence', 'proof', 'weighed' — the verb is 'measured'); the three readings of 'who are you' out of the voice's text (item 15); 'redeemer', never 'kinsman', for the go'el (item 7), with Boaz's 3:12–13 words at night kept on both sides of his condition (item 2); Naomi's words kept as her words ('the man will finish the matter today' and 'the matter is his today' out); no denials worded as form orders ('no one is named', 'no \"I am Ruth\"'; items 11 and 16); no pointers ahead ('the matter moves toward the town', 'pair opens here', 'final', 'sets the story down to wait'); no images ('gray', 'sack', 'as the dawn parts them', 'a held breath'); 'home' out where the text says 'to her mother-in-law' (3:16). Section 2.1, which P11–P14 hear, quotes 3:18 as Naomi says it ('until she knows how the matter falls'). Her ruled 'keep the secret Boaz asked for (3:14)' (SC-0087 R-9) stays in Section 2.4. Ruling D3 (vi): Scene 2's title is 'To her mother-in-law: the question, the report, and \"sit still\" (3:16–18)' (was 'Home: …'); its team-facing Portuguese label is the app's. Elements the text does not have: B3 (Naomi) out of the MEANING_COORDINATES Scene 1 beings (3:14–15 has no word of the mother-in-law), and B13's Scene 1 referential_form HA_ISH_THE_MAN with it (in 3:14–15 he is only 'he'); PL_NAOMIS_DWELLING out of Scene 2 (3:16–18 names no place) — map Section 3B reads '- None: the text names no place in this scene.' (the P08/P13 form), the MEANING_COORDINATES places are null with a _note, and P7's 'where' slot is gone. Duplicate: CB_0024 out of the MEANING_COORDINATES Scene 2 objects (one word, 'empty', at 3:17 is counted once, under CB_0044, as SC-0088 did for P12 CB_0009 and P14 CB_0005/0047/0048); it stays a concept flag at P11 and in Section 5A, and the map's Section 3C keeps its entry (the P14 form). The MEANING_COORDINATES' two scene purposes and significant absences equal the map's 3F and Significant Absence texts word for word; the register_overrides _note drops 'the two women alone again'. Map frontmatter sta-status set to complete. Builder choices named for review: (1) the Scene 1 B13 Relationship keeps the survey's 'if the nearer redeemer will redeem you, good' and takes the cross-check's full second branch 'if he does not want to redeem you, I will redeem you (3:12–13)', so the line says who 'he' is; R6 and R9 quote it; (2) quotations inside the new Section 2.1/2.2 prose use double quotation marks, as the rest of the map and the cross-check's Section 2.4 do. Made at the integration step (the builder's reported wording problems; standard items 1 and 2): the Scene 1 3F and the MEANING_COORDINATES S1 purpose 'He says: hold out the cloak that is on you; she holds it, and he measures six measures of barley and lays it on her' (was 'He measures six measures of barley into the cloak she holds'; 3:15 does not say 'into the cloak'; Section 2.1 already had it so); the Scene 2 B13 Role 'the one reported on — what he did, what he gave, and what he said' ('and what he will not rest from' out: Naomi's words, not told as a fact); the Scene 2 B13 Referential form '\"the man\" (3:16, 3:18); \"he\" in Ruth's words (3:17)' and the FIG_0155 flag '(\"the man\", 3:16 and 3:18)' (was 'only \"the man\"', which 3:17 does not bear out); the R3, R6 and R8 source quotes follow the new lines. Made at the review step (confirmed review findings; standard item 1; named for her yes/no at the merge word): Section 1 'Scene 1 shifts to CONSULTATIVE at scene level, as in the night at the threshing floor; the dawn is still private …' (was '… at scene level: a respectful exchange between the two of them at the threshing floor, as in the night; …' — at 3:14–15 only Boaz speaks), with the MEANING_COORDINATES register_overrides _note and R12 following; Sections 2.2 and 2.4 'the words Boaz asked at night, \"who are you?\" (3:9)' (was 'in the same words Boaz asked at night (3:9)' — at 3:9 Boaz asks only 'who are you?'; 'my daughter' is Naomi's, 3:16); the R5 and R12 source quotes follow the new lines. Unchanged, seen: the pericope title 'The nameless dawn: six measures home, and sit still' and the Scene 1 title (a later title pass); the ruled SC-0064 values; the entity slugs inside the links (the voice and the Validator see only the code)."
    },
    {
      "decision_id": "P10-D6",
      "decision": "Marcia's ruling of 2026-09-29, after the team's session: Boaz is never told as asleep or awake (R14, do_not_decide).",
      "description": "Her words (2026-09-29, afternoon, after the team's session): «(a), (a), sim — pode seguir com as recomendações». Ruling (2), option (a): a do_not_decide never-rule, as in P09 (R19) — the text never says Boaz slept or woke; 3:14 tells only that Ruth lay at the place of his feet until the morning. For the voice only, never to be said: that he fell asleep, was sleeping or woke up ('dormiu', 'dormindo', 'acordou', 'acordou assustado'). Live, on 2026-09-29, the voice said «acordou assustado» or «acordou» in three different scripts (P09 'ele acorda assustado'; P10 'quando acordou assustado' and 'No meio da noite o homem acordou'). No map or MEANING_COORDINATES text changes. R14 is appended (append-only numbering): 14 entries, 8 do_not_decide. The English wording is the builder's rendering of her Portuguese."
    }
  ],
  "vocabulary_additions": {
    "proposition_kinds": [
      {
        "value": "MEASURED_OUT",
        "source": "P10-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-09-36-789Z (claude-opus-4-8, req 0a7748b2d17917eb…) · ruled by Marcia 2026-06-13 (proposition_kind Group B)",
        "status": "CONFIRMED",
        "note": "Boaz portioning the barley (Ruth 3:15 'measured six measures of barley, laid it on her'). Kept distinct (Marcia's B-4 keep) from MEASURED — the act of measuring-out a gift, FIG_0152."
      },
      {
        "value": "SHOWED",
        "source": "P10-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-09-36-789Z (claude-opus-4-8, req 0a7748b2d17917eb…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). MM P10: 'showing — what did she show? these six measures of barley.' The gift is laid out as evidence; no approved kind covers displaying/presenting an object as proof (GAVE/HANDED is the original transfer, not the showing)."
      }
    ],
    "scene_kinds": [],
    "presence_values": [],
    "referential_forms": [],
    "other": [],
    "arc_elements": [
      {
        "value": "EMPTYING_REVERSED",
        "source": "P10-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-09-36-789Z (claude-opus-4-8, req 0a7748b2d17917eb…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19). Survivor of the emptying-reversed collapse (Marcia 2026-06-19): P13's EMPTINESS_REVERSED folded into this (shares the approved EMPTYING root; the book reads EMPTYING -> EMPTYING_REVERSED). EMPTINESS_REVERSED not promoted. MM 2.4 names 'the structural turn from emptying to filling, carried in six measures of barley' — Naomi's 1:21 reqam answered negated. EMPTYING is approved for the loss in P01; its deliberate reversal here has no approved token."
      },
      {
        "value": "SECRECY_INJUNCTION",
        "source": "P10-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-09-36-789Z (claude-opus-4-8, req 0a7748b2d17917eb…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1/2.4: Boaz says the night's one rule out loud — 'let it not be known that the woman came to the floor'; the whole scene closes under this rule of secrecy. No approved arc_element names a concealment injunction (PROTECTIVE_INSTRUCTION is about safeguarding a person, not enjoining secrecy)."
      }
    ]
  },
  "proposition_kind_slot_sets": [],
  "high_risk_register_audit": [
    {
      "id": "R1",
      "kind": "SIGNIFICANT_ABSENCE",
      "applies_to": "Scene 1 (3:14–15, P1–P6): no farewell told; Boaz's 'do not go empty' not told at the threshing floor; the measure of 'six of barley' not said; FIG_0152",
      "note": "Silences kept as facts. The narrator tells no farewell. The narrator does not tell Boaz saying 'do not go empty to your mother-in-law' at the threshing floor; those words are heard only in Ruth's report (3:17). The text says 'six of barley' and does not say six of what measure. 'Six measures of barley' ('seis medidas de cevada') is accepted without comment. For the voice only, never to be said: do not put Boaz's words 'do not go empty' into the scene at the threshing floor; name no measure (seah, ephah, kilos, sacks, baskets) and give no weight or amount; tell no farewell and no words at the parting. A team telling that has Boaz say 'do not go empty' at the threshing floor is offered back gently: those words come only in Ruth's report (3:17); told at the threshing floor, they move earlier in the telling. A team telling that names a measure is offered back gently with the text's words. Do not announce these silences before the team tells (item 16).",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Significant Absence in Scene 1 ('The narrator tells no farewell. The narrator does not tell Boaz saying \"do not go empty to your mother-in-law\" at the threshing floor; those words are heard only in Ruth's report (3:17).'; 'The text says \"six of barley\" and does not say six of what measure.'); Section 2.2 ('The narrator does not tell Boaz saying those words at the threshing floor; they are heard only in Ruth's report.'); Section 3C Scene 1 (O16 'six measures of barley — the measure-unit is left unsaid by the text'); Section 5B Figure Flags (FIG_0152 'the measure-unit left unsaid — the vagueness is the text's'); Section 4 Propositions 5, 10 and 11; Marcia's SC-0056 ruling (the measure-unit left unflagged because the text withholds it)"
    },
    {
      "id": "R2",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "the dawn at 3:14 (P1–P3): she lies until the morning, rises before one person could recognize another, and he says 'let it not be known'; FIG_0150, FIG_0151, CB_0042; carries P09 R16",
      "note": "REQUIRED keep: Ruth lies at the place of his feet until the morning and rises before one person could recognize another (FIG_0150); and he says: let it not be known that the woman came to the threshing floor (FIG_0151). The text does not say to whom he says it, or why; if asked, the text does not say. 'Let it not be known' is the word of Naomi's plan, 'do not be known to the man' (3:3); the voice may say that the word comes again. A telling in which he says it to Ruth, or says 'no one must know', keeps the meaning; accept it without comment. 'The woman' or 'a woman' ('a mulher' / 'uma mulher') are both correct. For the voice only, never to be said: give Boaz no reason for his words (shame, her good name, his own name, danger, what people would say); do not say whether it became known; give no verdict of the voice's own on the night, neither that something happened nor that nothing did (P09 R16); add no touch and no word of love or desire at dawn.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 1 ('She lies at the place of his feet until the morning, and rises before one person could recognize another.'; 'He says: let it not be known that the woman came to the'); Section 2.1 ('Ruth lies at the place of his feet until the morning and rises before one person could recognize another; and he says: let it not be known that the woman came to the threshing floor.'); Section 2.2 ('His word \"let it not be known\" is the word of Naomi's plan, \"do not be known to the man\" (3:3).'); Section 2.4 ('To speak this passage is to keep the secret Boaz asked for (3:14)'); Section 3B Scene 1 (PL6 'named in Boaz's words — \"let it not be known that the woman came to the threshing floor\"'); Section 5B Figure Flags (FIG_0150 'she rises before one person could recognize another'; FIG_0151 at Proposition 3); Section 4 Propositions 1, 2 and 3; carried forward from P09 R16"
    },
    {
      "id": "R3",
      "kind": "NAMING_SHIFT",
      "applies_to": "the forms at 3:14–18: Boaz 'he' (3:14–15) and 'the man' (3:16, 3:18; FIG_0155); Ruth 'the woman' (3:14) and 'my daughter' (3:16, 3:18); Naomi 'her mother-in-law' (3:16) and 'your mother-in-law' in Boaz's words (3:17; CB_0043); carries P09 R13",
      "note": "PREFERRED keep: here the story calls Boaz 'he' and 'the man', Ruth 'the woman' and 'my daughter', and Naomi 'her mother-in-law'; in Boaz's words, as Ruth reports them, Naomi is 'your mother-in-law'. Keep these forms where the language allows. A telling that uses the names Boaz, Ruth or Naomi keeps the meaning and is accepted without comment.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 2.2 ('Here the story calls Boaz \"he\" and \"the man\", Ruth \"the woman\" and \"my daughter\", and Naomi \"her mother-in-law\".'); Section 3A Scene 1 (B9 '\"the woman\" in Boaz's words (3:14); the narrator says \"she\"'; B13 '\"he\" (3:14–15)'); Section 3A Scene 2 (B3 '\"her mother-in-law\" (3:16); \"your mother-in-law\" in Boaz's words (3:17)'; B9 '\"my daughter\" in Naomi's mouth (3:16, 3:18)'; B13 '\"the man\" (3:16, 3:18); \"he\" in Ruth's words (3:17)'); Section 5B Figure Flags (FIG_0155 '\"the man\", 3:16 and 3:18'); Section 5A Concept Flags (CB_0043 '\"your mother-in-law\" in Boaz's words, as Ruth reports them'); SC-0056 (not one personal name in five verses); carried forward from P09 R13"
    },
    {
      "id": "R4",
      "kind": "CROSS_PERICOPE_PAIRING_CLOSED_HERE",
      "applies_to": "FIG_0153 at 3:17 (P11): 'do not go empty to your mother-in-law', the word reqam of 1:21. Closes here; the registry opens it at P04 1:21 (P04 P5 flags CB_0044, CB_0024 and FIG_0084). CB_0044, CB_0024, CB_0043; carries P04 R5",
      "note": "REQUIRED keep: Ruth says: these six measures of barley he gave me, for he said to me, do not go empty to your mother-in-law. 'Empty' (reqam) is the word of Naomi's 'I went out full, and YHWH brought me back empty' (1:21; FIG_0153, CB_0044, CB_0024). Keep the same word 'empty' where the language allows; the voice may say that the word comes again. The words are Boaz's, as Ruth reports them, and they name 'your mother-in-law' (CB_0043). A telling that says the barley was for her mother-in-law keeps the meaning. So does a telling that adds 'home' ('do not go home empty') while keeping 'your mother-in-law' (Marcia's 2026-09-24 repetition ruling, frase 16). Accept both without comment. For the voice only, never to be said: do not say that these words answer, reverse or end Naomi's emptiness, or that she is now full; do not say that YHWH sent the barley; say nothing of whom the barley is for beyond Boaz's words; do not say that the gift shows what Boaz means to do or feels.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 2 ('She says: these six measures of barley he gave me, for he said to me, do not go empty to your mother-in-law.'); Section 2.2 ('Boaz's words as Ruth reports them, \"do not go empty (reqam) to your mother-in-law\", use the word of Naomi's \"YHWH brought me back empty (reqam)\" (1:21).'); Section 2.4 ('The word \"empty\" (reqam) of Naomi's 1:21 is said again, in Boaz's words as Ruth reports them: do not go empty to your mother-in-law.'); Section 3C Scene 2 (CB_0044 'the same word as Naomi's at 1:21, \"YHWH brought me back empty\"'; CB_0024 'of the pair, only \"empty\" is said here, in Boaz's words as Ruth reports them'; CB_0043 'in Boaz's words, as Ruth reports them: do not go empty to your mother-in-law'); Section 5A Concept Flags (CB_0044, CB_0024, CB_0043 at Proposition 11); Section 5B Figure Flags (FIG_0153 'the word \"empty\" (reqam) of Naomi's 1:21, \"YHWH brought me back empty\", said again in Boaz's words as Ruth reports them'); Section 4 Proposition 11; carried forward from P04 R5"
    },
    {
      "id": "R5",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0154 at 3:16 (P8): 'who are you, my daughter?', the same words as Boaz's 'who are you?' at 3:9",
      "note": "PREFERRED keep: Naomi asks 'who are you, my daughter?'. These are the same words Boaz asked at night (3:9, 'who are you?'); the voice may say that the words come again (told as 'a história conta que…' when this team has not worked 3:6–13). The text does not say what Naomi means by the question; if asked, the text does not say. A telling 'how did it go, my daughter?' ('como foi, minha filha?') keeps the meaning but not the same words as 3:9: a nuance, named once, not sent back. For the voice only, never to be said: do not explain what Naomi means (that she cannot see who it is, that she asks how it went, or what Ruth now is); do not give Ruth an answer with her name.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 2 ('Naomi says: who are you, my daughter?'); Section 2.2 ('Naomi's question, \"who are you, my daughter?\", uses the words Boaz asked at night, \"who are you?\" (3:9).'); Section 2.4 ('Naomi asks \"who are you, my daughter?\", with the words Boaz asked at night, \"who are you?\" (3:9).'); Section 3A Scene 2 (B3 'the one who asks \"who are you, my daughter?\", hears Ruth's report, and tells her to sit still'); Section 5B Figure Flags (FIG_0154 'the same words Boaz asked at night, 3:9: \"who are you?\"'); Section 4 Proposition 8; Marcia's 2026-09-24 nuance ruling (b), which counts a map-marked echo as a nuance, and her 2026-09-24 earlier-passages ruling (a história conta que…)"
    },
    {
      "id": "R6",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "Naomi's closing words at 3:18 (P12–P13): sit still until you know how the matter falls; the man will not rest unless he has finished the matter today; FIG_0156, FIG_0155, O19, TM_TODAY; carries P09 R15 and P11 R10",
      "note": "REQUIRED keep, in order: Naomi says: sit still, my daughter, until you know how the matter falls — for the man will not rest unless he has finished the matter today. 'Today' goes with finishing the matter. 'Sit still', 'wait' and 'stay here' ('fique quieta', 'espere', 'fique aqui') are correct; accept them without comment. A telling that ties 'today' to something else (for example 'the matter of today') keeps most of the meaning; it is a nuance, named once and not sent back (Marcia's rulings of 2026-09-16 and 2026-09-24). A telling in which Naomi tells Ruth to tell no one adds words she does not say; offer it back gently. Naomi does not say what the matter is. If asked, the text does not say; the voice may set beside it, in the text's words, what Boaz said at night: if the nearer redeemer will redeem you, good; if he does not want to redeem you, I will redeem you (3:12–13). When this team has not worked that passage, it is told as 'a história conta que…'. For the voice only, never to be said: do not tell Naomi's words as something already done or sure to happen; do not say which redeemer will act, what the matter is, or how it will fall, and do not say that Boaz will marry her (P09 R15); give Naomi no feeling (joy, relief, hope, certainty). 'Will not rest' is another Hebrew word (shaqat, 'be quiet, be still') from the 'rest' of 1:9 and 3:1 (menuchah, manoach), so do not link the two, and do not say that Naomi's wish, prayer or plan is coming true. Say nothing of what Boaz does next.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 2 ('And Naomi says: sit still, my daughter, until you know how the matter falls — for the man will not rest unless he has finished the matter today.'); Section 3C Scene 2 (O19 'the matter (davar); Naomi does not say what the matter is'; 'what Ruth must wait to see fall, and what the man will not rest until he has finished — twice named in Naomi's closing word'); Section 3D Scene 2 (TM_TODAY 'in Naomi's words, the man will not rest unless he has finished the matter today — \"today\" goes with finishing the matter'); Section 3A Scene 1 (B13 'at night he said: if the nearer redeemer will redeem you, good; if he does not want to redeem you, I will redeem you (3:12–13)'); Section 3A Scene 2 (B13 'in Naomi's words, the man who will not rest unless he has finished the matter today'); Section 2.3 ('Naomi's last words are about the man: he will not rest unless he has finished the matter today.'); Section 5B Figure Flags (FIG_0156 'Naomi's words: the man will not rest unless he has finished the matter today'; FIG_0155 '\"the man\", 3:16 and 3:18'); Section 4 Propositions 12 and 13; carried forward from P09 R15 and P11 R10"
    },
    {
      "id": "R7",
      "kind": "CROSS_PERICOPE_PAIRING_FIRST_OCCURRENCE",
      "applies_to": "FIG_0156 at 3:18b (P13): opens here; closes at P11 P1 (4:1)",
      "note": "Canon record: FIG_0156 opens here (3:18b) and closes at P11 P1 (4:1); VERIFIED in the P11 register (R11).",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 5B Figure Flags (FIG_0156 'Naomi's words: the man will not rest unless he has finished the matter today'); Section 4 Proposition 13 (3:18b); the forward link is recorded only in this register and in cross_pericope_pair_verification; carried forward from P11 R11 and the P11 FIG_0156 row"
    },
    {
      "id": "R8",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "single keep-images and same words at 3:14–17: FIG_0152 (P5, P10), CB_0042 (P1), 'until the morning' (P1; the words of 3:13), O13 mitpachat (P4, P5), FIG_0155 (P9, P13); carries P09 R10",
      "note": "PREFERRED (FIG_0152): six measures of barley, said twice (3:15, 3:17); the measure is not named (R1). CB_0042: 'the place of his feet', the word of 3:4, 3:7 and 3:8, said a fourth time; the voice may say that the word comes again. 'Until the morning': the same words as Boaz's 'lie down until the morning' (3:13); the voice may say that the words come again. O13: the word here is mitpachat, not the simlah of 3:3 (Marcia, SC-0056); 'cloak', 'shawl', 'manto', 'capa' are all correct. FIG_0155: 'the man' (3:16, 3:18); see R3.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3C Scene 1 (CB_0042 'where Ruth lay until the morning — the word of Naomi's plan and of the night (3:4, 7, 8), said a fourth time here'; O13 'the word here is mitpachat, not the simlah of 3:3'; O16 'six measures of barley — the measure-unit is left unsaid by the text'); Section 3C Scene 2 (O16 'Ruth says: these six measures of barley he gave me'); Section 3D Scene 1 ('at night Boaz said \"lie down until the morning\" (3:13); she lies until the morning'); Section 2.2 ('At night Boaz said: lie down until the morning (3:13); here she lies at the place of his feet until the morning.'); Section 5A Concept Flags (CB_0042 'the word of 3:4, 7, 8, said a fourth time'); Section 5B Figure Flags (FIG_0152 at Propositions 5 and 10; FIG_0155 '\"the man\", 3:16 and 3:18'); Section 4 Propositions 1, 4, 5, 9, 10 and 13; carried forward from P09 R10 (FIG_0139, the word lie down through the night)"
    },
    {
      "id": "R9",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "Ruth's report at 3:16c–17 (P9–P11): 'all that the man did for her'; carries P09 R9 and P09 R16",
      "note": "REQUIRED keep: Ruth tells her mother-in-law all that the man did for her, and says: these six measures of barley he gave me, for he said to me, do not go empty to your mother-in-law. A telling that names some of what he did at night, in the text's words (he asked who she was; he said: if the nearer redeemer will redeem you, good; if he does not want to redeem you, I will redeem you; he gave her the barley), keeps the meaning; accept it without comment. For the voice only, never to be said: do not make Ruth's report more than the text gives: no words or feelings of love, no touch, and no verdict on the night (P09 R16); add no praise or blame of what Ruth did, and never say that Ruth or Boaz gained authority (P09 R9); give Ruth and Naomi no feelings the text does not give.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 2 ('And Ruth tells her all that'; 'the man did for her. She says: these six measures of barley he gave me, for he said to me, do not go empty to your mother-in-law.'); Section 3F Scene 2 ('Ruth tells her all that the man did for her, and says: these six measures of barley he gave me, for he said to me, do not go empty to your mother-in-law.'); Significant Absence in Scene 2 ('To Naomi's question, Ruth tells her all that the man did for her.'); Section 3A Scene 1 (B13 'at night he said: if the nearer redeemer will redeem you, good; if he does not want to redeem you, I will redeem you (3:12–13)'); Section 4 Propositions 9, 10 and 11; carried forward from P09 R9 and P09 R16"
    },
    {
      "id": "R10",
      "kind": "TEXTUAL_CLARITY_FLAG",
      "applies_to": "3:15c (P6): 'and he went into the town' (וַיָּבֹא, the Hebrew text; some manuscripts, ancient versions and Bibles read 'she'); Marcia's SC-0056 approval and her ruling D2 (b) of 2026-09-29",
      "note": "3:15 ends 'and he went into the town', the reading of the Hebrew text that Marcia approved at SC-0056. The voice tells 'he goes into the town' and does not teach another reading (item 15). A team telling 'she went into the town' ('ela foi para a cidade'), as some Bibles read, is offered back gently with the map's reading: he goes into the town (Marcia's ruling D2 (b), 2026-09-29, as at 4:5 in P11 R13). For the voice only, never to be said: do not explain the two readings or say which Bibles have which.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 1 ('And he goes into the'); Section 2.1 ('and he goes into the town'); Section 2.2 ('He goes into the town; she comes to her mother-in-law.'); Section 3A Scene 1 (B13 'the one who says \"let it not be known\", measures the six measures, and goes into the town'; B9 'the one who lies at the place of his feet until the morning, rises before one person could recognize another, and holds the cloak'); Section 3B Scene 1 (PL4 'where he goes (3:15)'; 'where he goes after he lays the barley on her'); Section 4 Proposition 6 ('Who went?'); SPEC_CHANGES SC-0056 (3:15 closes \"and HE went into the town\", flagged for her eyes)"
    },
    {
      "id": "R11",
      "kind": "TEXTUAL_CLARITY_FLAG",
      "applies_to": "minor text points at 3:14 (P1, P2), 3:15 (P4, P5), 3:16 (P9), 3:17 (P10, P11), 3:18 (P12)",
      "note": "Minor text points. (1) 3:14: the written and read forms of 'the place of his feet' and 'before' differ (ketiv/qere), with no change of meaning. (2) 3:15: Boaz says 'give / bring the cloak that is on you, and hold it'; 'hold out the cloak', 'bring the cloak', 'give me the cloak' and 'hold it' ('segure a capa') are all correct; 'he laid it on her' and 'on her back' ('lhe pôs às costas') are both correct. (3) 3:17: 'he said to me' — the 'to me' is read, not written, in the Hebrew; the plain sense is correct. (4) 3:18: 'how the matter falls' — 'how it turns out', 'how the matter ends', 'como esse assunto vai terminar' and the word-for-word 'como vai cair' are all correct. (5) 3:16: 'all that the man did for her' — 'all that happened', 'everything he did' are correct. All of these are accepted without comment.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3E Scene 1 ('He says: hold out the cloak that is on you — and she holds it, and he measures six measures of barley and lays it on her.'); Section 3E Scene 2 ('for he said to me'; 'until you know how the matter falls'; 'And Ruth tells her all that'); Section 4 Propositions 1, 2, 4, 5, 9, 11 and 12; the 2026-09-24 session translation calls (como esse assunto vai cair, segure a capa)"
    },
    {
      "id": "R12",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "register: whole passage INFORMAL_CASUAL; Scene 1 CONSULTATIVE and Scene 2 INTIMATE at scene level",
      "note": "The whole passage sits in INFORMAL_CASUAL. Scene 1 (3:14–15) is CONSULTATIVE at scene level, as in the night at the threshing floor; the dawn is still private (3:14). Scene 2 (3:16–18) is INTIMATE at scene level: Ruth and her mother-in-law talk together, as in 3:1–5. The narrator's voice frames the movements plainly.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 1 Metadata, multi-level register tagging ('Scene 1 shifts to CONSULTATIVE at scene level, as in the night at the threshing floor; the dawn is still private — before one person could recognize another, and under Boaz's word that it must not be known that the woman came to the threshing floor (3:14).'; 'Scene 2 shifts to INTIMATE at scene level: Ruth and her mother-in-law talk together (3:16–18), as in 3:1–5.'; 'The narrator's voice frames the movements plainly.'); MEANING_COORDINATES register_overrides (scene_level S1 CONSULTATIVE, S2 INTIMATE); P09 R12 (the CONSULTATIVE wording); SC-0086 ruling 5 (privacy stays, 3:14); SC-0087 R-9 (Scene 1 CONSULTATIVE, Scene 2 stays INTIMATE)"
    },
    {
      "id": "R13",
      "kind": "DISCOURSE_THREAD_ADVANCED",
      "applies_to": "T2 line-and-redemption at 3:14–18; canon-record links FIG_0156 → P11, FIG_0153 ← P04; threads and figures with no word in 3:14–18 (FIG_0120/CB_0014 rest, FIG_0142, T4 hesed, FIG_0001)",
      "note": "T2 (line and redemption; P05 R8, P07 R12, P09 R14): the redeem word is not said in 3:14–18. The map recalls, in the text's words, what Boaz said at night (3:12–13), and Naomi speaks of 'the man' and 'the matter'. In the canon record the thread goes on to the gate at P11 through FIG_0156 (R7). The words of 1:21 come again at 3:17 (FIG_0153, R4). Threads and figures with no word in 3:14–18, not flagged here: the rest of 1:9 and 3:1 (FIG_0120, CB_0014), since 'will not rest' at 3:18 is shaqat (R6); hesed (T4); the Moabite marker (FIG_0001). FIG_0142 is not flagged: the registry lists it in P10, but no firing site exists in 3:14–18 (P13 row DEFERRED). FIG_0139 ('lie down' through the night) closes at P09 in the registry; 3:14's 'she lay … until the morning' repeats its words and is recorded in R8 without a flag.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3A Scene 1 (B13 'a redeemer (3:12); at night he said: if the nearer redeemer will redeem you, good; if he does not want to redeem you, I will redeem you (3:12–13)'); Section 3A Scene 2 (B13 'a redeemer (3:12); in Naomi's words, the man who will not rest unless he has finished the matter today'); Section 5B Figure Flags (FIG_0153, FIG_0156); the canon links are recorded only in this register and in cross_pericope_pair_verification; carried forward from P05 R8, P07 R12, P09 R14, P11 R11 and P04 R5"
    },
    {
      "id": "R14",
      "kind": "SIGNIFICANT_ABSENCE",
      "applies_to": "Boaz at 3:14 (P1): 3:14 tells only that Ruth lay at the place of his feet until the morning; the text never says he slept or woke (Marcia's ruling of 2026-09-29, after the team's session; as P09 R19)",
      "note": "The text never says that Boaz slept or woke. In the night he lies down at the end of the grain heap (3:7) and at half of the night the man trembles and twists (3:8; P09 R19); 3:14 tells only that Ruth lay at the place of his feet until the morning. For the voice only, never to be said: that he fell asleep, was sleeping or woke up ('dormiu', 'dormindo', 'acordou', 'acordou assustado'). Do not announce this silence before the team tells (item 16).",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 1 ('She lies at the place of his feet until the morning'); Section 2.1 ('Ruth lies at the place of his feet until the morning'); Section 3A Scene 1 (B9 'the one who lies at the place of his feet until the morning'); Section 3C Scene 1 (CB_0042 'where Ruth lay until the morning'); Section 4 Proposition 1; carried from P09 R19; Marcia's ruling (2) of 2026-09-29"
    }
  ],
  "cross_pericope_pair_verification": {
    "pairs": [
      {
        "fig_id": "FIG_0153",
        "opens_at": "P04 P5 (1:21 'YHWH brought me back empty'; registry opens-at P04 — the P04 MEANING_COORDINATES flags CB_0044, CB_0024 and FIG_0084 at P5, not FIG_0153)",
        "closes_at": "P10 P11 (3:17 'do not go empty to your mother-in-law')",
        "verification_status": "VERIFIED",
        "note": "Pair closed at this register (R4), on CB_0044, flagged at both ends (P04 P5, P10 P11): the same word 'empty' (reqam) said again, in Boaz's words as Ruth reports them. Registry frontmatter (vault note) lists opens-at P04 / closes-at P10. The P04 MEANING_COORDINATES does not flag FIG_0153 at P5 (approved passage; vault half). Recorded as the same word said again, never as an answer to Naomi's 1:21 or a reversal of it; the vault note's intended-meaning ('structural answer to Naomi's 1:21 reqam lament') is a reading the map does not state (vault half)."
      },
      {
        "fig_id": "FIG_0156",
        "opens_at": "P10 P13 (3:18b 'the man will not rest unless he has finished the matter today')",
        "closes_at": "P11 P1 (4:1 Boaz goes up to the gate)",
        "verification_status": "VERIFIED",
        "note": "Mirrors the P11 row (VERIFIED at P11 R11): the P10 MEANING_COORDINATES flags FIG_0156 at P13 (3:18b), the P11 MEANING_COORDINATES at P1 (4:1a). Registry frontmatter (vault note) confirms opens-at P10 / closes-at P11. Canon-record link only (R7); the P10 map carries no pointer to 4:1. The vault note's intended-meaning ('the wait-formula that p11's gate scene immediately fulfills') uses 'fulfills' (vault half)."
      },
      {
        "fig_id": "FIG_0150",
        "opens_at": "P10 P2 (3:14b 'before one person could recognize another')",
        "closes_at": "P10 P2 (single occurrence)",
        "verification_status": "VERIFIED",
        "note": "Single occurrence within the pericope (R2): the P10 MEANING_COORDINATES flags FIG_0150 at P2. Registry frontmatter (vault note) confirms opens-at and closes-at P10. The vault note's intended-meaning ('the timing protects propriety') gives a motive the text does not give (vault half)."
      },
      {
        "fig_id": "FIG_0151",
        "opens_at": "P10 P3 (3:14c 'let it not be known that the woman came to the threshing floor')",
        "closes_at": "P10 P3 (single occurrence)",
        "verification_status": "VERIFIED",
        "note": "Single occurrence within the pericope (R2): the P10 MEANING_COORDINATES flags FIG_0151 at P3. Registry frontmatter (vault note) confirms opens-at and closes-at P10. The vault note's intended-meaning ('protects the threshing-floor scene from public scrutiny') gives a motive the text does not give (vault half)."
      },
      {
        "fig_id": "FIG_0152",
        "opens_at": "P10 P5 (3:15b he measures six measures of barley)",
        "closes_at": "P10 P10 (3:17a 'these six measures of barley he gave me')",
        "verification_status": "VERIFIED",
        "note": "Within the pericope (R8, R1): the P10 MEANING_COORDINATES flags FIG_0152 at P5 and P10. Registry frontmatter (vault note) confirms opens-at and closes-at P10. The measure is not named in the text (R1)."
      },
      {
        "fig_id": "FIG_0154",
        "opens_at": "P10 P8 (3:16b 'who are you, my daughter?')",
        "closes_at": "P10 P8 (single occurrence)",
        "verification_status": "VERIFIED",
        "note": "Single occurrence within the pericope (R5): the P10 MEANING_COORDINATES flags FIG_0154 at P8. Registry frontmatter (vault note) confirms opens-at and closes-at P10. The same words as Boaz's 'who are you?' at 3:9 are recorded in R5 as words said again, with no flag at P09. The vault note's intended-meaning holds three readings ('recognition question, identification question, or question about Ruth's now-changed status'); the map keeps only the words and the 3:9 echo, and the voice explains no reading (R5; vault half)."
      },
      {
        "fig_id": "FIG_0155",
        "opens_at": "P10 P9 (3:16c 'all that the man did for her')",
        "closes_at": "P10 P13 (3:18b 'the man will not rest')",
        "verification_status": "VERIFIED",
        "note": "Within the pericope (R3, R8): the P10 MEANING_COORDINATES flags FIG_0155 at P9 and P13. Registry frontmatter (vault note) confirms opens-at and closes-at P10. The vault note's intended-meaning says it 'structurally pairs with FIG_0156 (Ploni Almoni)', but FIG_0156 is 'the man will not rest', and the peloni almoni figure belongs to P11 (vault half)."
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
      "ASKS_KINSHIP_BELONGING_QUESTION",
      "DIRECTS_HEARER_NOT_TO_DO",
      "DIRECTS_HEARER_TO_DO",
      "REPORTS_PRIOR_SPEECH_INSTRUCTION",
      "STATES_AS_TRUE"
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
    "Mechanized ruled log (SC-0064 close part 2): the judgment half was machine-drafted (SC-0063) and reviewer-ruled; vocabulary_additions are assembled from this pericope's per-axis ruling-logs.",
    "The high-risk register audit was hand-authored from the corrected P10 map under the 2026-09-28 standard and the SC-0089 rulings: 13 entries (7 do_not_decide: R1, R2, R4, R5, R6, R9, R10), each traced to the P10 map, and R14 appended on her word of 2026-09-29 after the team's session (P10-D6: 14 entries, 8 do_not_decide); the carried-forward items (P04 R5, P05 R8, P07 R12, P09 R9/R10/R13/R14/R15/R16, P11 R10/R11) also cite their source registers (P10-D4).",
    "Propositions stay at meaning-map granularity; multi-event propositions decompose in-slot per the granularity contract.",
    "The forward link out of P10 (FIG_0156 to P11, 4:1) lives only in this register (R7, R13) and the pair table; the map carries none.",
    "The nuance for 'como foi, minha filha?' (R5) and the accepted renderings in R2, R4, R6 and R9 live in do_not_decide notes, which the Validator reads and the voice does not; the SC-0088 live runs showed that such a rule alone does not stop the voice's send-back (P13 'rei Davi'). The map prose carries the facts they rest on ('who are you, my daughter?', 'sit still', 'today', the report); not yet measured live for P10.",
    "Registry (vault note) data that no map or MEANING_COORDINATES backs: FIG_0153 opens-at P04, but the P04 MEANING_COORDINATES flags CB_0044, CB_0024 and FIG_0084 at P5, not FIG_0153; FIG_0142 appears-in lists P10, with no firing site in 3:14–18 (no P10 flag; its P13 row stays DEFERRED); CB_0043's first-appearance P10 ('her mother-in-law' is already at 1:14, 2:11, 2:18, 2:19, 2:23, 3:1 and 3:6); CB_0042's 'Surfaces in' lists P08 and P09 only; PL4's appears_in does not list P10.",
    "Several vault notes carry readings the P10 map no longer states: FIG_0150 and FIG_0151 'protects', FIG_0153 'structural answer', FIG_0154's three readings, FIG_0155's pairing with 'Ploni Almoni', FIG_0156 'fulfills', CB_0042's 'bridal-symbolic' rendering note; and slugs carry words the map does not use (FIG_0155 'Ha-Ish-Unnamed-Kinsman-Referent'; FIG_0153 'Do-Not-Return-Empty', where the verb is bo, 'go'). The voice and the Validator see only the code, and the slugs stay in canon for human readers.",
    "Three kinds in this register are not on the approved high_risk_register_kind list — SIGNIFICANT_ABSENCE (R1), TEXTUAL_CLARITY_FLAG (R10, R11) and DISCOURSE_THREAD_ADVANCED (R13); they join the register-kind call already owed under SC-0087 and SC-0088 and are not promoted here.",
    "The MEANING_COORDINATES keep ruled SC-0064 values that carry readings the map no longer states — arc EMPTYING_REVERSED, RECOGNITION_EXCHANGE and INITIATIVE_HANDOFF; tone ANTICIPATORY; function WITHHOLDS; B13 role REDEEMER_KIN; P8 question_about IDENTITY_RECOGNITION_AND_STANDING and speech_act ASKS_KINSHIP_BELONGING_QUESTION; P11 slot gift_destination; P13 speech_act STATES_AS_TRUE for Naomi's 'the man will not rest'; P1 referential_form_at_verse HA_ISHAH_THE_WOMAN where 3:14a says 'she' — none is voiced; for a future slot-name / value lint pass. The Proposition 10 kind SHOWED ('showing') is Marcia-ruled (2026-06-13) and kept, though 3:17 says 'she said: these six … he gave me'. CB_0043 ('your mother-in-law') stays an object beside the being B3 (not changed here).",
    "The vocabulary_additions notes (the dated SC-0064 ruling record) quote the map as it stood before SC-0089 (e.g. 'the structural turn from emptying to filling', 'Boaz says the night's one rule out loud', 'The gift is laid out as evidence'); they are kept as history, not as current map text.",
    "Two word points are map text under standard item 7: O13 is mitpachat at 3:15, not the simlah of 3:3 (Section 3C, Marcia's SC-0056 note), and 'will not rest' at 3:18 is shaqat, not the 'rest' of 1:9 and 3:1 (R6 only; the map does not link them)."
  ]
}
```

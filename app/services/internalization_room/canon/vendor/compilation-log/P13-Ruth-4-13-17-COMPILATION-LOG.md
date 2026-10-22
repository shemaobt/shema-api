---
type: "sta-compilation-log"
pericope: "P13"
status: "valid"
pilot: "pilot-2"
---

# P13 — Ruth 4:13-17 — COMPILATION-LOG

```json
{
  "sta_id": "ruth_pericope_13_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Ruth 4:13-17",
  "pericope_id": "P13",
  "pericope_title": "Obed: the conception YHWH gives, the women's blessing, the child on Naomi's lap",
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
  "confidence_overall_note": "Judgment half machine-drafted (SC-0063, patch-only contract) and ruled by Marcia axis-by-axis under SC-0064 (§A–§E + arc_element). The graduated MEANING_COORDINATES validates block-clean with 0 convergent drift and is lint-clean. Mechanized log: vocabulary_additions are this pericope's ruled mints; the high-risk register audit was hand-authored from the corrected P13 map under Marcia's map standard of 2026-09-28 and her SC-0088 rulings of 2026-09-28 (see P13-D4, P13-D5; the never-rules made do_not_decide and the Scene 3 register after the session, P13-D6).",
  "compilation_decisions": [
    {
      "decision_id": "P13-D1",
      "decision": "Deterministically compiled a MEANING_COORDINATES skeleton from the approved Meaning Map.",
      "description": "Extracted header/classification, scene + entity IDs + presence, verse-ranges, significant_absence, communicative purpose, proposition anchors/scene-links/cross-refs, and Section-5 concept/figure flags. 75 judgment fields left as typed placeholders for Agent 3. No values invented (extract-only)."
    },
    {
      "decision_id": "P13-D2",
      "decision": "Judgment gaps filled by the SC-0063 drafter (Slice 4).",
      "description": "claude-opus-4-8 under the pinned fm-drafter prompt; structured-output fills merged by the patch-only layer. Provenance: _working/P13/drafts/run-2026-06-12T15-32-24-490Z/."
    },
    {
      "decision_id": "P13-D3",
      "decision": "Ruled by Marcia under SC-0064 (the batch ruling), axis by axis.",
      "description": "§A–§E + the five §B axes (action+tone, proposition_kind, role_in_scene_being, scene_kind, arc_element) ruled across 2026-06-12→19; 10 vocabulary addition(s) CONFIRMED for promotion for this pericope (per-axis ruling-logs in _working/P13/P13-SC-0064-*-RULING-LOG.md). Renames/collapses applied to the MEANING_COORDINATES as recorded amendments where ruled."
    },
    {
      "decision_id": "P13-D4",
      "decision": "High-risk register built under SC-0088 (the P07–P14 register-completion program opened by SC-0085): Marcia's map standard of 2026-09-28 and her four SC-0088 rulings.",
      "description": "Drafted from the corrected P13 map under Marcia's approved map standard (2026-09-28, «(a), sim, pode seguir com as recomendações», item 16 included) and her SC-0088 rulings (2026-09-28, «(b), (b), (a), sim — pode seguir com as recomendações»); the English wording of the entries is the builder's rendering. 12 entries replace the R1 skeleton, 7 do_not_decide (R1 the swift sequence of 4:13, R3 the redeemer and 'his name', R5 Naomi and the child, R7 the naming, R8 David, R9 the child and the name of the dead, R10 who is spoken to and who is not mentioned). Ruling D1 (b) is in R8: a team's 'King David' is a nuance, named once — 'a história dá só o nome dele, Davi' — without a send-back, the same rule as for 4:22 in P14. Ruling D2 (b) is in R10 and in the Section 5B FIG_0016 note: 'not at the gate' only for 4:1–8; in 4:9–12 neither Ruth nor Naomi speaks, and the voice never says whether they were at the gate. Ruling D3 (4:11) has no site in P13. Never-lists are marked 'For the voice only, never to be said' (standard item 16); team-side judgments are their own sentences. Kinds: STRUCTURAL_FRAMING_DEVICE, REFERENTIAL_FORM_CHANGE, NAMING_SEQUENCE_PRESERVATION, WITHHELD_PAIRING_PER_SOURCE_DISCIPLINE and CROSS_PERICOPE_PAIRING_CLOSED_HERE from the approved high_risk_register_kind list; TEXTUAL_CLARITY_FLAG (R3), DISCOURSE_THREAD_ADVANCED (R6) and SIGNIFICANT_ABSENCE (R8, R10) as in P11 (not on the approved list). Carried-forward items land: P02 R1, R9, R10; P05 R8; P07 R7, R12; P09 R3, R14, R15; P11 R6, R8, R9, R10, R11, R14; the child-word of 1:5 (P01 R11) is noted in R11 as a word heard again, not carried as a keep-form. Pair table: FIG_0014 (P11 → middle P12 → P13), FIG_0016 (P11 → P13), FIG_0187 (P12 → P13) and FIG_0007 (P01 → P13) VERIFIED here; FIG_0142 and FIG_0181 DEFERRED (their registry openings are not flagged in any earlier map or MEANING_COORDINATES); FIG_0194, FIG_0192 and FIG_0189 PENDING to P14. Forward links to P14 live only in this register (R6) and the pair table, never in the map. The three gate signals (the real audit, high_risk_register_complete, and the map's sta-status) flip together in this change."
    },
    {
      "decision_id": "P13-D5",
      "decision": "Meaning Map + MEANING_COORDINATES corrected under the 2026-09-28 standard; PL_NAOMIS_DWELLING removed from S1 and S3 and CB_0001 from S1; the S3 child joined to B25 Obed.",
      "description": "The standard applied to the map and the MEANING_COORDINATES together: no verdicts, motives or feelings the text does not give (e.g. 'the book's emptiness reversed', 'faithfulness', 'reckoned', 'the foreign widow measured past a full house'); no answer or fulfilment links and no forward pointers in the voice's text — Section 2.1, which P14's story-so-far hears, carries none, and the backward links go only through words the Hebrew repeats (yeled 1:5 / 4:16; the verb 'bring back' 1:21 / 4:15; 'call' 1:20 / 4:17; name and call 4:11 / 4:14; redeemer); nothing from other books ('king', 'royal line', 'prologue of a kingdom', 'covenant line'); no image the text does not give ('cradle'); 'redeemer', never 'kinsman-redeemer'; 'the women' at 4:14 and 'the neighbor-women' at 4:17; YHWH only in the text's words (he gives her conception). Scene 2's title is 'The women's words to Naomi (4:14–15)': they bless YHWH, not Naomi. Elements the text does not have: PL_NAOMIS_DWELLING removed from S1 and S3 (4:13–17 names no place) and CB_0001 from S1 (4:13 does not say 'redeemer') — map Sections 3B/3C read 'None', the MEANING_COORDINATES places/objects are null with a _note (the E01–E03 form), CB_0001 leaves P1 cb_flags and Section 5A lists it at Proposition 4 only. Duplicate: the S3 child ('the child', 4:16) was listed both as B? and as B25 Obed; the MEANING_COORDINATES S3 B? entry is removed, P8 child_taken, P9 for_child and P10 named_child read B25 (as P11 already did), and the map's Scene 3 'The child — הַיֶּלֶד' entry is joined to the B25 entry. The MC's three scene purposes and significant absences equal the map's 3F and Significant Absence texts word for word; the register_overrides _note drops 'cradle'. Map frontmatter sta-status set to complete. Unchanged (ruled SC-0064 values, not voiced): arc EMPTYING_REVERSED and BIRTH_OF_HEIR; roles GRANDMOTHER, TOWNSWOMEN, ANCESTOR, LINEAGE_REFERENT; the slot name reckoned_to; register_overrides S2 CEREMONIAL (the S3 INTIMATE override was removed after the session, P13-D6); the entity slugs inside the links (the voice and the Validator see only the code). Builder extensions named for Marcia's yes/no, beyond the listed texts: (1) the Scene 3 merge of the duplicate child — the B25 heading reads '[[B25-Obed]] — הַיֶּלֶד / \"the child\"; עוֹבֵד / Obed' and its Role 'the child Naomi takes to her bosom; the neighbor-women call him Obed'; (2) §2.2 'the word used at 1:5 for Naomi's two children' (yeladeha at 1:5, as the approved P01 map has it; was 'Naomi's two sons'); (3) the Section 5B FIG_0016 note in ruling D2's wording, 'Ruth and Naomi are not at the gate in 4:1–8, and in 4:9–12 neither of them speaks; here Naomi takes the child'; (4) R6 states the T2 thread as facts only — the 3:13 promise resolved as told at 4:6–8, the purchase declared at 4:10, the marriage told at 4:13 — in place of the survey's 'the marriage promised at 3:13'. Made at the SC-0088 integration step, after the builder reported them as survivors: (5) the Scene 1 title 'The marriage, the conception, the birth (4:13)' (was 'the gift'; item 10 — the title follows 3F's 'YHWH's giving of conception', and scene titles reach P14's story-so-far); (6) §2.3 opens 'Swift, then warm, then still.' (was 'Swift, then full, then still and lifting.'; items 3 and 6 — the same residue as the cross-check's 'suddenly vast'). Made at the SC-0088 review step: (7) the Scene 1 B13 Relationship 'now her husband' (was 'the redeemer, now her husband'; item 1 — 4:13 does not say 'redeemer', the same reason CB_0001 left S1); (8) the Scene 2 CB_0005 'What it is: a name called out among the people' (was 'a name called out and known among the people'; items 1 and 2 — 4:14 is a wish, and 'known' goes beyond it); (9) §2.1 'The narrator adds: he is the father of Jesse, the father of David.' (was 'He is the father of Jesse, the father of David.', which runs straight on from the neighbor-women's naming in the story-so-far P14 hears; item 1 — the map gives the line to the narrator in §2.2, §2.4, Section 3D and R8, as P14 §2.2 does). Register numbering against the survey draft: R1–R5 and R7–R12 keep their numbers; the survey's R6 (yeled) is merged into R11, its R14 is dropped (it repeated P12 R1), and its R13 (the thread record) is R6."
    },
    {
      "decision_id": "P13-D6",
      "decision": "After the team's session, Marcia's word of 2026-09-28: the never-rules go to the Validator (do_not_decide); R2 flipped whole, R11's never-rule moved into a new do_not_decide entry R13; Scene 3's INTIMATE override removed (standard item 10); the Compilation Log's link-syntax prose in plain words.",
      "description": "Her words (2026-09-28, after the team's session ended): «A sessão acabou. Pode passar as regras do tipo nunca para o validador; pode trocar \"parente\" por \"resgatador\" nas quatro linhas em que Boaz é o resgatador; pode usar os títulos que você escreveu.» The app's Validator reads, from the register, only the id, kind and note of do_not_decide entries. In P13: R2 (the women's words in order; 'For the voice only, never to be said: do not call the redeemer 'kinsman' or 'relative', add another reason for the women's words, or explain what 'seven sons' stands for.') is now do_not_decide as a whole: every sentence in it is a rule on the women's words. R11 carried a canon-record sentence ('Canon record only, not part of P13's telling: …') beside its never-list, so its never-list sentence moved, word for word, into a new entry R13 (CROSS_PERICOPE_PAIRING_CLOSED_HERE, do_not_decide); R11 keeps its keep-images and the canon record and stays not do_not_decide. Note texts otherwise unchanged. The register now has 13 entries, 9 do_not_decide (R1, R2, R3, R5, R7, R8, R9, R10, R13). Register: Scene 3's scene-level INTIMATE override is removed (map §1, MEANING_COORDINATES register_overrides, R12) — the neighbor-women naming the child is not an intimate scene (her approved standard, item 10: «INTIMATE só onde a cena é íntima»), so Scene 3 falls back to the pericope's INFORMAL_CASUAL; S2 stays CEREMONIAL; the level_1 tone element INTIMATE (a ruled SC-0064 value, not a register) is unchanged. The decision and known_limitations lines on link slugs now say 'the code' in plain words, so Obsidian shows no broken link. App side (not canon here): the two Portuguese P13 scene titles hand-written in the app are approved («pode usar os títulos que você escreveu»)."
    }
  ],
  "vocabulary_additions": {
    "proposition_kinds": [
      {
        "value": "BORE",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). MM P3 'bearing' — Ruth bears a son; no approved proposition_kind (DIED, GAVE, TOOK, etc.) covers a birth event."
      }
    ],
    "scene_kinds": [
      {
        "value": "BIRTH_SCENE",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM Scene 1 title 'The marriage, the gift, the birth' and 3F centers on the divine gift of conception and the birth of the son; no approved scene_kind covers a birth/gift resolution."
      },
      {
        "value": "NAMING_SCENE",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM Scene 3 title 'The child on Naomi's lap; the naming' and 3F center on the communal naming of the child; no approved scene_kind covers a naming event."
      }
    ],
    "presence_values": [],
    "referential_forms": [],
    "other": [],
    "arc_elements": [
      {
        "value": "BIRTH_OF_HEIR",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1: 'she bears a son' — the line's future delivered; no approved birth/heir arc token exists."
      },
      {
        "value": "COMMUNAL_NAMING",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.4: 'closes the communal-naming the book opened in Naomi's bitter homecoming' — the women name the child for Naomi; no approved naming arc token."
      },
      {
        "value": "DIVINE_GIFT_OF_CONCEPTION",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1/2.4: 'YHWH gives her conception' — the book's second direct divine act, a distinct arc beat with no approved equivalent."
      },
      {
        "value": "MARRIAGE_CONSUMMATED",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1: 'Boaz takes Ruth, she becomes his wife, he comes to her' — the redemption completed in marriage; no existing arc token covers a consummated marriage."
      }
    ],
    "role_in_scene_beings": [
      {
        "value": "GRANDMOTHER",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM Scene 2/3: 'the grandmother' to whom the child is reckoned (the once-empty widow now holding the line's future); no approved role captures the grandmother function central to this scene."
      },
      {
        "value": "LINEAGE_REFERENT",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM Scene 3: Jesse and David are 'the names the narrator reaches to past the story' — forward genealogical referents; ANCESTOR is wrong-direction and ERA_REFERENT is time-setting only."
      },
      {
        "value": "TOWNSWOMEN",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM Scene 2/3 'the women' / 'the neighbor-women' act as the female counterpart to the men's gate-blessing (FIG_0187); approved TOWNSPEOPLE is gender-blind and FEMALE_WORKERS is field-specific."
      }
    ]
  },
  "proposition_kind_slot_sets": [],
  "high_risk_register_audit": [
    {
      "id": "R1",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "the swift sequence of 4:13 (P1–P3): Boaz takes Ruth, she becomes his wife, he comes to her, YHWH gives her conception, she bears a son; FIG_0180, FIG_0194, FIG_0188",
      "note": "REQUIRED. Keep the order and the doers of 4:13: Boaz takes Ruth, she becomes his wife, and he comes to her; YHWH gives her conception; she bears a son. The narrator names YHWH as the one who gives her conception. The marriage is told here (4:13). The narrator tells no wedding, no span of time, and nothing of the birth itself. A team telling such as 'God gave them a son' keeps the meaning; accept it without comment. For the voice only, never to be said: do not add a wedding feast, a length of time, a word that Ruth had been unable to have children, or feelings the text does not give (Boaz's, Ruth's or Naomi's). A team telling that adds one of these is offered back gently; if asked, the text does not tell.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 1 ('[[B13-Boaz]] Boaz takes [[B9-Ruth]] Ruth, and she becomes his wife, and he comes to her; and [[B10-YHWH]] YHWH gives her conception, and she bears a son.'); Section 2.1 ('Boaz takes Ruth, and she becomes his wife, and he comes to her; and YHWH gives her conception, and she bears a son.'; 'the narrator says it is YHWH who gives her conception'); Section 3F Scene 1 ('Tells the marriage and the birth in a single swift line, with YHWH's giving of conception at its center.'); Significant Absence in Scene 1 ('The narrator tells no wedding, no span of time, and nothing of the birth itself — only the swift verbs.'); Section 3A Scene 1 (B10 'the one who gives her conception'); Section 5B Figure Flags (FIG_0180 'Boaz → YHWH → Ruth in a breath'; FIG_0194 'YHWH gives her conception'; FIG_0188 'Boaz is not mentioned again in this passage'); Section 4 Propositions 1, 2 and 3; carried forward from P02 R1"
    },
    {
      "id": "R2",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "the women's words to Naomi at 4:14–15 (P4–P7); CB_0008, CB_0001, CB_0005, CB_0046; FIG_0142, FIG_0184, FIG_0183",
      "note": "REQUIRED keep: the women's words to Naomi in the text's order — blessed be YHWH, who has not left you without a redeemer today; may his name be called out in Israel; he will be a restorer of your life and a sustainer of your old age; for your daughter-in-law, who loves you, who is better to you than seven sons, has borne him. The women bless YHWH and speak to Naomi; a telling that has the women bless Naomi herself is a nuance: name it once. The word stays 'redeemer' (P09 R14, P11 R15). The women give their own reason ('for your daughter-in-law … has borne him'), and 'seven sons' stays the women's measure. For the voice only, never to be said: do not call the redeemer 'kinsman' or 'relative', add another reason for the women's words, or explain what 'seven sons' stands for.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 2 ('blessed be [[B10-YHWH]] YHWH, who has not left you without a redeemer today; may his name be called out in [[PL_ISRAEL-Israel]] Israel. He will be a restorer of your life and a sustainer of your old age — for [[B9-Ruth]] your daughter-in-law, who loves you, who is better to you than seven sons, has borne him.'); Section 3F Scene 2 ('The women speak to Naomi and bless YHWH, who has not left her without a redeemer today'); Scene 2 heading ('The women's words to Naomi (4:14–15)'); Section 3C Scene 2 (CB_0008 'the women's words to Naomi begin: blessed be YHWH'; CB_0001 'the redeemer — YHWH has not left Naomi without a redeemer today'; CB_0046 'seven sons — the women's measure'; 'the women say Ruth is better to Naomi than seven sons'); Section 2.1 ('The women say to Naomi: blessed be YHWH, who has not left you without a redeemer today; may his name be called out in Israel.'); Section 2.4 ('It gives the women's words to Naomi: blessed be YHWH, who has not left her without a redeemer today'); Section 5B Figure Flags (FIG_0142 'the women's words: blessed be YHWH, who has not left you without a redeemer today'; FIG_0184 active at Proposition 5; FIG_0183 'her daughter-in-law who loves her is better to her than seven sons'); Section 4 Propositions 4, 5, 6 and 7; carried forward from P02 R10, P09 R14, P11 R15"
    },
    {
      "id": "R3",
      "kind": "TEXTUAL_CLARITY_FLAG",
      "applies_to": "the redeemer and 'his name' at 4:14–15 (P4, P5, P6); MEANING_COORDINATES S2 B? (REDEEMER_GOEL), P4 redeemer B?, P5 name_bearer B?, P6 child B?",
      "note": "The text joins the redeemer to the one Ruth has borne: 'who has not left you without a redeemer today; may his name be called out in Israel; he will be a restorer of your life … for your daughter-in-law … has borne him'. The voice tells it in these words and in this order, and follows the map's reading: the one Ruth has borne is the redeemer, and 'his name' is his. For the voice only, never to be said: do not teach other readings (that the redeemer here is Boaz, or that 'his name' is YHWH's). A telling in which the child is the redeemer keeps the meaning; accept it without comment. A telling that makes Boaz the redeemer of 4:14, or makes 'his name' God's, is offered back gently with the text's words: 'for your daughter-in-law … has borne him'; 'may his name be called out in Israel'.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3A Scene 2 (the child 'The child — גֹּאֵל / \"a redeemer\"'; 'the newborn; the women say YHWH has not left Naomi without a redeemer today, and that he will be a restorer of her life, for her daughter-in-law has borne him'); Section 3B Scene 2 (PL_ISRAEL 'where the women wish his name to be called out'); Section 3C Scene 2 (CB_0005 'the women's wish: may his name be called out in Israel'); Section 3E Scene 2 ('may his name be called out in'); Section 4 Proposition 6 ('What will the child be?'); Section 4 Propositions 4 and 5; the reading is the one the map already held when Marcia approved it (SC-0060), and the team side follows her P11 ruling for 4:5 (P11 R13: a team telling that follows another reading is offered back gently with the map's reading)"
    },
    {
      "id": "R4",
      "kind": "REFERENTIAL_FORM_CHANGE",
      "applies_to": "Ruth at 4:15 (P7): 'your daughter-in-law who loves you'; FIG_0183, CB_0046; FIG_0001 not flagged in P13 (its last firing is P12, 4:10)",
      "note": "REQUIRED keep-image. The women do not say Ruth's name; she is 'your daughter-in-law who loves you', better to Naomi than seven sons. Keep the kinship word and 'who loves you'. A telling that says 'Ruth' keeps the meaning; accept it without comment. A telling in which the women call her 'the Moabite' is offered back gently: the women say 'your daughter-in-law who loves you'. The women's word is 'loves'; the hesed word of 1:8, 2:20 and 3:10 is not said here.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3A Scene 2 (B9 'Ruth; the women do not say her name — she is \"your daughter-in-law who loves you\"'; Referential form '\"your daughter-in-law who loves you … better to you than seven sons\"'); Significant Absence in Scene 2 ('They do not say Ruth's name or call her the Moabite; she is \"your daughter-in-law who loves you\".'); Section 2.2 ('The women do not call Ruth by her name or \"the Moabite\"; she is \"your daughter-in-law who loves you\", better to Naomi than seven sons.'); Section 5B Figure Flags (FIG_0183 'her daughter-in-law who loves her is better to her than seven sons'); Section 4 Proposition 7 ('she loves Naomi'); MEANING_COORDINATES S2 B9 DAUGHTER_IN_LAW_WHO_LOVES_YOU, P7 bearer_referential_form; carried forward from P07 R7, P11 R8 (FIG_0001) and P09 R3 (hesed)"
    },
    {
      "id": "R5",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "Naomi and the child at 4:16 (P8, P9): she takes him, sets him on her bosom, becomes his omenet; FIG_0185, FIG_0186",
      "note": "REQUIRED keep: Naomi takes the child, sets him on her bosom, and becomes his nurse — omenet, the one who looks after a child; the voice may explain the word. A telling 'she took care of him' or 'she raised him' keeps the meaning; accept it without comment. For the voice only, never to be said: do not say that Naomi nursed him at the breast, that she adopted him, or that he became hers by law, and do not have anyone hand the child to her — Naomi takes the child. A team telling that says one of these is offered back gently; if asked for more, the text does not tell.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 3 ('[[B3-Naomi]] Naomi takes the child, sets him on her bosom, and becomes his nurse.'); Section 2.1 ('Naomi takes the child, sets him on her bosom, and becomes his nurse.'); Section 3A Scene 3 (B3 'the one who takes the child to her bosom and becomes his nurse (omenet — the one who looks after a child)'); Section 3F Scene 3 ('Naomi takes the child to her bosom and becomes his nurse'); Section 5B Figure Flags (FIG_0185 'the child to Naomi's bosom'; FIG_0186 'Naomi as the child's nurse'); Section 4 Propositions 8 and 9"
    },
    {
      "id": "R6",
      "kind": "DISCOURSE_THREAD_ADVANCED",
      "applies_to": "T2 line-and-redemption, T6 divine action and T4 hesed at 4:13–17; canon-record links: FIG_0007 closes here; FIG_0194, FIG_0192 and FIG_0189 continue to P14",
      "note": "T2 (line and redemption; P05 R8, P07 R12, P09 R14, P11 R14): Boaz's conditional promise of 3:13 (P09 R15) was resolved as told at 4:6–8 (P11 R10), and at 4:10 Boaz declared that he had bought Ruth to be his wife (P12); at 4:13 the marriage is told: Boaz takes Ruth, and she becomes his wife. The women say YHWH has not left Naomi without a redeemer today (4:14). T6 (divine action; opened at 1:6, P02 R1, R9): the narrator says YHWH gives her conception — the verb 'give' (natan) of 1:6 ('to give them bread') and of the wishes at the gate (4:11, 4:12). T4 (hesed; P07 R12, P09 R3, R14): no station in 4:13–17; the women say 'who loves you'. In the canon record FIG_0007 (opened at P01, 1:1) closes here, and FIG_0194, FIG_0192 and FIG_0189 continue to P14 (4:18–22). These links stay here only and are not part of P13's telling.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3E Scene 1 ('she becomes his wife'); Section 3E Scene 2 ('who has not left you without a redeemer today'); Section 3A Scene 1 (B10 'the one who gives her conception'); Section 3A Scene 2 (B9 'Ruth; the women do not say her name — she is \"your daughter-in-law who loves you\"'); Section 5B Figure Flags (FIG_0007 'the narrator names David from a time after the events'; FIG_0194 'YHWH gives her conception'; FIG_0192 'Obed, Jesse, David'; FIG_0189 'the narrator's closing names'); the forward links to P14 are recorded only here and in cross_pericope_pair_verification — the map carries none (SC-0088); carried forward from P02 R1, R9, P05 R8, P07 R12, P09 R3, R14, R15, P11 R10, R14"
    },
    {
      "id": "R7",
      "kind": "NAMING_SEQUENCE_PRESERVATION",
      "applies_to": "the naming at 4:17 (P10–P12): 'a son has been born to Naomi' · Obed · father of Jesse · father of David; FIG_0182, FIG_0181, CB_0047",
      "note": "REQUIRED keep, in order: the neighbor-women call a name for him, saying 'a son has been born to Naomi'; they call his name Obed; he is the father of Jesse, the father of David. The name is given by the neighbor-women. The text does not say why the name Obed; if asked, the text does not tell. For the voice only, never to be said: do not give a reason for the name Obed, and do not say that Naomi became his mother or that he became hers by law. The words are the women's: 'a son has been born to Naomi'. A team telling that gives a reason for the name, or makes Naomi his mother, is offered back gently with the women's words.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 3 ('The neighbor-women call out a name for him, saying a son has been born to Naomi; and they call his name [[B25-Obed]] Obed.'); Significant Absence in Scene 3 ('The neighbor-women give the child his name; the text does not say why the name Obed.'); Section 3A Scene 3 (B24 'the ones who call a name for the child, saying a son has been born to Naomi, and call him Obed'; B25 'the child Naomi takes to her bosom; the neighbor-women call him Obed'); Section 3C Scene 3 (CB_0047 'the name the neighbor-women call him, after they say a son has been born to Naomi'); Section 5B Figure Flags (FIG_0182 'the naming sequence: born-to-Naomi · Obed · father of Jesse · father of David'; FIG_0181 'here the neighbor-women call a name for the child'); Section 4 Propositions 10, 11 and 12"
    },
    {
      "id": "R8",
      "kind": "SIGNIFICANT_ABSENCE",
      "applies_to": "David named at 4:17c (P12) with nothing more; CB_0048, FIG_0007, FIG_0192, FIG_0189",
      "note": "The narrator names David and says nothing more about him. The voice says only 'David'. For the voice only, never to be said: do not call David king, say who he is or will be, or bring in anything from other books; if asked, the text gives only his name. A team telling 'King David' ('o rei Davi') is a nuance: the voice names it once — 'a história dá só o nome dele, Davi' ('the story gives only his name, David') — without a send-back, and moves on. The narrator speaks from a time after the events: he is the father of Jesse, the father of David.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Significant Absence in Scene 3 ('The narrator names David and says nothing more about him.'); Section 3C Scene 3 (CB_0048 'the narrator names David and says nothing more about him'; 'the last name in the verse: Jesse is the father of David'); Section 3A Scene 3 (B26 'Jesse the son of Obed; David the son of Jesse'); Section 3D Scene 3 ('the narrator's reach to a later time'); Section 3E Scene 3 ('He is the father of [[B26-Jesse-and-David]] Jesse, the father of David.'); Section 5B Figure Flags (FIG_0007 'the narrator names David from a time after the events'; FIG_0192 'Obed, Jesse, David'; FIG_0189 'the narrator's closing names'); Section 4 Proposition 12"
    },
    {
      "id": "R9",
      "kind": "WITHHELD_PAIRING_PER_SOURCE_DISCIPLINE",
      "applies_to": "the child and the name of the dead (P3, P5, P10): 4:13–17 does not join them; canon-record FIG_0002 / CB_0005 (4:5, 4:10)",
      "note": "In this passage the text does not say that the child raises up the name of the dead, or that he is counted as Mahlon's or Elimelech's son; the women's words are 'a son has been born to Naomi' and 'may his name be called out in Israel'. For the voice only, never to be said: do not make that link, and bring in no law the story does not cite (the levirate law, Deuteronomy 25). A telling that recalls Boaz's words at the gate — he bought Ruth to raise up the name of the dead — is correct; accept it without comment. A telling that says the child is Mahlon's or Elimelech's son, or that the name of the dead now lives on, is offered back gently with the women's words. In the canon record the name-of-the-dead words of 4:5 and 4:10 (FIG_0002, CB_0005; P11 R11, P12) are not joined to 4:13–17.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3A Scene 1 (the child 'the son Ruth bears after Boaz comes to her'); Section 3C Scene 2 (CB_0005 'the women's wish: may his name be called out in Israel'); Section 3A Scene 3 (B25 'son of Ruth and Boaz; the neighbor-women say a son has been born to Naomi; the father of Jesse'); Section 3E Scene 3 ('saying a son has been born to Naomi'); Section 4 Proposition 10 ('a son has been born to Naomi'); carried forward from P11 R11, R14 (FIG_0002 continues to P12 only)"
    },
    {
      "id": "R10",
      "kind": "SIGNIFICANT_ABSENCE",
      "applies_to": "who is spoken to and who is not mentioned (S2, S3): the women speak to Naomi; Boaz not mentioned after 4:13; Ruth not mentioned in 4:16–17; FIG_0016 (closes here), FIG_0188",
      "note": "Facts kept: the women speak to Naomi; they say nothing to Ruth or to Boaz, and neither Ruth nor Boaz speaks in 4:13–17. Boaz is not mentioned after 4:13 in this passage; Ruth is not mentioned in 4:16–17; here Naomi takes the child. For the voice only, never to be said: do not give Ruth or Boaz words or feelings here (for example, 'Ruth was glad to give the child to Naomi'), do not comment on why they are not mentioned, and do not say whether Ruth or Naomi was at the gate in 4:9–12; if asked, the text does not say ('this young woman', 4:12, is not read as proof either way). A team telling that gives Ruth or Boaz words or feelings here is offered back gently.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Significant Absence in Scene 2 ('The women speak to Naomi; they say nothing to Ruth or to Boaz, and Boaz is not mentioned.'); Significant Absence in Scene 3 ('Ruth is not mentioned in this scene; the neighbor-women say a son has been born to Naomi. Boaz is not mentioned after 4:13 in this passage.'); Section 2.1 ('the women speak to Naomi, not to Ruth or to Boaz'); Section 3A Scene 1 (B13 'the one who takes Ruth as wife and comes to her; after this verse he is not mentioned again in this passage'); Section 5B Figure Flags (FIG_0016 'Ruth and Naomi are not at the gate in 4:1–8, and in 4:9–12 neither of them speaks; here Naomi takes the child'; FIG_0188 'Boaz is not mentioned again in this passage'); carried forward from P11 R6 (4:1–8) and P12 R3 (4:9–12: neither Ruth nor Naomi speaks; ruling D2 of 2026-09-28)"
    },
    {
      "id": "R11",
      "kind": "CROSS_PERICOPE_PAIRING_CLOSED_HERE",
      "applies_to": "the same words heard again (P4, P5, P6, P8, P10): FIG_0187 (P12 P8 → P13 P4), FIG_0014 (P11 P13 → middle P12 P8 → P13 P4, closes here), FIG_0181 (registry P04 1:19 → P13 P10), FIG_0142 (P13 P4); 'the child' (yeled) at 4:16 (P8), the word of 1:5; its never-rule is R13",
      "note": "PREFERRED keep-images, heard as the same words again: 'name … call' at the gate (4:11, 'call out a name in Bethlehem') and in the women's wish (4:14, 'may his name be called out in Israel'); YHWH's name, spoken in the blessing at the gate (4:11–12), spoken again by the women (4:14); the women of the town who spoke at Naomi's return and heard 'do not call me Naomi, call me Mara' (1:19–20), and the neighbor-women who now call a name (4:17); 'restorer', in Hebrew 'one who brings back' (4:15), the verb of Naomi's 'YHWH has brought me back empty' (1:21). Keep the same words where the language allows; the voice may say that a word comes again. At 4:16 the child is 'the child' (yeled), the word of 1:5; the voice may say that the same word comes again. Canon record only, not part of P13's telling: FIG_0142's registry opening at P09 (not flagged there) and Naomi's 'blessed … who has not' at 2:20.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 2.2 ('At 4:11 all the people at the gate and the elders blessed Boaz and said: call out a name in Bethlehem; here the women bless YHWH and wish: may his name be called out in Israel — the same words, name and call.'; 'YHWH's name, spoken in the blessing at the gate, is spoken again in the women's words.'; 'At her return the women of the town said \"Is this Naomi?\" (1:19), and Naomi told them: do not call me Naomi, call me Mara (1:20); here the women speak to Naomi, and the neighbor-women call a name — the child's.'; 'here the women say he will be \"a restorer of your life\" — in Hebrew \"one who brings back\", the same verb Naomi used when she said YHWH had brought her back'; 'At 4:16 the child is \"the child\" (yeled), the word used at 1:5 for Naomi's two children.'); Section 3A Scene 3 (B25 'הַיֶּלֶד / \"the child\"'); Section 3C Scene 2 (CB_0001 'the word \"redeemer\", said at the gate (4:1–8), said again by the women'); Section 5B Figure Flags (FIG_0187 'all the people at the gate and the elders blessed at 4:11–12; here the women bless; the words name and call come again (4:11, 4:14)'; FIG_0014 'YHWH's name, spoken in the blessing at the gate (4:11–12), is spoken again in the women's words'; FIG_0181 'at Naomi's return the women spoke and Naomi told them what to call her (1:19–20); here the neighbor-women call a name for the child'; FIG_0142 'the women's words: blessed be YHWH, who has not left you without a redeemer today'); Section 4 Propositions 4, 5, 6, 8 and 10; carried forward from P11 R6 (FIG_0014) and the P12 opening of FIG_0187; the child-word of 1:5 is P01 R11's (carries_forward_to none; noted here as a word heard again, not carried as a keep-form)"
    },
    {
      "id": "R12",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "register: pericope INFORMAL_CASUAL; S2 CEREMONIAL at scene level; S3 in the pericope-level INFORMAL_CASUAL (MEANING_COORDINATES register_overrides)",
      "note": "Pericope-level INFORMAL_CASUAL — the narrator's telling of the marriage, the birth, and the naming. Scene 2, the women's words to Naomi (4:14–15), lifts to CEREMONIAL: a set 'blessed be YHWH' benediction invoking the divine name. Scene 3, Naomi taking the child and the neighbor-women naming him (4:16–17), stays in the pericope-level INFORMAL_CASUAL.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 1 Metadata multi-level register tagging ('Pericope-level INFORMAL_CASUAL — the narrator's telling of the marriage, the birth, and the naming.'; 'Scene 2, the women's words to Naomi (4:14–15), lifts to CEREMONIAL: a set \"blessed be YHWH\" benediction invoking the divine name.'; 'Scene 3, Naomi taking the child and the neighbor-women naming him (4:16–17), stays in the pericope-level INFORMAL_CASUAL.'); MEANING_COORDINATES register_overrides (scene_level S2 CEREMONIAL only)"
    },
    {
      "id": "R13",
      "kind": "CROSS_PERICOPE_PAIRING_CLOSED_HERE",
      "applies_to": "the same words heard again (P4, P5, P6, P8, P10; R11): no answer, no fulfilment, no end of Naomi's grief; FIG_0187, FIG_0014 (moved out of R11, 2026-09-28)",
      "note": "For the voice only, never to be said: do not say that the women's blessing answers the blessing at the gate or fulfils it, or that it ends Naomi's grief.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 2.2 ('At 4:11 all the people at the gate and the elders blessed Boaz and said: call out a name in Bethlehem; here the women bless YHWH and wish: may his name be called out in Israel — the same words, name and call.'; 'YHWH's name, spoken in the blessing at the gate, is spoken again in the women's words.'; 'here the women say he will be \"a restorer of your life\" — in Hebrew \"one who brings back\", the same verb Naomi used when she said YHWH had brought her back'); Section 5B Figure Flags (FIG_0187 'all the people at the gate and the elders blessed at 4:11–12; here the women bless; the words name and call come again (4:11, 4:14)'; FIG_0014 'YHWH's name, spoken in the blessing at the gate (4:11–12), is spoken again in the women's words'); Section 4 Propositions 4, 5 and 6; Marcia's map standard of 2026-09-28, items 3 and 6 (the women's words never told as an answer or a fulfilment); carried forward from P11 R6 (FIG_0014) and the P12 opening of FIG_0187"
    }
  ],
  "cross_pericope_pair_verification": {
    "pairs": [
      {
        "fig_id": "FIG_0014",
        "opens_at": "P11 P13 (4:7; no one says the name of God in the proceeding)",
        "closes_at": "P13 P4 (4:14a 'blessed be YHWH'); middle station at P12 P8 (4:11b, YHWH named in the blessing at the gate)",
        "verification_status": "VERIFIED",
        "note": "Pair closed at this register (R11), on the three MEANING_COORDINATES: the P11 MC flags FIG_0014 at P13 (4:7a), the P12 MC at P8 (4:11b), the P13 MC at P4 (4:14a). Registry frontmatter (vault note) lists opens-at P11 / closes-at P13, so P12 is the middle station. The P11 row (PENDING, 'for the P12 and P13 registers to settle') is settled here. Recorded as YHWH's name spoken again, never as one blessing answering the other."
      },
      {
        "fig_id": "FIG_0016",
        "opens_at": "P11 P5, P9 (4:3, 4:5; Ruth and Naomi not at the gate in 4:1–8)",
        "closes_at": "P13 P8 (4:16a, Naomi takes the child)",
        "verification_status": "VERIFIED",
        "note": "Pair closed at this register (R10): the P11 MC flags FIG_0016 at P5 and P9, the P13 MC at P8. There is no P12 flag: at 4:9–12 neither Ruth nor Naomi speaks, and the text does not say whether they are at the gate (ruling D2, 2026-09-28). Registry frontmatter (vault note) lists opens-at P11 / closes-at P13; its appears-in also lists P12, and its intended-meaning still reads 'not at the gate in 4:1–12' where ruling D2 keeps 'not at the gate' for 4:1–8 only. Canon-record link only; in P13's telling the fact is only that here Naomi takes the child."
      },
      {
        "fig_id": "FIG_0187",
        "opens_at": "P12 P8 (4:11b, the blessing at the gate)",
        "closes_at": "P13 P4 (4:14a, the women's words: blessed be YHWH)",
        "verification_status": "VERIFIED",
        "note": "Pair closed at this register (R11): the P12 MC flags FIG_0187 at P8, the P13 MC at P4. Registry frontmatter (vault note) lists opens-at P12 / closes-at P13. Recorded as the same words heard again (name and call, 4:11 and 4:14; YHWH's name spoken again), never as the women's blessing answering the one at the gate; the vault note's surface-image and intended-meaning ('structurally paired', 'male-civic and female-domestic blessings frame the resolution') are readings the map does not state."
      },
      {
        "fig_id": "FIG_0142",
        "opens_at": "P09 (registry opens-at only; not flagged in the P09 or P10 map or MEANING_COORDINATES)",
        "closes_at": "P13 P4 (4:14a 'blessed be YHWH, who has not left you without a redeemer today')",
        "verification_status": "DEFERRED",
        "note": "Only the P13 MC flags FIG_0142 (P4, 4:14a). The registry (vault note) lists opens-at P09 / appears-in P09, P10, P13 / closes-at P13, but no P09 or P10 map or MC flags it (SC-0054 found no firing site in 3:6–13). Recorded as a single site at P13; the registry opening is unconfirmed (vault half). The closest same words earlier are Naomi's 'blessed … who has not' at 2:20 (canon record only, R11)."
      },
      {
        "fig_id": "FIG_0181",
        "opens_at": "P04 (registry opens-at, 1:19; not flagged in the P04 map or MEANING_COORDINATES)",
        "closes_at": "P13 P10 (4:17a, the neighbor-women call a name)",
        "verification_status": "DEFERRED",
        "note": "Only the P13 MC flags FIG_0181 (P10, 4:17a). The registry (vault note) lists opens-at P04 / closes-at P13, but the P04 map and MC do not flag it. The same verb 'call' (qara, feminine plural) at 1:20 and 4:17 is recorded in R11 as a word heard again; the vault note's intended-meaning ('gives the child to Naomi's lineage; structurally answers the women's earlier 1:19 recognition question') is a reading the map does not state (vault half)."
      },
      {
        "fig_id": "FIG_0007",
        "opens_at": "P01 P1 (1:1a 'in the days when the judges judged')",
        "closes_at": "P13 P12 (4:17c, the narrator names David from a time after the events)",
        "verification_status": "VERIFIED",
        "note": "Pair closed at this register (R6, R8): the P01 MC flags FIG_0007 at P1, the P13 MC at P12. Registry frontmatter (vault note) lists opens-at P01 / closes-at P13; its appears-in also lists P12, whose MC does not flag it, its scope names 4:7 (P11, not flagged), and its closes-at-proposition reads P01:P1 — mismatches for the vault half. Canon-record link only: 1:1 and 4:17 share no words, and the P13 map carries no backward pointer to 1:1."
      },
      {
        "fig_id": "FIG_0194",
        "opens_at": "P13 P2 (4:13b, YHWH gives her conception); registry opens-at P06, appears-in P06, P09 (not flagged there)",
        "closes_at": "P14 (4:21b–22b)",
        "verification_status": "PENDING",
        "note": "The P13 MC flags FIG_0194 at P2; the P14 MC flags it at P8, P9 and P10. Verification at P14's register (registry closes-at P14). The registry's opens-at P06 and appears-in P06, P09 are not backed by any map or MC (vault half). Canon-record link only, not part of P13's telling (R6)."
      },
      {
        "fig_id": "FIG_0192",
        "opens_at": "P13 P12 (4:17c 'he is the father of Jesse, the father of David')",
        "closes_at": "P14 P8–P10 (4:21b–22b)",
        "verification_status": "PENDING",
        "note": "Opens here: the P13 MC flags FIG_0192 at P12; the P14 MC at P8, P9 and P10. Verification at P14's register (registry opens-at P13 / closes-at P14). Canon-record link only, not part of P13's telling (R6)."
      },
      {
        "fig_id": "FIG_0189",
        "opens_at": "P13 P12 (4:17c, the narrator's closing names)",
        "closes_at": "P14 P10 (4:22b)",
        "verification_status": "PENDING",
        "note": "Opens here: the P13 MC flags FIG_0189 at P12; the P14 MC at P10. Verification at P14's register (registry opens-at P13 / closes-at P14). The vault note's surface-image ('the book's closing scene answers its prologue') and intended-meaning are readings the map no longer states (vault half). Canon-record link only, not part of P13's telling (R6)."
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
      "STATES_AS_TRUE",
      "WISHES_FOR_THIRD_PARTY"
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
    "The high-risk register audit was hand-authored from the corrected P13 map under the 2026-09-28 standard and the SC-0088 rulings: 13 entries (9 do_not_decide: R1, R2, R3, R5, R7, R8, R9, R10, R13 — R2 and R13 since Marcia's word of 2026-09-28 after the session, P13-D6), each traced to the P13 map; the carried-forward items (P02 R1/R9/R10, P05 R8, P07 R7/R12, P09 R3/R14/R15, P11 R6/R8/R10/R11/R14/R15) also cite their source registers (P13-D4).",
    "Propositions stay at meaning-map granularity; multi-event propositions decompose in-slot per the granularity contract.",
    "Forward links out of P13 (FIG_0194, FIG_0192 and FIG_0189 to P14) live only in this register (R6) and the pair table; the map carries none. Those rows stay PENDING until P14's register.",
    "Registry (vault note) data that no map or MEANING_COORDINATES backs: FIG_0142 opens-at P09 and FIG_0181 opens-at P04 (rows DEFERRED); FIG_0194 opens-at P06 / appears-in P06, P09; FIG_0016 and FIG_0007 appears-in list P12, which flags neither; FIG_0016's intended-meaning reads 'not at the gate in 4:1–12' (ruling D2 keeps it to 4:1–8); FIG_0007's closes-at-proposition reads P01:P1; FIG_0172 and FIG_0017 list closes-at P13, where the P13 map and MEANING_COORDINATES do not flag them (the P12 pair rows record both). The registry's PL_NAOMIS_DWELLING appears_in still lists P13.",
    "Several vault figure notes carry readings in their slugs or surface text that the P13 map no longer states (FIG_0183 'Inverted-Fullness', FIG_0185 'Maternal-Adoption-Locus', FIG_0186 'Faithful-Sustainer', FIG_0187 'male-civic and female-domestic blessings', FIG_0189 'Inclusio-with-Prologue' / 'answers its prologue'); the voice and the Validator see only the code, and the slugs stay in canon for human readers.",
    "Three kinds in this register are not on the approved high_risk_register_kind list — TEXTUAL_CLARITY_FLAG (R3), DISCOURSE_THREAD_ADVANCED (R6) and SIGNIFICANT_ABSENCE (R8, R10); they join the register-kind call already owed under SC-0087 and are not promoted here.",
    "The MEANING_COORDINATES keep ruled SC-0064 values that carry readings the map no longer states — arc EMPTYING_REVERSED, role GRANDMOTHER (S2, S3), B25 role ANCESTOR (faces forward), the P10 slot name reckoned_to — none is voiced. The S1 and S2 child stays B? (he is named only at 4:17).",
    "The vocabulary_additions notes (the dated SC-0064 ruling record) quote the map as it stood before SC-0088 (e.g. 'the redemption completed in marriage', 'the grandmother', 'the female counterpart to the men's gate-blessing', 'closes the communal-naming'); they are kept as history, not as current map text.",
    "Two word explanations are map text under standard item 7: omenet, 'the one who looks after a child' (Section 3A Scene 3), and 'restorer', in Hebrew 'one who brings back' (Section 2.2)."
  ]
}
```

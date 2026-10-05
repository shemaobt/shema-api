---
type: "sta-compilation-log"
pericope: "P14"
status: "valid"
pilot: "pilot-2"
---

# P14 — Ruth 4:18-22 — COMPILATION-LOG

```json
{
  "sta_id": "ruth_pericope_14_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Ruth 4:18-22",
  "pericope_id": "P14",
  "pericope_title": "The generations of Perez: ten names to David",
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
  "confidence_overall_note": "Judgment half machine-drafted (SC-0063, patch-only contract) and ruled by Marcia axis-by-axis under SC-0064 (§A–§E + arc_element). The graduated MEANING_COORDINATES validates block-clean with 0 convergent drift and is lint-clean. Mechanized log: vocabulary_additions are this pericope's ruled mints; the high-risk register audit was hand-authored from the corrected P14 map under SC-0088, on Marcia's standard of 2026-09-28 and her ruling D1 (b) of 2026-09-28 (see P14-D4, P14-D5; R6 made do_not_decide after the session, P14-D6).",
  "compilation_decisions": [
    {
      "decision_id": "P14-D1",
      "decision": "Deterministically compiled a MEANING_COORDINATES skeleton from the approved Meaning Map.",
      "description": "Extracted header/classification, scene + entity IDs + presence, verse-ranges, significant_absence, communicative purpose, proposition anchors/scene-links/cross-refs, and Section-5 concept/figure flags. 47 judgment fields left as typed placeholders for Agent 3. No values invented (extract-only)."
    },
    {
      "decision_id": "P14-D2",
      "decision": "Judgment gaps filled by the SC-0063 drafter (Slice 4).",
      "description": "claude-opus-4-8 under the pinned fm-drafter prompt; structured-output fills merged by the patch-only layer. Provenance: _working/P14/drafts/run-2026-06-12T15-36-24-880Z/."
    },
    {
      "decision_id": "P14-D3",
      "decision": "Ruled by Marcia under SC-0064 (the batch ruling), axis by axis.",
      "description": "§A–§E + the five §B axes (action+tone, proposition_kind, role_in_scene_being, scene_kind, arc_element) ruled across 2026-06-12→19; 6 vocabulary addition(s) CONFIRMED for promotion for this pericope (per-axis ruling-logs in _working/P14/P14-SC-0064-*-RULING-LOG.md). Renames/collapses applied to the MEANING_COORDINATES as recorded amendments where ruled."
    },
    {
      "decision_id": "P14-D4",
      "decision": "High-risk register built under SC-0088 (the SC-0085 program's P12–P14 slice) from the corrected P14 map, on Marcia's standard of 2026-09-28 and her SC-0088 ruling D1.",
      "description": "Drafted from the corrected P14 map (the SC-0088 survey and its adversarial cross-check, 2026-09-28) under Marcia's approved standard of 2026-09-28 («(a), sim, pode seguir com as recomendações», item 16 included) and her four SC-0088 rulings of 2026-09-28 («(b), (b), (a), sim — pode seguir com as recomendações»). The ruling that touches P14 is D1 (b), 'King David' (4:17, 4:22): the book never calls David king and the voice never does; in a team telling 'o rei Davi' is a nuance, named once — «a história dá só o nome dele, Davi» ('the story gives only his name, David') — without a send-back; the same rule and wording as P13 R8 (here R4). The English wording of the entries is the builder's rendering. 11 entries replace the R1 skeleton, 5 do_not_decide (R1 the ten names in order, R2 no woman in the list, R3 no God in the list, R4 David with no title and no comment, R5 the list and the name of the dead). Never-lists are marked 'For the voice only, never to be said' (standard item 16); team-side judgments stand in their own sentences. Two survey doubts are settled by the standard, not asked (cross-check): a telling that recalls Tamar (4:12) or Ruth (4:13) as a mother is correct and accepted without comment (item 5; R2); a telling that leaves a name out is offered back gently as a missing detail (items 11–12; R1). Kinds: NAMING_SEQUENCE_PRESERVATION, STRUCTURAL_ABSENCE_OF_DIVINE_AGENCY, WITHHELD_PAIRING_PER_SOURCE_DISCIPLINE, CROSS_PERICOPE_PAIRING_CLOSED_HERE, REFERENTIAL_FORM_CHANGE and STRUCTURAL_FRAMING_DEVICE from the approved high_risk_register_kind list; SIGNIFICANT_ABSENCE (R2, R4), TEXTUAL_CLARITY_FLAG (R9) and DISCOURSE_THREAD_ADVANCED (R10) as in P11 (not on the approved list; the register-kind call owed under SC-0087). Carried-forward items land: P11 R14 (T2; R5, R10); P01 R10, P02 R5, P06 R4 and P11 R7 — nothing is withheld at 4:18–22, and the list names no Elimelech, Mahlon or Chilion (R5); FIG_0014, FIG_0016, FIG_0001, the hesed and worth threads and T5/T6 have no word in 4:18–22 (R10). Pair table: FIG_0191 (P12 → P14), FIG_0192 (P13 → P14), FIG_0189 (P13 → P14) and FIG_0194 (P13 → P14; the vault's P06 opening not backed by any map or MC) VERIFIED here; FIG_0193 and FIG_0190 VERIFIED within the pericope. One builder wording named for Marcia's yes/no: R3's team-side sentence accepts a recall of 4:13 ('YHWH gave her conception, and she bore a son') without comment, the same reading of item 5 as R2's recall of Ruth bearing the son. The three gate signals (the real audit, high_risk_register_complete, and the map's sta-status) flip together in this change."
    },
    {
      "decision_id": "P14-D5",
      "decision": "Meaning Map + MEANING_COORDINATES corrected under the standard of 2026-09-28 (SC-0088); FIG_0189 and FIG_0194 kept flagged with fact-only notes; CB_0005, CB_0047 and CB_0048 out of the MC S1 objects_in_scene.",
      "description": "The standard applied to the map and the MEANING_COORDINATES together: out of the voice's text — 'the king' / 'a king's lineage' (Ruth never calls David king; item 5), 'the redeemed child' and 'the redeemed Bethlehem household' (the text never calls Obed or the household redeemed; item 1), 'hinge', 'destination', 'arrival', 'claim', 'the line he served', 'quietly traveling toward', 'where this rescue was going' (item 3), the completion and fulfilment frames — 'completes the comparison', 'traced in full', 'answers the prologue', 'the long consequence of YHWH's gift … spelled out' — and the pericope pointers in §5B (item 6), 'at the cradle' and 'seated' (item 8), 'the patriarchs' (item 5), 'the single divine act of the book' (false: 1:6 also tells YHWH's act; item 4), the narrator's 'vantage' (§2.2, §3D). The count fixed: Boaz is the seventh name and Obed the eighth (§2.1, §3A, §3C; BHSA 4:18–22); 'named only here' dropped for Perez (named at 4:12). The only looks back are through the same names, Perez (4:12) and Obed, Jesse and David (4:17) (item 6). §1 without the process text and with 'X fathered Y' (was 'X begot Y'); §2.3 without 'formal' (the register is INFORMAL_CASUAL; item 10). The Significant Absence as facts, with 'It does not name God.' added (BHSA 4:18–22: 19 proper nouns, all men, none divine). Proposition 6 records the form: 'Salmon (the text spells it Salmah here)' (4:20 שַׂלְמָה, 4:21 שַׂלְמוֹן). Cross-check corrections: §3A B27 Relationship without Tamar, and B25 Relationship 'son of Boaz; father of Jesse' (was 'son of Boaz and Ruth'; the list names no woman; the Tamar recall stays in §2.1, §2.2 and §2.4 as context); 'neighbor-women'; 'all the people at the gate and the elders' for 4:11–12; FIG_0189 and FIG_0194 stay flagged in the map (active-figures, §5B) and in the MC P8/P9/P10 figure_flags, as the P13 map keeps them, with fact-only notes — FIG_0189 '(David, the last word of the book)', FIG_0194 '(Boaz fathered Obed, Obed fathered Jesse, Jesse fathered David)', no God — and their links to 1:1 and 4:13 live only in R10 and the pair table. The MC S1 scene_communicative_purpose and significant_absence equal the map's 3F and Significant Absence word for word. Coverage fix in the MC (items 1 and 10): CB_0047 'Obed' and CB_0048 'David' duplicated the beings B25 and B26 in the coverage list, and CB_0005 ('the line of names') is not a thing in the text of 4:18–22 — all three removed from the S1 objects_in_scene (CB_0049, 'the generations of Perez', stays); they remain concept flags (map active-concepts, §3C, §5A; MC cb_flags P1, P8, P10). The three B27 wikilinks follow the registry's book-level name as changed in SC-0088 ('Genealogy Figures' → 'Perez and His Descendants'): [[B27-Perez-and-His-Descendants]] in §3A, §3E and Proposition 1 (id-check name-binding). Map frontmatter sta-status set to complete. Named for Marcia's yes/no: the map §3C keeps its four concept entries while the MC S1 objects keep one (the voice reads §3C as prose; the coverage list reads the MC); the word gloss in the map text (item 7): toledot, 'generations', a word for a line of descent (§2.2). Seen, not changed: B26 'Jesse and David' is one being for two people and its S1 role LINE_TERMINUS fits David only (a clean split needs new registry codes and touches P13 — not done here); B26's registry name 'Jesse and David' and the other map wikilink slugs (the voice sees only the codes); the MC referential_form SALMAH_AND_SALMON; the ruled SC-0064 values DIVINE_CONTEXT, LINE_TERMINUS_REACHED, WEIGHTED and SETTLES (not voiced); §5A CB_0049 '(the named head of the line)'; the propositions' 'What is recorded?'. Made at the SC-0088 integration step, named for Marcia's yes/no: §2.2 'the neighbor-women named the child Obed, and the narrator added: \"he is the father of Jesse, the father of David\" (4:17)' (was 'the neighbor-women named the child Obed — \"he is the father of Jesse, the father of David\" (4:17)', which can be heard as the women's words; the P13 map gives that line to the narrator, §3D and P13 R8; item 1); R7's quote of §2.2 follows."
    },
    {
      "decision_id": "P14-D6",
      "decision": "After the team's session, Marcia's word of 2026-09-28: the never-rules go to the Validator (do_not_decide); R6 flipped whole.",
      "description": "Her words (2026-09-28, after the team's session ended): «A sessão acabou. Pode passar as regras do tipo nunca para o validador; pode trocar \"parente\" por \"resgatador\" nas quatro linhas em que Boaz é o resgatador; pode usar os títulos que você escreveu.» The app's Validator reads, from the register, only the id, kind and note of do_not_decide entries. In P14: R6 (FIG_0191 closes at Perez; 'For the voice only, never to be said: do not present the list as the answer to the blessing or as its fulfilment.') is now do_not_decide as a whole: every sentence in it is a rule on the same name heard again. Note text unchanged. The register now has 11 entries, 6 do_not_decide (R1–R6)."
    }
  ],
  "vocabulary_additions": {
    "proposition_kinds": [
      {
        "value": "FATHERED",
        "source": "P14-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-36-24-880Z (claude-opus-4-8, req cbff07622ed32986…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). MM P2–P10: the repeated \"X fathered Y\" genealogical formula; no approved proposition_kind names a begetting event."
      },
      {
        "value": "GENEALOGY_HEADER",
        "source": "P14-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-36-24-880Z (claude-opus-4-8, req cbff07622ed32986…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). MM P1: \"the line is named / Whose generations? Perez's\" — the toledot-formula header opening the genealogy; no approved proposition_kind names a lineage header."
      }
    ],
    "scene_kinds": [
      {
        "value": "GENEALOGY_SCENE",
        "source": "P14-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-36-24-880Z (claude-opus-4-8, req cbff07622ed32986…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM scene title \"The generations of Perez\" and genre GENEALOGY: the scene is a formal toledot list, a form with no approved scene_kind."
      }
    ],
    "presence_values": [],
    "referential_forms": [],
    "other": [],
    "arc_elements": [
      {
        "value": "GENEALOGICAL_DESCENT",
        "source": "P14-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-36-24-880Z (claude-opus-4-8, req cbff07622ed32986…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1: the passage is \"a ten-name line of descent\"; no approved arc_element covers an unbroken father-to-son lineage chain."
      },
      {
        "value": "LINE_TERMINUS_REACHED",
        "source": "P14-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-36-24-880Z (claude-opus-4-8, req cbff07622ed32986…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19); renamed from LINE_ARRIVAL_AT_DAVID (strip the proper noun 'David' from a cross-Bible type; mirrors the approved role token LINE_TERMINUS for B26; David stays in the prose/referential_form). MM 2.1/2.4: the cadence \"tilts toward its last word\" and \"exists to arrive at David\" — the arrival at the terminal name is the arc's burden, with no approved element for it."
      }
    ],
    "role_in_scene_beings": [
      {
        "value": "LINE_TERMINUS",
        "source": "P14-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-36-24-880Z (claude-opus-4-8, req cbff07622ed32986…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM 3A/2.4: B26 is \"the line's arrival; David the book's destination\" — the terminal name the whole genealogy exists to reach; no approved role_in_scene_being names the endpoint of a descent line."
      }
    ]
  },
  "proposition_kind_slot_sets": [],
  "high_risk_register_audit": [
    {
      "id": "R1",
      "kind": "NAMING_SEQUENCE_PRESERVATION",
      "applies_to": "the ten names in order at 4:18–22 (P1–P10): Perez, Hezron, Ram, Amminadab, Nahshon, Salmon, Boaz, Obed, Jesse, David; FIG_0193, FIG_0190",
      "note": "REQUIRED. Keep every name of the list in the text's order — Perez, Hezron, Ram, Amminadab, Nahshon, Salmon, Boaz, Obed, Jesse, David — each the father of the next, with David as the last name. The voice tells the list in the plain formula 'X fathered Y', said the same way each time. A team telling that changes the order of the names is offered back gently, and the scene is told again. A telling that leaves a name out is offered back gently as a missing detail. Other words for 'fathered' ('begot', 'was the father of', 'had a son') keep the meaning; accept them without comment. For the voice only, never to be said: add no father, son or generation that the list does not give.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 2.1 ('Perez fathered Hezron, Hezron fathered Ram, Ram fathered Amminadab, Amminadab fathered Nahshon, Nahshon fathered Salmon, Salmon fathered Boaz, Boaz fathered Obed, Obed fathered Jesse, and Jesse fathered David.'; 'What weighs on the passage is the order of the names, one generation after another, said the same way each time.'); Section 2.3 ('The same formula, \"X fathered Y\", nine times over, one name after another, with no comment and no pause.'); Section 2.4 ('To speak this passage is to keep the plain repeated formula, every name in its order, and David as the last name.'); Section 3E Scene 1 ('Perez fathered Hezron, and Hezron fathered Ram, and Ram fathered Amminadab, and Amminadab fathered Nahshon, and Nahshon fathered Salmon'); Section 3A Scene 1 (B27 'the first six names of the line, each fathering the next'); Section 4 Propositions 1–10; Section 5B Figure Flags (FIG_0193 'the ten names, from Perez to David'; FIG_0190 'the \"X fathered Y\" formula, repeated nine times')"
    },
    {
      "id": "R2",
      "kind": "SIGNIFICANT_ABSENCE",
      "applies_to": "no woman in the list at 4:18–22 (P1–P10); S1 significant_absence",
      "note": "The list names no woman — not Tamar, not Ruth, not Naomi. It names only fathers and sons. The voice tells the list as the text does, with no mother in it. A team telling that recalls Perez as the son Tamar bore to Judah (4:12), or Obed as the son Ruth bore (4:13), is correct; accept it without comment. For the voice only, never to be said: in its own telling the voice adds no mother to the list and gives no reason why the list names no woman.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Significant Absence in Scene 1 ('The list names no woman — not Tamar, not Ruth, not Naomi; it names only fathers and sons.'); Section 2.1 ('The list names no woman, does not name God, and adds no comment; it stops at David.'); Section 2.4 ('It names no woman, does not name God, and adds no comment.'); Section 2.1 ('the house of Perez, whom Tamar bore to Judah (4:12)'); Section 3A Scene 1 (B27 'the line from Perez down to Salmon, Boaz's father'; B25 'son of Boaz; father of Jesse')"
    },
    {
      "id": "R3",
      "kind": "STRUCTURAL_ABSENCE_OF_DIVINE_AGENCY",
      "applies_to": "4:18–22 (P1–P10): God is not named; FIG_0194 flagged at P8–P10 with a fact-only note, its link to 4:13 in the canon record only (R10)",
      "note": "The list does not name God. It names only fathers and sons. A team telling that recalls what the book told at 4:13 — YHWH gave her conception, and she bore a son — is correct; accept it without comment. A telling that puts God into the list itself (for example 'God gave Boaz this line' or 'God chose David') is an addition; offer it back gently: the list names only fathers and sons. For the voice only, never to be said: put no 'God gave', 'God blessed' or 'God chose' into the list, and do not tell the list as the result of YHWH's gift of conception at 4:13. If asked, the list names only fathers and sons.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Significant Absence in Scene 1 ('It does not name God.'); Section 2.1 ('The list names no woman, does not name God, and adds no comment; it stops at David.'); Section 2.4 ('It names no woman, does not name God, and adds no comment.'); Section 5B Figure Flags (FIG_0194 'Boaz fathered Obed, Obed fathered Jesse, Jesse fathered David')"
    },
    {
      "id": "R4",
      "kind": "SIGNIFICANT_ABSENCE",
      "applies_to": "David at 4:22b (P10): the last name, with no title and no comment; CB_0048; Marcia's ruling D1 (b) of 2026-09-28 — the same rule and wording as P13 R8 (4:17c)",
      "note": "The list stops at David and adds no comment on him. The book gives only his name (4:17, 4:22). For the voice only, never to be said: do not call David king, say who he is or will be, or bring in anything from other books; if asked, the text gives only his name. A team telling 'King David' ('o rei Davi') is a nuance: the voice names it once — 'a história dá só o nome dele, Davi' ('the story gives only his name, David') — without a send-back, and moves on.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Significant Absence in Scene 1 ('It adds no comment on David; the list stops at his name.'); Section 2.1 ('and it ends with David'; 'it stops at David'); Section 2.3 ('The list stops at David.'); Section 3A Scene 1 (B26 'David is the last name of the list and of the book'; 'David son of Jesse'); Section 3C Scene 1 (CB_0048 'the last name of the list'; 'the last word of the list and of the book'); Section 5B Figure Flags (FIG_0189 'David, the last word of the book')"
    },
    {
      "id": "R5",
      "kind": "WITHHELD_PAIRING_PER_SOURCE_DISCIPLINE",
      "applies_to": "the list and 'the name of the dead' (4:5, 4:10): CB_0005 at P1; the T2 thread in the canon record (R10); carried from P11 R14",
      "note": "The list runs from Perez through Salmon, Boaz and Obed to David. It does not speak of the name of the dead and does not name Elimelech, Mahlon or Chilion. A team telling that says the list raises up or keeps the name of the dead, or that it is Elimelech's or Mahlon's line, is an addition; offer it back gently: the list names only fathers and sons, from Perez to David. For the voice only, never to be said: never say that this list raises up or keeps the name of the dead, or that it is Elimelech's or Mahlon's line.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3C Scene 1 (CB_0005 'the list keeps ten names in order, from Perez to David; it does not speak of the name of the dead'); Section 3A Scene 1 (B27 'the line from Perez down to Salmon, Boaz's father'; B13 'son of Salmon; father of Obed'); Section 5A Concept Flags (CB_0005 'the names kept in order, from Perez to David'); Section 3E Scene 1; carried forward from P11 R14 (T2; P05 R8, P07 R12, P09 R14)"
    },
    {
      "id": "R6",
      "kind": "CROSS_PERICOPE_PAIRING_CLOSED_HERE",
      "applies_to": "FIG_0191 at 4:18a (P1) — CLOSES here; opened at P12 P10 (4:12a); CB_0049",
      "note": "PREFERRED keep-image. Perez, the first name of the list (4:18), is the name all the people at the gate and the elders spoke in their blessing: 'may your house be like the house of Perez, whom Tamar bore to Judah' (4:12). It is the same name again, and the voice may recall 4:12 in its words. For the voice only, never to be said: do not present the list as the answer to the blessing or as its fulfilment.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 2.1 ('The list begins with Perez, the name all the people at the gate and the elders spoke in their blessing — the house of Perez, whom Tamar bore to Judah (4:12) — and it ends with David.'); Section 2.2 ('Perez is a name the book has already spoken: all the people at the gate and the elders blessed Boaz, \"may your house be like the house of Perez, whom Tamar bore to Judah\" (4:12).'); Section 3C Scene 1 (CB_0049 'the house of Perez that all the people at the gate and the elders spoke of (4:12)'); Section 5B Figure Flags (FIG_0191 'Perez, the name spoken in the blessing at the gate: \"the house of Perez, whom Tamar bore to Judah\" (4:12)'); Section 4 Proposition 1"
    },
    {
      "id": "R7",
      "kind": "CROSS_PERICOPE_PAIRING_CLOSED_HERE",
      "applies_to": "FIG_0192 at 4:21b–22b (P8–P10) — CLOSES here; opened at P13 P12 (4:17c); CB_0047, CB_0048",
      "note": "PREFERRED keep-image. The names given at 4:17 — Obed, 'the father of Jesse, the father of David' — stand here inside the list (4:21–22), in the same order. They are the same names again, and the voice may recall 4:17 in its words.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 2.2 ('Obed, Jesse, and David are names already given too: the neighbor-women named the child Obed, and the narrator added: \"he is the father of Jesse, the father of David\" (4:17).'); Section 3A Scene 1 (B25 'the child named Obed at 4:17'); Section 3C Scene 1 (CB_0047 'the child's name, given at 4:17, here inside the list'); Section 5B Figure Flags (FIG_0192 'the names Obed, Jesse, and David, already given at 4:17, here inside the list'); Section 4 Propositions 8–10"
    },
    {
      "id": "R8",
      "kind": "REFERENTIAL_FORM_CHANGE",
      "applies_to": "B27 Salmah at 4:20 (P6) / Salmon at 4:21 (P7); MC referential_form SALMAH_AND_SALMON",
      "note": "One ancestor is spelled Salmah at 4:20 (שַׂלְמָה) and Salmon at 4:21 (שַׂלְמוֹן). The map says 'Salmon' and notes the spelling. A team telling with either form, or with the spelling of their own Bible, is correct; accept it without comment. If asked, the voice may say that the text spells the name two ways.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3A Scene 1 (B27 'the name of Boaz's father is spelled two ways in the list — Salmah (שַׂלְמָה, 4:20) and Salmon (שַׂלְמוֹן, 4:21) — one ancestor, both forms in the text'); Section 4 Proposition 6 ('Salmon (the text spells it Salmah here)'); Section 4 Proposition 7"
    },
    {
      "id": "R9",
      "kind": "TEXTUAL_CLARITY_FLAG",
      "applies_to": "minor text points at 4:18a (P1) and in the formula (P2–P10)",
      "note": "Minor text points. (1) 4:18 'these are the generations (toledot) of Perez': 'the descendants of Perez', 'the family line of Perez' and similar wordings are correct, and the voice may explain the word. (2) 'Fathered' (holid): 'fathered', 'begot', 'was the father of' and 'had a son' are all correct. (3) Names as the team's own Bible spells them (e.g. 'Rão', 'Naassom', 'Salmom') are correct. Accept these forms without comment.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 2.2 ('The list is headed \"these are the generations of Perez\" — toledot, \"generations\", a word for a line of descent.'); Section 3C Scene 1 (CB_0049 'Perez, the first name of the list: \"these are the generations of Perez\"'); Section 3E Scene 1 ('These are the generations of'); Section 5B Figure Flags (FIG_0190 'the \"X fathered Y\" formula, repeated nine times')"
    },
    {
      "id": "R10",
      "kind": "DISCOURSE_THREAD_ADVANCED",
      "applies_to": "canon-record links at the book's close: FIG_0189 (P10) and FIG_0194 (P8–P10) flagged with fact-only notes, their links to 1:1 and 4:13 recorded here only; the T2 end; threads with no word in 4:18–22",
      "note": "Canon record only, not part of P14's telling. FIG_0189 (in the registry, the book's close set beside its opening; opened at P13 4:17c) closes at 4:22b, where the map's note says only 'David, the last word of the book'; the list does not repeat the words of 1:1, and that link stays in this record. FIG_0194 (in the registry, YHWH's gift of conception at 4:13 set beside the list; flagged at P13 4:13b) is flagged at 4:21b–22b with the note 'Boaz fathered Obed, Obed fathered Jesse, Jesse fathered David'; the list does not name God and does not repeat the words of 4:13 (R3). T2 (line and redemption; P05 R8, P07 R12, P09 R14, P11 R14) ends in the canon record at P12–P13; the list is the line from Perez to David through Boaz and Obed and names no Elimelech (R5). The hesed thread (FIG_0111, FIG_0133), the worth pair (FIG_0134), the Moabite marker (FIG_0001), the gate silences (FIG_0014, FIG_0016) and the T5 and T6 threads (P02 R9, P03 R5, P03 R12) have no word in 4:18–22 and are not brought into the list.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 5B Figure Flags (FIG_0189 'David, the last word of the book'; FIG_0194 'Boaz fathered Obed, Obed fathered Jesse, Jesse fathered David'); Significant Absence in Scene 1 ('It does not name God.'); Section 2.2 (the only looks back are through the same names: 'Perez is a name the book has already spoken'; 'Obed, Jesse, and David are names already given too'); Section 3C Scene 1 (CB_0005 'it does not speak of the name of the dead'); the links to 1:1 and 4:13 are recorded only here and in cross_pericope_pair_verification — the map carries none (SC-0088); carried forward from P11 R14"
    },
    {
      "id": "R11",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "register: whole passage INFORMAL_CASUAL; no scene-level or moment-level overrides",
      "note": "The whole passage is INFORMAL_CASUAL: the narrator's own voice, reciting the line in the plain formula 'X fathered Y'. The list is said the same plain way from the first name to the last. There are no character speeches, no ceremony, and no register shift.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 1 Metadata multi-level register tagging ('Pericope-level INFORMAL_CASUAL — the narrator's own voice, reciting the line in the plain \"X fathered Y\" formula.'; 'The list is said the same plain way from the first name to the last.'; 'There are no character speeches, no ceremony, and no register shift anywhere in the unit.'); Section 2.3 ('Even and steady.'); MEANING_COORDINATES register_overrides (scene_level null, moment_level null)"
    }
  ],
  "cross_pericope_pair_verification": {
    "pairs": [
      {
        "fig_id": "FIG_0191",
        "opens_at": "P12 P10 (4:12a 'the house of Perez, whom Tamar bore to Judah')",
        "closes_at": "P14 P1 (4:18a 'these are the generations of Perez')",
        "verification_status": "VERIFIED",
        "note": "Pair closed at this register (R6), on the two MEANING_COORDINATES: the P12 MC flags FIG_0191 at P10 (4:12a, with FIG_0170 and CB_0049), the P14 MC at P1 (4:18a). Registry frontmatter (vault note) confirms opens-at P12 / closes-at P14. The same name again (Perez); the P14 map's note says no more than 4:12's words. The P12 register is built in the same change (SC-0088)."
      },
      {
        "fig_id": "FIG_0192",
        "opens_at": "P13 P12 (4:17c 'he is the father of Jesse, the father of David')",
        "closes_at": "P14 P8–P10 (4:21b–22b Boaz fathered Obed, Obed fathered Jesse, Jesse fathered David)",
        "verification_status": "VERIFIED",
        "note": "Pair closed at this register (R7): the P13 MC flags FIG_0192 at P12 (4:17c, with FIG_0182, FIG_0189, FIG_0007 and CB_0048), the P14 MC at P8, P9 and P10. Registry frontmatter (vault note) confirms opens-at P13 / closes-at P14. The same names again, in the same order."
      },
      {
        "fig_id": "FIG_0189",
        "opens_at": "P13 P12 (4:17c)",
        "closes_at": "P14 P10 (4:22b; the map's note: 'David, the last word of the book')",
        "verification_status": "VERIFIED",
        "note": "Flag kept at P14 P10 with a fact-only note, as the P13 map keeps its own (SC-0088 cross-check). The P13 MC flags FIG_0189 at P12 (4:17c), the P14 MC at P10 (4:22b); registry frontmatter (vault note) confirms opens-at P13 / closes-at P14. The registry's reading — the book's close set beside its prologue; the vault note's intended-meaning concerns Naomi at the close (P13) — is not part of P14's telling; the list does not repeat the words of 1:1 (R10)."
      },
      {
        "fig_id": "FIG_0194",
        "opens_at": "P13 P2 (4:13b YHWH gives her conception) — the only opening any map or MEANING_COORDINATES flags",
        "closes_at": "P14 P8–P10 (4:21b–22b; the map's note: 'Boaz fathered Obed, Obed fathered Jesse, Jesse fathered David')",
        "verification_status": "VERIFIED",
        "note": "Verified on the two MEANING_COORDINATES: the P13 MC flags FIG_0194 at P2 (4:13b), the P14 MC at P8, P9 and P10. Registry/vault mismatch, reported: the vault note lists appears-in [P06, P09, P13, P14] and opens-at P06, but no P06 or P09 map or MC flags FIG_0194. The P14 note is fact-only and names no God; the link to 4:13 is canon record only (R3, R10)."
      },
      {
        "fig_id": "FIG_0193",
        "opens_at": "P14 P1 (4:18a)",
        "closes_at": "P14 P10 (4:22b) — within the pericope; the map's range P1–P10, the MC flags P1",
        "verification_status": "VERIFIED",
        "note": "Within-pericope figure (R1): the ten names, from Perez to David. Registry frontmatter (vault note) opens-at and closes-at P14. The map gives the range Propositions 1–10; the MC flags the first proposition only (consistency only; not voiced)."
      },
      {
        "fig_id": "FIG_0190",
        "opens_at": "P14 P2 (4:18b)",
        "closes_at": "P14 P10 (4:22b) — within the pericope; the map's range P2–P10 (nine formulas), the MC flags P2",
        "verification_status": "VERIFIED",
        "note": "Within-pericope figure (R1): the 'X fathered Y' formula, repeated nine times (BHSA: הוֹלִיד ×9). Registry frontmatter (vault note) opens-at and closes-at P14. The map gives the range Propositions 2–10; the MC flags the first proposition only (consistency only; not voiced)."
      }
    ]
  },
  "validation_checklist": {
    "meaning_map_contains_only_story_content": true,
    "meaning_coordinates_contains_only_inference_signal": true,
    "every_proposition_has_cb_flags_and_figure_flags": true,
    "no_grammatical_frame_slot_names": true,
    "speech_act_present_on_all_component_records": true,
    "speech_act_values_used": [],
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
    "The high-risk register audit was hand-authored from the corrected P14 map under SC-0088 (Marcia's standard of 2026-09-28 and her ruling D1 (b)): 11 entries (6 do_not_decide: R1–R6 — R6 since Marcia's word of 2026-09-28 after the session, P14-D6), each traced to the P14 map; the carried-forward items (P01 R10, P02 R5, P06 R4, P11 R7, P11 R14, and the threads named in R10) also cite their source registers (P14-D4). Marcia's merge word is pending.",
    "Propositions stay at meaning-map granularity; multi-event propositions decompose in-slot per the granularity contract.",
    "The links of FIG_0189 (the book's close set beside its opening, 1:1) and FIG_0194 (YHWH's gift of conception at 4:13) live only in R10 and the pair table; both flags stay in the map and MC with fact-only notes. Registry/vault mismatch: the vault FIG_0194 note lists appears-in [P06, P09, P13, P14] and opens-at P06, but no P06 or P09 map or MEANING_COORDINATES flags it; the vault FIG_0189 note's intended-meaning concerns Naomi at the close (P13), not the list.",
    "B26 is one being for two people (Jesse and David); its S1 role LINE_TERMINUS fits David only (the P10 slot begotten_role LINE_TERMINUS is David's). A clean split needs new registry codes (registry + vault BCD) and touches P13, so it is not made here.",
    "CB_0005, CB_0047 and CB_0048 are out of the MC S1 objects_in_scene (SC-0088 coverage fix) but keep their §3C entries in the map, their §5A lines and their MC cb_flags (P1, P8, P10); the map §3C lists four concept entries, the MC S1 objects one (CB_0049).",
    "Map-range vs MC-first-only flags (consistency only; not voiced): FIG_0193 (map Propositions 1–10; MC P1), FIG_0190 (map Propositions 2–10; MC P2), CB_0005 (map Propositions 1–10; MC P1).",
    "Three kinds in this register are not on the approved high_risk_register_kind list — SIGNIFICANT_ABSENCE (R2, R4), TEXTUAL_CLARITY_FLAG (R9) and DISCOURSE_THREAD_ADVANCED (R10); used as in P11 and not promoted here (the register-kind call owed under SC-0087).",
    "The MEANING_COORDINATES keep the ruled SC-0064 values DIVINE_CONTEXT (context_elements; the list names no God, R3), LINE_TERMINUS_REACHED, WEIGHTED and SETTLES, and the B27 referential_form SALMAH_AND_SALMON (one ancestor, two spellings, R8) — not voiced; the vocabulary_additions notes keep their SC-0064 provenance wording, which quotes the map as it stood before SC-0088."
  ]
}
```

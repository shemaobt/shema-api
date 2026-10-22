---
type: "sta-compilation-log"
pericope: "P12"
status: "valid"
pilot: "pilot-2"
---

# P12 — Ruth 4:9-12 — COMPILATION-LOG

```json
{
  "sta_id": "ruth_pericope_12_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Ruth 4:9-12",
  "pericope_id": "P12",
  "pericope_title": "You are witnesses this day: the names spoken and the gate's blessing",
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
  "confidence_overall_note": "Judgment half machine-drafted (SC-0063, patch-only contract) and ruled by Marcia axis-by-axis under SC-0064 (§A–§E + arc_element). The graduated MEANING_COORDINATES validates block-clean with 0 convergent drift and is lint-clean. Mechanized log: vocabulary_additions are this pericope's ruled mints; the high-risk register audit was hand-authored from the corrected P12 map under SC-0088 — Marcia's standard of 2026-09-28 and her four SC-0088 rulings of 2026-09-28 (see P12-D4, P12-D5; the never-rules made do_not_decide after the session, P12-D6); her merge word on the SC-0088 package is owed.",
  "compilation_decisions": [
    {
      "decision_id": "P12-D1",
      "decision": "Deterministically compiled a MEANING_COORDINATES skeleton from the approved Meaning Map.",
      "description": "Extracted header/classification, scene + entity IDs + presence, verse-ranges, significant_absence, communicative purpose, proposition anchors/scene-links/cross-refs, and Section-5 concept/figure flags. 79 judgment fields left as typed placeholders for Agent 3. No values invented (extract-only)."
    },
    {
      "decision_id": "P12-D2",
      "decision": "Judgment gaps filled by the SC-0063 drafter (Slice 4).",
      "description": "claude-opus-4-8 under the pinned fm-drafter prompt; structured-output fills merged by the patch-only layer. Provenance: _working/P12/drafts/run-2026-06-12T15-25-23-642Z/."
    },
    {
      "decision_id": "P12-D3",
      "decision": "Ruled by Marcia under SC-0064 (the batch ruling), axis by axis.",
      "description": "§A–§E + the five §B axes (action+tone, proposition_kind, role_in_scene_being, scene_kind, arc_element) ruled across 2026-06-12→19; 6 vocabulary addition(s) CONFIRMED for promotion for this pericope (per-axis ruling-logs in _working/P12/P12-SC-0064-*-RULING-LOG.md). Renames/collapses applied to the MEANING_COORDINATES as recorded amendments where ruled."
    },
    {
      "decision_id": "P12-D4",
      "decision": "High-risk register drafted under SC-0088 (the P07–P14 register-completion program opened by SC-0085) from the corrected P12 map, under Marcia's standard of 2026-09-28 and her four SC-0088 rulings of 2026-09-28.",
      "description": "Her word on the standard (padrao-do-mapa, 2026-09-28): «(a), sim, pode seguir com as recomendações», item 16 included; on the four SC-0088 rulings: «(b), (b), (a), sim — pode seguir com as recomendações». Two touch P12: D2 (b) — in 4:9–12 the map says only 'Neither Ruth nor Naomi speaks.'; the voice never says whether Ruth or Naomi is at the gate, and if asked, the text does not say ('this young woman', 4:12, is not read as proof either way); P11's 'Ruth and Naomi are not at the gate' stays for 4:1–8 (R3); D3 (a) — 'do worthily' (4:11) keeps the worth-word chayil of 2:1 and 3:11; worth, standing, strength, prosperity or means are correct without comment; 'have (many) children' is offered back gently with the map's reading, as at 4:5; the voice does not teach the variants (R9, CB_0032). D1 ('King David') does not touch 4:9–12; D4 (fixes in approved passages) lies outside this file. The English wording of the entries is the builder's rendering, from the SC-0088 survey drafts as corrected by its cross-check. 12 entries replace the R1 skeleton, 4 do_not_decide (R2, R3, R5, R6: R2 Boaz's purpose stays a purpose, no law the story does not cite; R3 the silences of 4:9–12; R5 the blessing — wishes, no outside stories, no Tamar–Ruth link, no later names; R6 no child and no taking-home told here). Never-lists read 'For the voice only, never to be said' (standard item 16); R3 keeps the 'Voice and team' form of the P11 R6 wording it carries. Kinds: WITHHELD_PAIRING_PER_SOURCE_DISCIPLINE (R1), STRUCTURAL_FRAMING_DEVICE (R2, R5, R10), NAMING_SHIFT (R7), CROSS_OCCURRENCE_INTRA_PERICOPE (R8) and FIGURE_FIRST_OCCURRENCE (R9) from the approved high_risk_register_kind list; SIGNIFICANT_ABSENCE (R3, R6), TEXTUAL_CLARITY_FLAG (R11) and DISCOURSE_THREAD_ADVANCED (R4, R12) as in SC-0087 (not on the approved list). R4 records FIG_0014's middle station with a non-closing kind (carries_forward_to P13_audit): the pair closes at P13 (4:14), as the registry says. Carried-forward items land: P01 R10, P02 R5, P06 R4, P11 R7 (the pairing, said at 4:10 — R1); P07 R4, P11 R11 (only 'the dead' — R2); P11 R6 (the silences — R3, for 4:9–12 under D2); P11 R10 (resolved as told — R6); P07 R7, P11 R8 (Ruth the Moabite — R7); P05 R1, R7, P09 R6 (the worth-word — R9); P02 R10, P01 R6, P02 R1 (R5); P03 R12, P05 R8, P07 R12, P09 R14, P11 R14 (threads — R12). Pair table: FIG_0001, FIG_0110, FIG_0002, FIG_0005 (sequence link only) and FIG_0003 VERIFIED (close here); FIG_0172, FIG_0171, FIG_0004 and FIG_0170 VERIFIED within the pericope; FIG_0014 (middle station), FIG_0187, FIG_0191, FIG_0016 and FIG_0017 PENDING. Forward links to P13 and P14 live only in this register (R4, R12) and the pair table, never in the map. The three gate signals (the real audit, high_risk_register_complete, and the map's sta-status) flip together in this change."
    },
    {
      "decision_id": "P12-D5",
      "decision": "Meaning Map + MEANING_COORDINATES corrected under the 2026-09-28 standard and the SC-0088 rulings; FIG_0003 and CB_0032 flagged; CB_0009 no longer a Scene 2 object; the second B4 entry removed from the MC S1.",
      "description": "The SC-0088 survey edits for P12 applied as corrected by its cross-check, with the cross-check's missed items (map §1, §2.1–§2.4, Scenes 1–2 3A–3F and Significant Absences, §4 Propositions 10–11, §5A, §5B): no future in §2.1 (read by the later passages' story-so-far digest) — 'the name yet to be born' out, and the denial 'The seed is asked for in the blessing, not told as given.' kept only in the Scene 2 absence; 'Boaz says to', not 'turns to' (4:9); the wish kept a wish ('the seed that YHWH will give you', Hebrew yitten); no Genesis backstory, no levirate law, no 'precedent', 'outsider-brides' or 'matriarchs'; no intent ('withheld', 'careful namelessness', 'deliberate'); Elimelech not 'named openly now' (he is named at 4:3); Boaz's purpose kept a purpose ('secured', 'alive', 'erased from the town's record' out); no 'field' at 4:9–10; the forward pointers to P13, P14, the genealogy and David out of the map. D2 applied: the Scene 1 and Scene 2 Significant Absences open 'Neither Ruth nor Naomi speaks.'; §2.2 ends with the same sentence; 'absent from the scene' dropped from B3 Naomi and B9 Ruth in Scene 1 (builder extension under D2, named for Marcia's yes/no). D3 applied: CB_0032 flagged at Proposition 9 (map active-concepts and Section 5A; MC P9 cb_flags) — the third chayil after 2:1 and 3:11. FIG_0003 flagged at Proposition 5 (map active-figures and Section 5B; MC P5 figure_flags): 4:10 'from the gate of his place' (the registry closes-at P12; P11 R14 left the close for P12). Coverage fixes in the MC (standard items 1 and 10): the second S1 entry for B4 (DECEASED_KIN, referential_form HA_MET_THE_DEAD) removed, so Mahlon is counted once — the map keeps 'The dead' as an uncoded prose entry in Scene 1; CB_0009 removed from the S2 objects and its Section 3C entry removed from the map, since YHWH is the being B10 — CB_0009 stays a flag (active-concepts, Section 5A, MC P8/P11 cb_flags); this supersedes the survey's wording edit of that 3C line. B27's link slug follows its book-level name in the registry ('Perez and His Descendants', the SC-0088 registry change) at its 3 places in the map. The MC's two scene purposes and significant absences equal the map's 3F and Significant Absence texts word for word. Map frontmatter sta-status set to complete. Unchanged (not voiced): register overrides, the Level-1 values, slot names, scene titles and the passage title. Builder extensions named for Marcia's yes/no, beyond the listed texts: (1) Scene 2 B13 Role reads 'the one the blessing is spoken to — his house, and \"the seed that YHWH will give you\"' — the cross-check's 'the seed YHWH will give him' with the wish quoted, as the cross-check's own §2.3 correction does; (2) Scene 1 PL7 Role 'the place from which the dead man's name is not to be cut off' (was 'must not be cut off'; item 2, Boaz's purpose kept a purpose, as the Effect line says); (3) Scene 2 PL7 Role 'where the people witness and bless' (was 'where the people stand to witness and bless'; item 1, the text does not say they stand); (4) §2.3 '\"you are witnesses\" opening and closing it' (was 'the bracketing \"you are witnesses\" closing it like a seal'; item 8, an image the text does not give); (5) §2.3 ends 'to the broad, generous swing of the blessing.' (the clause '— the gate, which has been doing careful procedural work, breaks into blessing' cut; item 3, a verdict on the gate's work). (4) and (5) were made at the SC-0088 integration step, after the builders reported them as survivors."
    },
    {
      "decision_id": "P12-D6",
      "decision": "After the team's session, Marcia's word of 2026-09-28: the never-rules go to the Validator (do_not_decide); R1 flipped whole, R9's ruling-D3 sentences moved into a new do_not_decide entry R13; the Compilation Log's link-syntax prose in plain words.",
      "description": "Her words (2026-09-28, after the team's session ended): «A sessão acabou. Pode passar as regras do tipo nunca para o validador; pode trocar \"parente\" por \"resgatador\" nas quatro linhas em que Boaz é o resgatador; pode usar os títulos que você escreveu.» The app's Validator reads, from the register, only the id, kind and note of do_not_decide entries, so a never-rule outside do_not_decide reached neither the voice nor the Validator. In P12: R1 (the pairing said at 4:10, with the Orpah rule 'The text names only Ruth as Mahlon's wife and never says whose wife Orpah was; Orpah is not in this passage, and the voice does not bring her in.') is now do_not_decide as a whole: every sentence in it is a rule on the same point (keep 'the wife of Mahlon', no Orpah, the sons' order accepted). R9 mixed five keep-images with ruling D3, so D3's CB_0032 sentences moved, word for word, into a new entry R13 (FIGURE_FIRST_OCCURRENCE, do_not_decide, traced to the §5A CB_0032 flag); R9 keeps the other keep-images and stays not do_not_decide. Note texts otherwise unchanged. The register now has 13 entries, 6 do_not_decide (R1, R2, R3, R5, R6, R13). The known_limitations line on link slugs now says 'inside the link' in plain words, so Obsidian shows no empty link."
    }
  ],
  "vocabulary_additions": {
    "proposition_kinds": [
      {
        "value": "ACQUIRED",
        "source": "P12-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-25-23-642Z (claude-opus-4-8, req 4ded8ce0a993d3b2…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). MM P2/P3: 'I have bought all that was Elimelech's... I have bought Ruth' — the redemption-purchase; no existing proposition_kind names a legal acquisition/redemption (TOOK is take-as-wife; DECLARED is the speech frame). Reviewer may prefer a registry REDEEMED if one exists in P11."
      },
      {
        "value": "NAME_PRESERVED",
        "source": "P12-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-25-23-642Z (claude-opus-4-8, req 4ded8ce0a993d3b2…) · ruled by Marcia 2026-06-13 (proposition_kind Group C)",
        "status": "CONFIRMED",
        "note": "Consolidated neutral type (Marcia's Group-C ruling, option a): the levirate name-preservation formula's two halves — NAME_RAISED (4:10b 'raise up the name of the dead upon his inheritance') and the sentence-shaped NAME_NOT_CUT_OFF (4:10c 'so that the name is not cut off from his kindred') — BOTH renamed to NAME_PRESERVED, one neutral kind. NAME_RAISED + NAME_NOT_CUT_OFF retire; the P12 FM's P4 + P5 are amended to NAME_PRESERVED."
      }
    ],
    "scene_kinds": [],
    "presence_values": [],
    "referential_forms": [],
    "other": [],
    "arc_elements": [
      {
        "value": "COMMUNITY_WITNESS_ATTESTATION",
        "source": "P12-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-25-23-642Z (claude-opus-4-8, req 4ded8ce0a993d3b2…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1: 'The assembly answers as one: we are witnesses' — the choral attestation; distinct from BLESSING_INVOCATION; no existing token for the witness response."
      },
      {
        "value": "DEAD_NAME_RAISED",
        "source": "P12-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-25-23-642Z (claude-opus-4-8, req 4ded8ce0a993d3b2…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1/2.4: 'to raise up the name of the dead upon his inheritance, so that the name of the dead is not cut off' — the raise-up-the-name beat, distinct from the declaration and the blessing; no existing token."
      },
      {
        "value": "PUBLIC_REDEMPTION_DECLARATION",
        "source": "P12-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-25-23-642Z (claude-opus-4-8, req 4ded8ce0a993d3b2…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1: 'Boaz turns... to the whole assembly and declares what he has done... you are witnesses today that I have bought...' — the public legal attestation that completes the redemption; no existing arc token covers a witnessed redemption declaration."
      }
    ],
    "role_in_scene_beings": [
      {
        "value": "WITNESSING_ASSEMBLY",
        "source": "P12-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-25-23-642Z (claude-opus-4-8, req 4ded8ce0a993d3b2…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM 3A: 'the wider assembly called to witness alongside the elders'; TOWNSPEOPLE/PEOPLE name the group but not its scene-defining witnessing function ('you are witnesses today')."
      }
    ]
  },
  "proposition_kind_slot_sets": [],
  "high_risk_register_audit": [
    {
      "id": "R1",
      "kind": "WITHHELD_PAIRING_PER_SOURCE_DISCIPLINE",
      "applies_to": "Ruth 'the wife of Mahlon' at 4:10 (P3): Ruth as Mahlon's wife — not said from 1:4 until here; said at 4:10 — closes P01 R10, P02 R5, P06 R4, P11 R7; the dead named at 4:9 (P2): Elimelech, Chilion, Mahlon",
      "note": "REQUIRED. Boaz names the dead — all that was Elimelech's, and all that was Chilion's and Mahlon's (4:9) — and calls Ruth 'Ruth the Moabite, the wife of Mahlon' (4:10). Here, for the first time, the story says whose wife Ruth was; keep 'the wife of Mahlon' in the telling. At 4:5 Ruth was 'the wife of the dead'; here she is 'the wife of Mahlon'. The text names only Ruth as Mahlon's wife and never says whose wife Orpah was; Orpah is not in this passage, and the voice does not bring her in. The three names are a list, not an order of events: a telling that names the sons in another order is accepted without comment.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 2.1 ('Here, for the first time, the story says whose wife Ruth was: she is the wife of Mahlon.'); Section 2.2 ('At 4:5 Ruth was \"the wife of the dead\"; here she is \"the wife of Mahlon\".'); Section 2.4 ('for the first time the story says whose wife Ruth was'); Section 3A Scene 1 (B4 'the dead son; here, for the first time, the story says he was Ruth's husband'; 'named by Boaz; Ruth is \"the wife of Mahlon\"'; B9 '\"Ruth the Moabite, the wife of Mahlon\" — the foreigner-marker, and her husband named'; the dead 'Ruth's late husband; in this declaration he is named: Mahlon'); Section 3E Scene 1 ('you are witnesses today that I have bought all that was [[B2-Elimelech]] Elimelech's, and all that was [[B5-Chilion]] Chilion's and [[B4-Mahlon]] Mahlon's'); Section 3F Scene 1 ('Here, for the first time, the story says whose wife Ruth was.'); Section 4 Propositions 2 and 3; carried forward from P01 R10, P02 R5, P06 R4, P11 R7"
    },
    {
      "id": "R2",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "Boaz's declaration at 4:9–10 (P1–P6): what he has bought and why; the purpose stays a purpose; FIG_0002, FIG_0110, CB_0005, CB_0039, CB_0002, CB_0003, CB_0006",
      "note": "REQUIRED keep: Boaz says that he has bought all that was Elimelech's, Chilion's and Mahlon's from Naomi's hand, and that he has bought Ruth to be his wife, to raise up the name of the dead upon his inheritance, so that the name of the dead is not cut off from his kindred and from the gate of his place. 'To raise up the name of the dead upon his inheritance' are Boaz's words of 4:5, said again (FIG_0002). Only 'the dead' is said: the 2:20 phrase 'the living and the dead' is not repeated here, and 2:20 is not brought into 4:10 (FIG_0110; P07 R4, P11 R11). The purpose stays Boaz's stated purpose, not a thing already done. 'Bought' told as 'redeemed' or 'acquired' is accepted without comment (at 4:4 Boaz speaks of buying and of redeeming together). For the voice only, never to be said: do not tell that the name of the dead is now kept or secured; bring in no law the story does not cite (the levirate law, Deuteronomy 25); do not explain what being cut off from the gate means beyond Boaz's words.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 1 ('to raise up the name of the dead upon his inheritance, so that the name of the dead is not cut off from his kindred and from the gate of his place'); Section 2.2 ('to raise up the name of the dead upon his inheritance — the words he spoke at 4:5'); Section 2.4 ('He says again the words of 4:5 — to raise up the name of the dead upon his inheritance — and adds: so that the name of the dead is not cut off from his kindred and from the gate of his place.'); Section 3C Scene 1 (CB_0002 'what Boaz says buying Ruth is for'; CB_0039 'only \"the dead\" is said here'; CB_0003 '\"upon his inheritance\" — where the name of the dead is to be raised up'; CB_0006 '\"from the gate of his place\" — the name of the dead is not to be cut off from it'); Section 5A Concept Bank Flags (CB_0039 'so that the name of the dead is not cut off — only \"the dead\" is said'); Section 5B Figure Flags (FIG_0002 'Boaz's words of 4:5 said again'; FIG_0110 'the dead kept in the reckoning — only \"the dead\" is said here'); Section 4 Propositions 1–6; carried forward from P07 R4, P11 R11"
    },
    {
      "id": "R3",
      "kind": "SIGNIFICANT_ABSENCE",
      "applies_to": "the silences at 4:9–12, carried from P11 R6 (4:1–8): neither Ruth nor Naomi speaks (Scenes 1 and 2); the night at the threshing floor not spoken of, and the name of God not said in Boaz's declaration (Scene 1); FIG_0016 is not flagged here",
      "note": "Silences kept as facts: neither Ruth nor Naomi speaks (4:9–12); at the gate no one speaks of the night at the threshing floor (3:14); no one says the name of God in Boaz's declaration. The voice never says whether Ruth or Naomi is at the gate in 4:9–12; if asked, the text does not say ('this young woman', 4:12, is not read as proof either way). Voice and team do not give the women words or feelings during the scene, make no comment on whether they were asked or whether it was fair, have no one at the gate speak of the night, and put no prayer or 'thank God' in Boaz's declaration.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Significant Absence in Scene 1 ('Neither Ruth nor Naomi speaks. At the gate no one speaks of the night at the threshing floor. No one says the name of God in Boaz's declaration.'); Significant Absence in Scene 2 ('Neither Ruth nor Naomi speaks.'); Section 2.2 ('Neither Ruth nor Naomi speaks.'; 'No one said the name of God in the whole proceeding (4:1–10)'); Section 3A Scene 2 (B9 'Ruth, not named here — \"the woman coming into your house\", \"this young woman\"'); Marcia's SC-0088 ruling D2 (2026-09-28); carried forward from P11 R6"
    },
    {
      "id": "R4",
      "kind": "DISCOURSE_THREAD_ADVANCED",
      "applies_to": "FIG_0014 at 4:11 (P8) and 4:12 (P11) — middle station: the name of God, not said in the proceeding (opened at P11 P13; P11 R6), said by the people in the blessing; the pair closes at P13 (4:14); CB_0009",
      "note": "REQUIRED keep: YHWH named in the blessing, both times — 'may YHWH make the woman coming into your house like Rachel and Leah' (4:11) and 'the seed that YHWH will give you' (4:12). No one said the name of God in the proceeding (4:1–10); the people say it here. The voice tells this as it is told and adds no reason. In the canon record FIG_0014 closes at P13 (4:14); that link stays here and in the pair table only and is not part of P12's telling.",
      "required_in_audit": true,
      "carries_forward_to": "P13_audit",
      "source_in_meaning_map": "Section 2.1 ('the name of God, which no one said in the proceeding, is spoken by the people in the blessing'); Section 2.2 ('No one said the name of God in the whole proceeding (4:1–10); here, in the blessing, the people say it.'); Section 3F Scene 2 ('In the blessing the name of God is said, which no one said in the proceeding.'); Section 3A Scene 2 (B10 'the God of Israel, named here for the first time since the proceeding began'); Section 3E Scene 2 ('May [[B10-YHWH]] YHWH make [[B9-Ruth]] the woman coming into your house like'; 'from the seed that YHWH will give you from this young woman'); Section 5A Concept Bank Flags (CB_0009 'YHWH named in the blessing; no one says the name of God in the proceeding'); Section 5B Figure Flags (FIG_0014 'no one says the name of God in the proceeding; here the people say it in the blessing'); Section 4 Propositions 8 and 11; carried forward from P11 R6; the P13 close is recorded only here and in cross_pericope_pair_verification"
    },
    {
      "id": "R5",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "the blessing at 4:11–12 (P8–P11): three wishes, in order; CB_0008, FIG_0004, CB_0010, FIG_0017, FIG_0170, CB_0049, FIG_0187; carries the blessing form of P02 R10 and the divine-agency discipline of P01 R6 / P02 R1",
      "note": "REQUIRED keep: after 'we are witnesses' all the people at the gate and the elders bless, in this order: may YHWH make the woman coming into your house like Rachel and Leah, who together built the house of Israel; do worthily in Ephrathah and call out a name in Bethlehem; may your house be like the house of Perez, whom Tamar bore to Judah, from the seed that YHWH will give you from this young woman. It is a blessing — wishes, not things told as done. The blessing names Rachel, Leah, Tamar, Judah and Perez and tells no more of them than it says. For the voice only, never to be said: tell no story of Rachel, Leah, Tamar or Judah from outside the book; bring in no law (the levirate law, Deuteronomy 25); do not say that Ruth is like Tamar or that the blessing compares Ruth's story to Tamar's (the blessing likens Boaz's house to the house of Perez); do not say that the blessing makes Ruth an Israelite or ends her being a Moabite; do not say that God has given, or will surely give, the seed; name no one who comes later in the line.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 2 ('say: we are witnesses'; 'who together built the house of Israel. Do worthily in [[PL8-Ephrathah]] Ephrathah and call out a name in [[PL1-Bethlehem-of-Judah]] Bethlehem. And may your house be like the house of [[B27-Perez-and-His-Descendants]] Perez, whom [[B23-Tamar]] Tamar bore to [[B30-Judah]] Judah, from the seed that YHWH will give you from this young woman.'); Section 3F Scene 2 ('Then they bless: may YHWH make the woman coming into Boaz's house like Rachel and Leah; may Boaz do worthily in Ephrathah and call out a name in Bethlehem; may his house be like the house of Perez, from the seed YHWH will give him from this young woman.'); Section 2.2 ('The blessing names Rachel and Leah, the two who built the house of Israel, and the house of Perez, whom Tamar bore to Judah; it tells no more of them than that.'); Section 2.3 ('three wishes'); Significant Absence in Scene 2 ('The seed is asked for, not told as given. The blessing tells no more of Rachel and Leah, of Tamar, Judah and Perez, than it says here.'); Section 3A Scene 2 (B22 'named in the blessing as the two who built the house of Israel'; B27 'the son Tamar bore to Judah'; B23 'named in the blessing as the mother of Perez'; B30 'named in the blessing as the father of Perez'); Section 3C Scene 2 (CB_0008 'the assembly's blessing on Boaz — the woman like Rachel and Leah; do worthily and call out a name; the house like the house of Perez'; CB_0010 'what Rachel and Leah built, in the blessing's words'; CB_0049 '\"the house of Perez, whom Tamar bore to Judah\"'); Section 5B Figure Flags (FIG_0004 'Rachel and Leah, the two who built the house of Israel; the woman coming into Boaz's house likened to them'; FIG_0187 'the blessing spoken by all the people at the gate and the elders'; FIG_0017 'Ephrathah and Bethlehem named side by side'; FIG_0170 'the house of Perez, whom Tamar bore to Judah'); Section 4 Propositions 8–11; carried forward from P02 R10, P01 R6, P02 R1"
    },
    {
      "id": "R6",
      "kind": "SIGNIFICANT_ABSENCE",
      "applies_to": "4:10 (P3) Ruth bought 'to be my wife'; 4:12 (P11) the seed asked for; no child and no taking-home told in this passage; resolves P11 R10 as told",
      "note": "Boaz declares that he has bought Ruth to be his wife (4:10), and the blessing asks for seed from this young woman (4:12). The seed is asked for, not told as given. For the voice only, never to be said: do not tell in this passage that a child is conceived or born, give a child a name, or say that Boaz took Ruth into his house. A telling that Boaz married Ruth, or is marrying her, keeps the meaning of his declaration; accept it without comment. A telling that adds, as something that happened, a wedding, Boaz taking Ruth into his house, or a child in this passage is offered back gently: here Boaz says he has bought her to be his wife.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 1 ('also [[B9-Ruth]] Ruth the Moabite, the wife of Mahlon, I have bought to be my wife'); Section 3A Scene 1 (B9 'the widow Boaz declares he has bought to be his wife'); Section 3A Scene 2 (B9 'the young woman the blessing asks seed from'; B13 'the one who has just declared he has bought Ruth to be his wife'); Significant Absence in Scene 2 ('The seed is asked for, not told as given.'); Section 4 Propositions 3 and 11; carried forward from P11 R10"
    },
    {
      "id": "R7",
      "kind": "NAMING_SHIFT",
      "applies_to": "Ruth at 4:10 (P3) 'Ruth the Moabite, the wife of Mahlon' — FIG_0001 closes here (P01 P10 → P12 P3), CB_0004, carried from P07 R7 and P11 R8; at 4:11 (P8) 'the woman coming into your house'; at 4:12 (P11) 'this young woman'",
      "note": "REQUIRED keep-image: in Boaz's declaration Ruth is 'Ruth the Moabite, the wife of Mahlon'; keep 'the Moabite' in the line. PREFERRED: in the blessing she is not named — 'the woman coming into your house' (4:11), 'this young woman' (4:12); a telling that names her there keeps the meaning and is accepted without comment.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3A Scene 1 (B9 '\"Ruth the Moabite, the wife of Mahlon\" — the foreigner-marker, and her husband named'); Section 3C Scene 1 (CB_0004 'the foreigner-marker, spoken by Boaz in his declaration'); Section 3A Scene 2 (B9 heading 'הָאִשָּׁה הַבָּאָה אֶל־בֵּיתֶךָ … הַנַּעֲרָה הַזֹּאת'; 'Ruth, not named here — \"the woman coming into your house\", \"this young woman\"'); Section 5B Figure Flags (FIG_0001 'the foreigner-marker, in Boaz's declaration: \"Ruth the Moabite, the wife of Mahlon\"'); Section 4 Propositions 3, 8 and 11; carried forward from P07 R7, P11 R8"
    },
    {
      "id": "R8",
      "kind": "CROSS_OCCURRENCE_INTRA_PERICOPE",
      "applies_to": "'you are witnesses today' opening and closing the declaration (4:9, 4:10; P1, P6; FIG_0172) and the answer 'witnesses' (4:11; P7; FIG_0171)",
      "note": "REQUIRED keep: Boaz opens and closes his declaration with 'you are witnesses today', and all the people at the gate and the elders answer with one word, 'witnesses'. 'We are witnesses' is the same answer and is accepted without comment.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3E Scene 1 ('you are witnesses today that I have bought'; '— you are witnesses today.'); Section 3E Scene 2 ('say: we are witnesses'); Section 2.3 ('The assembly's answer is a single word, choral and quick.'); Section 3D Scene 1 (TM_TODAY 'the day of the witnessing — twice named, opening and closing the declaration'; '\"you are witnesses today\", said at the opening and at the close of the declaration'); Section 5B Figure Flags (FIG_0172 'the \"you are witnesses today\" bracket opening and closing the declaration'; FIG_0171 'the people's one-voiced answer'); Section 4 Propositions 1, 6 and 7"
    },
    {
      "id": "R9",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "single keep-images: FIG_0017 (P9), FIG_0004 + CB_0010 (P8), FIG_0170 + CB_0049 (P10), FIG_0003 + CB_0006 (P5), FIG_0005 (P1); the worth-word CB_0032 (P9) is R13",
      "note": "PREFERRED (FIG_0017): Ephrathah and Bethlehem named side by side — do worthily in Ephrathah, call out a name in Bethlehem. REQUIRED (FIG_0004, CB_0010): Rachel and Leah, 'who together built the house of Israel'. REQUIRED (FIG_0170, CB_0049): 'the house of Perez, whom Tamar bore to Judah'. FIG_0003 / CB_0006: 'from the gate of his place' — the gate where the matter is done before everyone is the place the name of the dead is not to be cut off from. FIG_0005: the sandal is drawn off at 4:8 and then Boaz speaks; 4:9 does not mention the sandal, and the voice does not bring it into Boaz's words.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3B Scene 2 (PL8 'named side by side with Bethlehem'; PL1 'where the blessing tells Boaz to call out a name'); Section 3C Scene 2 (CB_0010 'what Rachel and Leah built, in the blessing's words'; CB_0049 '\"the house of Perez, whom Tamar bore to Judah\"'); Section 3B Scene 1 (PL7 'the gate is where the matter is done before everyone; and \"the gate of his place\" is what the name of the dead is not to be cut off from'); Section 3C Scene 1 (CB_0006 '\"from the gate of his place\" — the name of the dead is not to be cut off from it'); Section 2.2 ('After the sandal is drawn off (4:8), Boaz speaks to the elders and all the people.'); Section 5B Figure Flags (FIG_0017 'Ephrathah and Bethlehem named side by side'; FIG_0004 'Rachel and Leah, the two who built the house of Israel'; FIG_0170 'the house of Perez, whom Tamar bore to Judah'; FIG_0003 '\"the gate of his place\": the name of the dead is not to be cut off from it'; FIG_0005 'the sandal drawn off at 4:8; then Boaz speaks to the elders and all the people'); Section 4 Propositions 1, 5, 8, 9 and 10"
    },
    {
      "id": "R10",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "register: whole passage INFORMAL_CASUAL; Scene 1 FORMAL_OFFICIAL and Scene 2 CEREMONIAL at scene level",
      "note": "The whole passage sits in INFORMAL_CASUAL — the narrator's framing of the two speeches. Scene 1, Boaz's declaration (4:9–10), is FORMAL_OFFICIAL at scene level: a legal declaration before witnesses, opened and closed by 'you are witnesses today'. Scene 2, the answer and the blessing (4:11–12), is CEREMONIAL at scene level: a communal blessing in set, weighty form.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 1 Metadata multi-level register tagging ('The whole passage sits in INFORMAL_CASUAL — the narrator's framing of the two speeches'; 'Scene 1, Boaz's declaration (4:9–10), is FORMAL_OFFICIAL at scene level: a legal declaration before witnesses, spoken to the elders and all the people and opened and closed by \"you are witnesses today.\"'; 'Scene 2, the people's and elders' answer and blessing (4:11–12), is CEREMONIAL at scene level: a communal blessing in set, weighty form'); MEANING_COORDINATES register_overrides (scene_level S1 FORMAL_OFFICIAL, S2 CEREMONIAL)"
    },
    {
      "id": "R11",
      "kind": "TEXTUAL_CLARITY_FLAG",
      "applies_to": "minor text points at 4:10 (P3, P5), 4:11 (P7, P8) and 4:12 (P11)",
      "note": "Minor text points. (1) 4:10: 'from his kindred' — the Hebrew says 'from among his brothers', meaning his kin; 'his kindred', 'his brothers', 'his family' are all correct. (2) 4:10: Boaz says he has bought Ruth 'for myself, to be my wife'; 'bought' and 'acquired' are both correct. (3) 4:11: the answer is one Hebrew word, 'witnesses'; 'we are witnesses' is correct. (4) 4:11: the Hebrew says 'may YHWH give the woman … like Rachel and Leah'; 'make' is the plain sense. (5) 4:12: 'the seed that YHWH will give you' stays inside the wish. All of these are accepted without comment.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3E Scene 1 ('from his kindred'; 'I have bought to be my wife'); Section 3E Scene 2 ('say: we are witnesses'; 'May [[B10-YHWH]] YHWH make'; 'from the seed that YHWH will give you from this young woman'); Section 4 Propositions 3, 5, 7, 8 and 11"
    },
    {
      "id": "R12",
      "kind": "DISCOURSE_THREAD_ADVANCED",
      "applies_to": "T2 line-and-redemption and T5 threads at 4:9–12; canon-record forward links (FIG_0014 → P13, FIG_0187 → P13, FIG_0191 → P14, FIG_0016 → P13)",
      "note": "T2 (line and redemption; P05 R8, P07 R12, P09 R14, P11 R14): the purchase is declared before witnesses and Ruth is bought to be Boaz's wife (4:9–10). T5 (canon record; P03 R12): at 4:10 she is 'Ruth the Moabite, the wife of Mahlon', and at 4:11 the blessing likens the woman coming into Boaz's house to Rachel and Leah; the thread's canon name ('incorporation') is not part of P12's telling (R5). Canon-record forward links, recorded only here and in the pair table, never in the map: FIG_0014 closes at P13 4:14 (P12 is its middle station, R4); FIG_0187 opens here and closes at P13 4:14; FIG_0191 opens here and closes at P14 4:18; FIG_0016 closes at P13 4:16 and is not flagged here; the vault notes list FIG_0172 and FIG_0017 as closing at P13, where the P13 map and MEANING_COORDINATES do not flag them.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 2.4 ('This passage makes the purchase public before witnesses.'; 'The blessing likens the woman coming into Boaz's house to Rachel and Leah'); Section 3E Scenes 1 and 2; Section 5B Figure Flags (FIG_0187 'the blessing spoken by all the people at the gate and the elders'; FIG_0191 'Perez named in the blessing'); the forward links are recorded only here and in cross_pericope_pair_verification — the map carries none (SC-0088); carried forward from P03 R12, P05 R8, P07 R12, P09 R14, P11 R14"
    },
    {
      "id": "R13",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "CB_0032 at 4:11 (P9): 'do worthily', the worth-word chayil of 2:1 and 3:11; Marcia's SC-0088 ruling D3 (moved out of R9, 2026-09-28)",
      "note": "CB_0032 (Marcia's SC-0088 ruling D3): 'do worthily' carries the worth-word chayil, the same word as 'a man of worth' (2:1) and 'a woman of worth' (3:11) (P05 R1, R7; P09 R6); the voice keeps the worth-word the same as at 2:1 and 3:11. In a team telling, worth, standing, strength, prosperity or means are correct; accept them without comment. 'Have (many) children' is offered back gently with the map's reading, as at 4:5 (P11 R13). The voice does not teach the variants.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 5A Concept Bank Flags (CB_0032 'the worth-word chayil, as in \"a man of worth\" (2:1) and \"a woman of worth\" (3:11)'); Section 4 Proposition 9; Marcia's SC-0088 ruling D3 (2026-09-28); carried forward from P05 R1, P05 R7, P09 R6"
    }
  ],
  "cross_pericope_pair_verification": {
    "pairs": [
      {
        "fig_id": "FIG_0001",
        "opens_at": "P01 P10 (1:4; book-wide arc)",
        "closes_at": "P12 P3 (4:10 'Ruth the Moabite, the wife of Mahlon')",
        "verification_status": "VERIFIED",
        "note": "Arc closed at this register (R7): the P01 MEANING_COORDINATES flags FIG_0001 at P10 (1:4a), the P07 MC at P13 (2:21), the P11 MC at P9 (4:5a) and the P12 MC at P3 (4:10a), with CB_0004. Registry frontmatter (vault note) confirms opens-at P01 / closes-at P12; its opens-at-proposition reads 'P01:P6', where the P01 MC and every register row put the opening at P01 P10 (1:4a) — alignment listed for the vault half."
      },
      {
        "fig_id": "FIG_0110",
        "opens_at": "P07 P11 (2:20 the living and the dead)",
        "closes_at": "P12 P5 (4:10c); at P11 P10 (4:5) and here only 'the dead' is said",
        "verification_status": "VERIFIED",
        "note": "Pair closed at this register (R2): the P07 MC flags FIG_0110 at P11 (2:20b), the P11 MC at P10 (4:5b) and the P12 MC at P5 (4:10c), with CB_0039. At 4:5 and 4:10 only 'the dead' is said: the 2:20 phrase 'the living and the dead' is not repeated, and 2:20 is not brought into 4:10 (P07 R4, P11 R11). Registry frontmatter (vault note) confirms opens-at P07 / closes-at P12."
      },
      {
        "fig_id": "FIG_0002",
        "opens_at": "P11 P10 (4:5 'to raise up the name of the dead upon his inheritance')",
        "closes_at": "P12 P4 (4:10b, the same words said again)",
        "verification_status": "VERIFIED",
        "note": "Pair closed at this register (R2): the P11 MC flags FIG_0002 at P10 (4:5b), the P12 MC at P4 (4:10b), with CB_0005 and CB_0002; Boaz says the words of 4:5 again. Registry frontmatter (vault note) confirms opens-at P11 / closes-at P12."
      },
      {
        "fig_id": "FIG_0005",
        "opens_at": "P11 P14-P15 (4:7-8 the custom told, the sandal drawn off)",
        "closes_at": "P12 P1 (4:9a Boaz speaks to the elders and all the people) — sequence link only",
        "verification_status": "VERIFIED",
        "note": "Canon-record sequence link (R9): the P11 MC flags FIG_0005 at P14 and P15, the P12 MC at P1 (4:9a). 4:9 does not mention the sandal: the sandal is drawn off at 4:8, and then Boaz speaks. Registry frontmatter (vault note) confirms opens-at P11 / closes-at P12."
      },
      {
        "fig_id": "FIG_0003",
        "opens_at": "P11 P1 (4:1 the gate)",
        "closes_at": "P12 P5 (4:10c 'from the gate of his place')",
        "verification_status": "VERIFIED",
        "note": "Pair closed at this register (R9): the P11 MC flags FIG_0003 at P1 (4:1a) with CB_0006. SC-0088 adds the flag to the P12 map (active-figures and Section 5B) and to the P12 MC at P5 (4:10c), where the text itself joins the gate and the name of the dead ('from the gate of his place'). Registry frontmatter (vault note) confirms opens-at P11 / closes-at P12."
      },
      {
        "fig_id": "FIG_0014",
        "opens_at": "P11 P13 (4:7; no one says the name of God in the proceeding)",
        "closes_at": "P13 P4 (4:14a); middle station at P12 P8 (4:11b, the people say the name in the blessing)",
        "verification_status": "PENDING",
        "note": "Middle station verified here (R4): the P12 MC flags FIG_0014 at P8 (4:11b), and YHWH is named again at 4:12 (P11, CB_0009). The pair closes at P13, where the P13 MC flags FIG_0014 at P4 (4:14a); registry frontmatter (vault note) confirms opens-at P11 / closes-at P13. Full verification lands at P13's register. The P11 row still names 'P12 (4:11)' as the close."
      },
      {
        "fig_id": "FIG_0187",
        "opens_at": "P12 P8 (4:11b the blessing spoken by all the people at the gate and the elders)",
        "closes_at": "P13 P4 (4:14a)",
        "verification_status": "PENDING",
        "note": "Opens here (R12): the P12 MC flags FIG_0187 at P8, the P13 MC at P4 (4:14a); registry frontmatter (vault note) confirms opens-at P12 / closes-at P13. Verification at P13's register. Canon-record link only, not part of P12's telling; the P12 map carries no pointer to P13."
      },
      {
        "fig_id": "FIG_0191",
        "opens_at": "P12 P10 (4:12a the house of Perez)",
        "closes_at": "P14 P1 (4:18a)",
        "verification_status": "PENDING",
        "note": "Opens here (R12): the P12 MC flags FIG_0191 at P10, the P14 MC at P1 (4:18a); registry frontmatter (vault note) confirms opens-at P12 / closes-at P14. Verification at P14's register. Canon-record link only, not part of P12's telling; the P12 map carries no pointer to P14."
      },
      {
        "fig_id": "FIG_0016",
        "opens_at": "P11 P5, P9 (4:3, 4:5)",
        "closes_at": "P13 P8 (4:16a)",
        "verification_status": "PENDING",
        "note": "Not flagged at P12: the P12 map and MC carry no FIG_0016. Under Marcia's SC-0088 ruling D2 the voice never says whether Ruth or Naomi is at the gate in 4:9–12; R3 keeps only that neither speaks. The registry (vault note) lists appears-in [P11, P12, P13]; its P12 entry is not backed by the P12 map or MC — listed for the vault half. Verification at P13's register (the P13 MC flags FIG_0016 at P8, 4:16a)."
      },
      {
        "fig_id": "FIG_0172",
        "opens_at": "P12 P1 (4:9a 'you are witnesses today')",
        "closes_at": "P12 P6 (4:10d 'you are witnesses today')",
        "verification_status": "VERIFIED",
        "note": "Within the pericope (R8): the P12 MC flags FIG_0172 at P1 and P6. The registry (vault note) lists appears-in [P12, P13] and closes-at P13, but the P13 map and MC do not flag FIG_0172 — mismatch listed for P13's register and the vault half."
      },
      {
        "fig_id": "FIG_0017",
        "opens_at": "P12 P9 (4:11c Ephrathah and Bethlehem)",
        "closes_at": "P13 (registry closes-at P13; not flagged there)",
        "verification_status": "PENDING",
        "note": "The P12 MC flags FIG_0017 at P9 (R9). The registry (vault note) lists appears-in [P12, P13] and closes-at P13, but the P13 map and MC do not flag FIG_0017 — for P13's register and the vault half to settle."
      },
      {
        "fig_id": "FIG_0171",
        "opens_at": "P12 P7 (4:11a 'witnesses')",
        "closes_at": "P12 P7 (single occurrence)",
        "verification_status": "VERIFIED",
        "note": "Single occurrence within the pericope (R8): the P12 MC flags FIG_0171 at P7. Registry frontmatter (vault note) confirms opens-at and closes-at P12."
      },
      {
        "fig_id": "FIG_0004",
        "opens_at": "P12 P8 (4:11b Rachel and Leah, who built the house of Israel)",
        "closes_at": "P12 P8 (single occurrence)",
        "verification_status": "VERIFIED",
        "note": "Single occurrence within the pericope (R9): the P12 MC flags FIG_0004 at P8 with CB_0010. Registry frontmatter (vault note) confirms opens-at and closes-at P12."
      },
      {
        "fig_id": "FIG_0170",
        "opens_at": "P12 P10 (4:12a the house of Perez, whom Tamar bore to Judah)",
        "closes_at": "P12 P10 (single occurrence)",
        "verification_status": "VERIFIED",
        "note": "Single occurrence within the pericope (R9): the P12 MC flags FIG_0170 at P10 with CB_0049. Registry frontmatter (vault note) confirms opens-at and closes-at P12."
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
      "WISHES_FOR_HEARER",
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
    "The high-risk register audit was hand-authored from the corrected P12 map under SC-0088: 13 entries (6 do_not_decide: R1, R2, R3, R5, R6, R13 — R1 and R13 since Marcia's word of 2026-09-28 after the session, P12-D6), each traced to the P12 map; the carried-forward items (P01 R6/R10, P02 R1/R5/R10, P03 R12, P05 R1/R7/R8, P06 R4, P07 R4/R7/R12, P09 R6/R14, P11 R6/R7/R8/R10/R11/R13/R14) also cite their source registers (P12-D4). Marcia's merge word on the SC-0088 package is owed.",
    "Propositions stay at meaning-map granularity; multi-event propositions decompose in-slot per the granularity contract.",
    "Forward links out of P12 (FIG_0014's close, FIG_0187 and FIG_0016 to P13; FIG_0191 to P14) live only in this register (R4, R12) and the pair table; the map carries none.",
    "Registry (vault note) data to align in the vault half: FIG_0001 opens-at-proposition 'P01:P6' (the P01 MC and every register row say P01 P10, 1:4a); FIG_0016 appears-in lists P12, whose map and MC do not flag it (D2); FIG_0172 and FIG_0017 list closes-at P13, where the P13 map and MC do not flag them; CB_0032 appears-in [P05, P09] does not yet list P12 (flagged at 4:11 under SC-0088).",
    "Three kinds in this register are not on the approved high_risk_register_kind list — SIGNIFICANT_ABSENCE (R3, R6), TEXTUAL_CLARITY_FLAG (R11) and DISCOURSE_THREAD_ADVANCED (R4, R12); they are used as in SC-0087 and join the register-kind call owed there.",
    "The MEANING_COORDINATES keep ruled SC-0064 values unchanged by SC-0088 and not voiced: arc_element PUBLIC_REDEMPTION_DECLARATION and DEAD_NAME_RAISED, tone_element ANTICIPATORY, communicative_function PLANTS; and the slot names secured_name_of / secured_name_referential_form (P5) and likened_to_matriarchs with blessing_content_kind FRUITFULNESS_LIKE_MATRIARCHS (P8; the text says 'who together built the house of Israel'). They carry readings the map no longer makes; recorded for a future slot-name and value lint pass (like SC-0070).",
    "The map's 'The dead' (4:10) stays an uncoded prose entry in Scene 1 (Mahlon, named in the same sentence); the compiler skeleton still emits a __TODO__ being for it, and the MC no longer carries a second B4 entry for it (SC-0088).",
    "B27's link slug in the map follows its book-level name in _spec/registry/ruth.aliases.json ('Perez and His Descendants'); PL1 keeps the slug Bethlehem-of-Judah. The voice and the Validator see only the code inside the link (SC-0087). Link slugs that still carry a reading stay in canon for human readers, not changed here: CB_0001 Kinsman-Redeemer, CB_0004 Moabite-Outsider, CB_0049 Perez-as-Lineage-Founder, FIG_0005 Shoe-Drawing-Attestation, FIG_0014 Divine-Name-Returns-at-Blessing-After-Legal-Silence, FIG_0187 Blessing-Pair-Elders-and-Women, FIG_0191 Tamar-Perez-Forward-Pair-Completion."
  ]
}
```

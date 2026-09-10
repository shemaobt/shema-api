---
type: "sta-compilation-log"
pericope: "P07"
status: "valid"
pilot: "pilot-2"
---

# P07 — Ruth 2:17-23 — COMPILATION-LOG

```json
{
  "sta_id": "ruth_pericope_07_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Ruth 2:17-23",
  "pericope_id": "P07",
  "pericope_title": "The gleaning brought home and the redeemer named",
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
  "confidence_overall_note": "Judgment half machine-drafted (SC-0063, patch-only contract) and ruled by Marcia axis-by-axis under SC-0064 (§A–§E + arc_element). The graduated MEANING_COORDINATES validates block-clean with 0 convergent drift and is lint-clean. Mechanized log: vocabulary_additions are this pericope's ruled mints; the high-risk register audit was completed and ruled under SC-0085 (see P07-D4).",
  "compilation_decisions": [
    {
      "decision_id": "P07-D1",
      "decision": "Deterministically compiled a MEANING_COORDINATES skeleton from the approved Meaning Map.",
      "description": "Extracted header/classification, scene + entity IDs + presence, verse-ranges, significant_absence, communicative purpose, proposition anchors/scene-links/cross-refs, and Section-5 concept/figure flags. 94 judgment fields left as typed placeholders for Agent 3. No values invented (extract-only)."
    },
    {
      "decision_id": "P07-D2",
      "decision": "Judgment gaps filled by the SC-0063 drafter (Slice 4).",
      "description": "claude-opus-4-8 under the pinned fm-drafter prompt; structured-output fills merged by the patch-only layer. Provenance: _working/P07/drafts/run-2026-06-12T14-42-50-505Z/."
    },
    {
      "decision_id": "P07-D3",
      "decision": "Ruled by Marcia under SC-0064 (the batch ruling), axis by axis.",
      "description": "§A–§E + the five §B axes (action+tone, proposition_kind, role_in_scene_being, scene_kind, arc_element) ruled across 2026-06-12→19; 9 vocabulary addition(s) CONFIRMED for promotion for this pericope (per-axis ruling-logs in _working/P07/P07-SC-0064-*-RULING-LOG.md). Renames/collapses applied to the MEANING_COORDINATES as recorded amendments where ruled."
    },
    {
      "decision_id": "P07-D4",
      "decision": "High-risk register completed and ruled under SC-0085 (the P07–P14 register-completion program).",
      "description": "The 14-entry register was seeded from the June draft (_working/P07/P07-Ruth-2-17-23-COMPILATION-LOG-DRAFT.md; same content on branch p07-wip), re-anchored to the current 16-proposition MEANING_COORDINATES (five anchors renumbered: P10→P11, P11→P12, P12→P13, P14→P15), citations re-anchored to the current map wording, and R3/R13 aligned to the map's held-open phrasing ('YHWH or the man'). Ruled keep-all-14 by Marcia 2026-08-31. cross_ref notes added to the five pair propositions (P6, P11, P12, P13, P15 — the MC carried none; P01/P06 pattern, ruled by Marcia same day). FIG_0113's missing P08 landing ruled: resolve at P08's register. The three Sala gate signals (the real audit, high_risk_register_complete, and the map's sta-status) flip together in this change."
    }
  ],
  "vocabulary_additions": {
    "proposition_kinds": [
      {
        "value": "MEASURED",
        "source": "P07-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T14-42-50-505Z (claude-opus-4-8, req 0c65b09805ebcdef…) · ruled by Marcia 2026-06-13 (proposition_kind Group B)",
        "status": "CONFIRMED",
        "note": "The ephah's quantity result (Ruth 2:17 'measuring — about an ephah'). Kept distinct (Marcia's B-4 keep) from MEASURED_OUT — a measure RESULT, not the act of portioning."
      },
      {
        "value": "THRESHED",
        "source": "P07-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T14-42-50-505Z (claude-opus-4-8, req 0c65b09805ebcdef…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). MM P2: 'beating out | who beat it out? Ruth | beat out what? what she had gleaned' (chavat, CB_0041); no approved proposition_kind covers threshing."
      }
    ],
    "scene_kinds": [
      {
        "value": "GLEANING_SCENE",
        "source": "P07-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T14-42-50-505Z (claude-opus-4-8, req 0c65b09805ebcdef…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM S1: 'Ruth gleans in the field until evening, beats out what she gathered, and it comes to about an ephah' — a narrated gleaning/work scene with no approved scene_kind fit."
      },
      {
        "value": "PROVISION_HOMECOMING_SCENE",
        "source": "P07-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T14-42-50-505Z (claude-opus-4-8, req 0c65b09805ebcdef…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM S2: 'Ruth lifts the grain and comes into the town. Her mother-in-law sees what she gleaned. Then Ruth brings out and gives her what she had left over' — bringing provision home; no approved fit."
      },
      {
        "value": "REDEEMER_RECOGNITION_SCENE",
        "source": "P07-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T14-42-50-505Z (claude-opus-4-8, req 0c65b09805ebcdef…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM S3 3F: 'The turn of the passage: at the name Boaz, Naomi recognizes a redeemer' — a dialogue scene whose spine is the kinship-role recognition; no approved scene_kind fits."
      }
    ],
    "presence_values": [],
    "referential_forms": [],
    "other": [],
    "arc_elements": [
      {
        "value": "PROVISION_BROUGHT_HOME",
        "source": "P07-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T14-42-50-505Z (claude-opus-4-8, req 0c65b09805ebcdef…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM arc: 'The passage moves from the field to home... carries it into town... hands her the food left over' — a day's gleaning brought home as provision; no approved arc token covers this."
      },
      {
        "value": "REDEEMER_RECOGNITION",
        "source": "P07-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T14-42-50-505Z (claude-opus-4-8, req 0c65b09805ebcdef…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM arc: 'Naomi blesses him by YHWH... and tells Ruth the man is near to them, one of their redeemers' — the redeemer-role recognized for the first time in the book; the central turn, with no approved token for it."
      }
    ],
    "action_values": [
      {
        "value": "TOOK",
        "source": "P07-MEANING-COORDINATES P4@2:18a · SC-0063 drafter run-2026-06-12T14-42-50-505Z (claude-opus-4-8, request 0c65b09805ebcdef…) · audit-caught UNDECLARED use (sheet §D) · ruled tick by Marcia 2026-06-12 (SC-0064 §B sitting 1, item 12)",
        "status": "CONFIRMED",
        "note": "Ruth lifts the threshed-barley load (O12) to carry into town (2:18a) — plain physical taking, distinct from approved TOOK_AS_WIFE. The drafter used it without declaring it (contract miss the origin-aware mint audit caught); the value was put to Marcia on its merits and ticked."
      }
    ],
    "role_in_scene_beings": [
      {
        "value": "DECEASED_KIN",
        "source": "P07-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T14-42-50-505Z (claude-opus-4-8, req 0c65b09805ebcdef…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Cluster survivor (Principle A, Marcia 2026-06-13): absorbs DECEASED_KINSMAN + DECEASED_HOUSEHOLD_HEAD + DECEASED_HUSBAND + DECEASED_WHOSE_NAME_RAISED — 5-deceased cluster to one role; who lives in the being-id (B2/B4), kinship in approved HUSBAND/KINSMAN, the levirate act in NAME_PRESERVED. MM S3 3A: 'the dead of the household... those the blessing keeps inside the reach of hesed' — Naomi's dead husband and sons, named only as 'the dead'; no approved role fits."
      }
    ]
  },
  "proposition_kind_slot_sets": [],
  "high_risk_register_audit": [
    {
      "id": "R1",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0104 Abundance Triplet — CLOSES at 2:18 (P07 P6); opened at P06 P15 (2:14)",
      "note": "REQUIRED keep-image. The 'had leftover' third verb of the P06 triplet must land here as the leftover food Ruth gives Naomi, so the abundance-after-famine image is audible across the pericope boundary. Cross-pericope pair closes here.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 5B Figure Flags (FIG_0104 'cross-pericope pair closes here at 2:18; opened at P06 Proposition 15, 2:14 — the had-leftover verb lands as the leftover Ruth gives Naomi'); Section 3C Scene 2 Objects (O10 — the food left over from Ruth's own meal)"
    },
    {
      "id": "R2",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "Living-and-dead formula at v.20 (P11); 'the dead' kept generic, not individuated",
      "note": "The dead are named only as הַמֵּתִים 'the dead,' never as Elimelech, Mahlon, and Chilion. The reconstructor must keep the dead generic in the formula and must not individuate the three men. The formula stretches the LORD's hesed over the dead husband and sons without naming them.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3A Scene 3 (the dead of the household — 'named here only as the dead'); Section 3C Scene 3 (CB_0039 'stretches the hesed of the blessing over the dead husband and sons, not only the two women still alive'); Significant Absence in Scene 3 ('The dead are named only as the dead, not as Elimelech, Mahlon, and Chilion')"
    },
    {
      "id": "R3",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0111 Hesed-Not-Forsaken at 2:20 (P11); antecedent held open (YHWH or the man)",
      "note": "PREFERRED keep-image. Opens here; closes at P09 3:10. The antecedent of 'who has not forsaken his hesed' is grammatically ambiguous — YHWH or the man — and must be kept open. The reconstructor must not resolve the antecedent to either party.",
      "required_in_audit": true,
      "do_not_decide": true,
      "carries_forward_to": "P09_audit",
      "source_in_meaning_map": "Section 3C Scene 3 (CB_0011 cross-ref: 'whether the unforsaken hesed is YHWH's or the man's — is left open, and the blessing's words keep it open'); Section 5A Concept Flags (CB_0011 'the antecedent — YHWH or the man — held open'); Section 5B Figure Flags (FIG_0111)"
    },
    {
      "id": "R4",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0110 Living-and-Dead Formula at 2:20 (P11) — theological hinge",
      "note": "REQUIRED keep-image. Opens here; pairs forward to P11 4:5 and P12 4:10. The paired phrase 'the living and the dead' must render as a deliberate pair so the dead remain in the family's covenantal accounting across the book. Theological hinge of the pericope.",
      "required_in_audit": true,
      "do_not_decide": true,
      "carries_forward_to": "P11_audit",
      "source_in_meaning_map": "Section 3C Scene 3 (CB_0039 Living-and-Dead-Formula); Section 5B Figure Flags (FIG_0110 'pairs forward to P11 4:5 and P12 4:10'); Section 2.4 ('so the dead husband and sons stay inside the family's accounting')"
    },
    {
      "id": "R5",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0112 Close-to-Us at 2:20 (P12); kinship-nearness that creates obligation",
      "note": "PREFERRED keep-image. Opens here; pairs forward to P09 3:12 and P11 4:1-6. The 'near to us' (קָרוֹב לָנוּ) nearness is what creates the redeemer obligation; it must read as genealogical-clan nearness, not mere acquaintance. Sets up the nearer-redeemer tension of chapters 3-4.",
      "required_in_audit": true,
      "do_not_decide": true,
      "carries_forward_to": "P09_audit",
      "source_in_meaning_map": "Section 3C Scene 3 (CB_0001 'near to us is the nearness that carries the duty'); Section 5B Figure Flags (FIG_0112 'pairs forward to P09 3:12 and P11 4:1-6')"
    },
    {
      "id": "R6",
      "kind": "CROSS_PERICOPE_PAIRING_FIRST_OCCURRENCE",
      "applies_to": "FIG_0012 Clinging-Dabaq image-rhyme — CLOSES at 2:23 (P07 P15); opened at P02 P14 (1:14)",
      "note": "PREFERRED keep-image. The davaq root that tagged Ruth's clinging to Naomi at 1:14 returns here as her staying-close to Boaz's young women. If the target language can carry the verbal echo, the same clinging/holding-fast word should render at both 1:14 and 2:23 so the image-rhyme links Ruth's first loyalty to her continued footing under Boaz's protection.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3C Scene 4 (CB_0018 cross-ref: 'the same word as her first holding-fast to Naomi at 1:14 — the loyalty rhymes forward'); Section 5B Figure Flags (FIG_0012 'cross-pericope image-rhyme pair closes here at 2:23; opened at P02 Proposition 14, 1:14')"
    },
    {
      "id": "R7",
      "kind": "NAMING_SHIFT",
      "applies_to": "FIG_0001 Ruth-the-Moabitess narrator-epithet at v.21 (P13)",
      "note": "REQUIRED keep-image. The narrator reasserts 'Ruth the Moabitess' precisely as she repeats Boaz's welcome — the foreigner-marker returns where incorporation is at stake. The epithet must remain visible; it is not decorative repetition but a structural marker of Ruth's outsider standing as her place in the household grows. Book-wide pattern (1:22; 2:6; 2:21; 4:5; 4:10).",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3A Scene 3 ('the narrator names her Ruth the Moabite again as she speaks at v.21'); Section 5B Figure Flags (FIG_0001 'the narrator's foreigner-marker returns at 2:21; the arc runs P01 to P12')"
    },
    {
      "id": "R8",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "CEREMONIAL blessing form at v.20 inside INFORMAL_CASUAL chronicle (P10)",
      "note": "Naomi's v.20 blessing ('Blessed be he of the LORD') carries formal, weighty blessing-shape and names YHWH; declared at moment-level register_overrides at v.20. The blessing must read as ceremonial against the plain home-talk frame, then the talk settles back to intimate register for the redeemer-recognition and counsel.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 1 Metadata multi-level register tagging ('One moment inside that talk lifts to CEREMONIAL: Naomi's blessing at v.20 takes a set, weighty shape and invokes YHWH by name')"
    },
    {
      "id": "R9",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "INTIMATE home-talk register across vv.19-22 (S3 and the v.22 counsel)",
      "note": "The talk between the two women back home shifts from the narrator's plain telling to INTIMATE — a mother-in-law and daughter-in-law alone at day's end, the day's surprise spilling out. Declared at scene-level on S3. The exchange should read as close, private, unguarded against the surrounding chronicle frame.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 1 Metadata multi-level register tagging ('Scene 3 (vv. 19-22) shifts to INTIMATE: a mother-in-law and her daughter-in-law alone at the end of the day, the day's surprise spilling out'); MEANING_COORDINATES register_overrides.scene_level (S3 INTIMATE)"
    },
    {
      "id": "R10",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "Blessing-before-naming sequence at v.19 (P8 then P9)",
      "note": "Naomi blesses 'the man who took notice of you' BEFORE she learns his name. The ordering — blessing, then Ruth naming Boaz — must be preserved; Naomi's blessing is not yet attached to a name. The reconstructor must not move the name earlier or fold the two into one beat.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 4 Proposition 8 ('Whom did she bless? — the man who took notice of Ruth'); Proposition 9 ('What was the man's name? — Boaz'); Section 2.1 ('blesses the man who took notice of her — not yet knowing his name')"
    },
    {
      "id": "R11",
      "kind": "NUMBER_MEASURE_EXACT_RENDERING",
      "applies_to": "About an ephah of barley at v.17 (P3); CB_0040",
      "note": "The day's gleaning comes to about an ephah (≈ a bushel) of barley — a heavy haul for one gleaner in one day, the plain measure of how far Boaz's favor reached. The quantity is approximate ('about an ephah') and must render as a large but inexact measure, not a precise figure.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3C Scene 1 Objects (O12 'a large grain measure (about a bushel)'); Section 4 Proposition 3 ('about an ephah'); Section 5A Concept Flags (CB_0040 active at Proposition 3)"
    },
    {
      "id": "R12",
      "kind": "DISCOURSE_THREAD_OPENED",
      "applies_to": "T2 redeemer/line thread named-in-full at 2:20; T7 harvest-provision RESOLVED at 2:23; T4 hesed-thread lexeme returns at 2:20",
      "note": "Three threads turn here. T2 (line/redemption): the redeemer-role is named aloud for the first time in the book — the characters now share the redeemer-frame the audience has held since 2:1. T7 (harvest-provision): closes/resolves as Ruth gleans to the end of both harvests. T4 (hesed): the hesed lexeme, kept back through the field scenes, returns on Naomi's lips at v.20 (first hesed lexeme in chapter 2). The paired P07 BCD-DELTA draft (vault _working/P07) records the full discourse_thread_events set.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 2.2 Context ('The redeemer-role is named here for the first time in the book'; 'the hesed word last fell at 1:8 … at 2:20 that wish comes back with both halves'); Section 2.4 Communicative Function ('closes the chapter's provision strand'); Section 3C Scene 4 (CB_0026 'the season-frame opened at 1:22 closes here')"
    },
    {
      "id": "R13",
      "kind": "STRUCTURAL_ABSENCE_OF_DIVINE_AGENCY",
      "applies_to": "Held-open hesed antecedent and silence on Ruth's understanding (vv.20-21)",
      "note": "Naomi does not explain what a redeemer is or what it could mean for them; she names the role and stops, and the narrator does not say what Ruth understands by it. Combined with the held-open hesed antecedent, the passage leaves the agency of rescue (YHWH's hesed / the man's role) and Ruth's grasp of it deliberately unstated. The reconstructor must not fill these silences.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Significant Absence in Scene 3 ('Naomi does not explain to Ruth what a redeemer is or what the nearness could mean for them; she names the role and stops, and the narrator does not say what Ruth understands by it')"
    },
    {
      "id": "R14",
      "kind": "STRUCTURAL_ABSENCE_OF_GRIEF",
      "applies_to": "No further Ruth-Boaz contact through the harvest weeks (v.23 close)",
      "note": "The narrator does not say Ruth and Boaz meet again or speak again through all the weeks of harvest; the season passes with no further contact recorded. The quiet must be preserved — the next move waits for Naomi's plan in chapter 3. The reconstructor must not invent intervening encounters.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Significant Absence in Scene 4 ('Through all the weeks of both harvests, the narrator records no further meeting and no further word between Ruth and Boaz. The season passes in silence; the next move waits for Naomi's plan at 3:1')"
    }
  ],
  "cross_pericope_pair_verification": {
    "pairs": [
      {
        "fig_id": "FIG_0104",
        "opens_at": "P06 P15 (2:14 third verb 'had leftover')",
        "closes_at": "P07 P6 (2:18 leftover food Ruth gives Naomi)",
        "verification_status": "VERIFIED",
        "note": "Pair closed at this register. P06 opened it (P06 R10) and recorded the forward link; it lands structurally at P07 P6, and the cross_ref on P6 records the close. Registry frontmatter confirms opens-at P06 / closes-at P07."
      },
      {
        "fig_id": "FIG_0012",
        "opens_at": "P02 P14 (1:14 Ruth clings to Naomi)",
        "closes_at": "P07 P15 (2:23 Ruth stays close to Boaz's young women)",
        "verification_status": "VERIFIED",
        "note": "Image-rhyme pair closed at this register. The davaq root opens at P02 1:14 and closes here at 2:23; the cross_ref on P15 records the close. Registry frontmatter confirms opens-at P02 / closes-at P07."
      },
      {
        "fig_id": "FIG_0111",
        "opens_at": "P07 P11 (2:20 hesed not forsaken)",
        "closes_at": "P09 3:10 ('you have made this last hesed greater than the first')",
        "verification_status": "PENDING",
        "note": "The P09 MEANING_COORDINATES carries FIG_0111; full pair verification lands with P09's high-risk register (this SC-0085 queue). Antecedent held open (YHWH or the man) per R3."
      },
      {
        "fig_id": "FIG_0112",
        "opens_at": "P07 P12 (2:20 close to us)",
        "closes_at": "P09 3:12 ('a redeemer nearer than I'); P11 4:1-6",
        "verification_status": "PENDING",
        "note": "FIG_0112 is present in the P09 and P11 MEANING_COORDINATES; full verification at those registers. Forward-pair anchor for the nearer-redeemer tension."
      },
      {
        "fig_id": "FIG_0110",
        "opens_at": "P07 P11 (2:20 living and dead)",
        "closes_at": "P11 4:5; P12 4:10",
        "verification_status": "PENDING",
        "note": "FIG_0110 is present in the P11 and P12 MEANING_COORDINATES; full verification at those registers. Theological hinge pairing forward to the legal acquisition scenes."
      },
      {
        "fig_id": "FIG_0113",
        "opens_at": "P07 P6 (2:18 leftover after satiety)",
        "closes_at": "P08 (3:1-5)",
        "verification_status": "PENDING",
        "note": "The P08 MEANING_COORDINATES does NOT yet carry FIG_0113 — ruled by Marcia 2026-08-31: resolve at P08's high-risk register (next in this queue). OPTIONAL small abundance-after-famine image."
      },
      {
        "fig_id": "FIG_0001",
        "opens_at": "P01 (1:4 / book-wide foreigner-marker)",
        "closes_at": "P12 4:10 (book-wide pattern: 1:22; 2:6; 2:21; 4:5; 4:10)",
        "verification_status": "PENDING",
        "note": "Book-wide narrator-epithet arc; active here at P07 P13 (2:21). FIG_0001 is present in the P12 MEANING_COORDINATES; the full-arc verification lands at P12's register."
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
      "ASKS_INFORMATION_SEEKING_QUESTION",
      "DIRECTS_HEARER_TO_DO",
      "REPORTS_PRIOR_SPEECH_INSTRUCTION",
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
    "The high-risk register audit was completed under SC-0085 (2026-08-31): 14 entries seeded from the June P07 draft (_working/P07), re-validated against the post-SC-0067/69/70/72/80 artifacts (propositions renumbered to the current 16), and ruled entry-by-entry by Marcia (keep all 14).",
    "Propositions stay at meaning-map granularity; multi-event propositions decompose in-slot per the granularity contract."
  ]
}
```

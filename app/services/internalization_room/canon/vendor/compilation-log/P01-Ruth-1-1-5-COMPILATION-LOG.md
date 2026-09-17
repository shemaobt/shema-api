---
type: "sta-compilation-log"
pericope: "P01"
pericope-title: "The famine, the family's sojourn, and the emptying of the household"
source-meaning-map: [[P01-Ruth-1-1-5]]
source-meaning-coordinates: [[P01-Ruth-1-1-5-MEANING-COORDINATES]]
related-bcd-delta: [[P01-Ruth-1-1-5-BCD-DELTA]]
status: "valid"
pilot: "pilot-2"
---

# P01 — Ruth 1:1–5 — COMPILATION-LOG

This page renders the COMPILATION-LOG JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder. Registry promotions for this pericope live in the paired BCD-DELTA page.

```json
{
  "sta_id": "ruth_pericope_01_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Ruth 1:1-5",
  "pericope_id": "P01",
  "pericope_title": "The famine, the family's sojourn, and the emptying of the household",
  "compiled_at": "2026-05-24",

  "review_status": {
    "meaning_map_status": "APPROVED",
    "sta_compilation_status": "PILOT_2_COMPILATION",
    "community_verified": false,
    "translation_team_verified": false,
    "consultant_review_required": false,
    "production_use": false
  },

  "confidence_overall": "HIGH",
  "confidence_overall_note": "P01 compiles cleanly under the corrected v0.3 three-artifact architecture: one-pass compilation against an authoritative meaning map, with registry promotions extracted to BCD-DELTA. Thirteen propositions across four scenes. Register set to INFORMAL_CASUAL for biblical narrator voice with one moment-level override (COMMUNITY_MEMORY at 1:1a). All proposition kinds, scene kinds, and referential forms drawn from the meaning map. The tishaer image-rhyme pair and the cumulative-loss listing are the two highest-risk items; both are structurally encoded and flagged. Wife-husband pairing withheld per source-text discipline.",

  "compilation_decisions": [
    {
      "decision_id": "P01-D1",
      "decision": "Pericope-level register set to INFORMAL_CASUAL.",
      "description": "Per meaning map Section 1 Metadata: INFORMAL_CASUAL is the unmarked default register for biblical narrator voice in Ruth. The narrator chronicles community memory in relaxed storytelling form. The closed-list value INFORMAL_CASUAL covers this per the Oral Collector taxonomy. CONSULTATIVE was rejected because it specifically denotes asking counsel or guidance, which is not the narrator's voice. The moment-level override at 1:1a (COMMUNITY_MEMORY for the wayhi bimei formula) is declared in pericope_classification.register_overrides."
    },
    {
      "decision_id": "P01-D2",
      "decision": "Wife pairings withheld per source-text discipline.",
      "description": "The source text at 1:4 names Orpah and Ruth but does not pair them with their husbands. The pairing Mahlon-Ruth and Chilion-Orpah is disclosed at 4:10. The MEANING_COORDINATES preserves the withholding structurally: P9 marriage_components use wife_taken: B? rather than naming specific brides. The reconstructor must not infer the pairing at 1:4."
    },
    {
      "decision_id": "P01-D3",
      "decision": "Cross-pericope pair verification deferred for FIG_0013.",
      "description": "FIG_0013 BREAD_HOUSE_IN_FAMINE opens at P01 Proposition P2 and closes at P02 (1:6). P02 is not yet compiled under Pilot 2. Verification deferred pending P02 compilation."
    },
    {
      "decision_id": "P01-D4",
      "decision": "PL_HA_ARETZ flagged for BCD formal registration.",
      "description": "The place reference ha-aretz (the land) appears in the meaning map as plain text (no wiki-link) and in the MEANING_COORDINATES as PL_HA_ARETZ but does not appear in the formal PL-code registry of BCD v0.3. It is used here as a working code pending formal registration. BCD should assign it a formal PL-code at next update."
    },
    {
      "decision_id": "P01-D5",
      "decision": "Methodology metadata separated from story content; registry promotions extracted to BCD-DELTA.",
      "description": "Per Pilot 2 v0.3 architecture: the meaning map and MEANING_COORDINATES contain only story content. This COMPILATION-LOG contains only methodology trace. Registry additions (beings, places, objects, times, discourse-thread events, figure entries, concept-bank flags) are extracted to the paired BCD-DELTA artifact for promotion into the BCD, Figure Registry, and Concept Bank. Team-facing prompts (listen-for items, do-not-add items, discussion items) are Agent 4's responsibility in VERIFICATION-INPUT and do not appear here. The structural representation of source-text discipline (e.g., wife_taken: B? in MEANING_COORDINATES P9) remains in MEANING_COORDINATES because it is story content: the source text does not state the pairing, so the MEANING_COORDINATES does not state it."
    }
  ],

  "vocabulary_additions": {
    "action_values": [
      { "value": "ARRIVED_AT", "source": "first introduced in P01 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "TOOK_AS_WIFE", "source": "first introduced in P01 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "WERE_AT", "source": "first introduced in P01 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" }
    ],
    "proposition_kinds": [
      {
        "value": "ARRIVED_AT",
        "source": "P6 1:2b",
        "status": "CONFIRMED"
      },
      {
        "value": "DIED",
        "source": "P7 1:3",
        "status": "CONFIRMED"
      },
      {
        "value": "DWELT_AT",
        "source": "P11 1:4b",
        "status": "CONFIRMED"
      },
      {
        "value": "FAMINE_OCCURRED",
        "source": "P2 1:1a",
        "status": "CONFIRMED"
      },
      {
        "value": "IDENTIFIED",
        "source": "P5 1:2a",
        "status": "CONFIRMED"
      },
      {
        "value": "MIGRATED",
        "source": "P3 1:1b",
        "status": "CONFIRMED"
      },
      {
        "value": "NAMED",
        "source": "P4 1:2a",
        "status": "CONFIRMED"
      },
      {
        "value": "REMAINED",
        "source": "P8 1:3",
        "status": "CONFIRMED"
      },
      {
        "value": "TIME_ANCHOR_ESTABLISHED",
        "source": "P1 1:1a",
        "status": "CONFIRMED"
      },
      {
        "value": "TOOK",
        "source": "P9 1:4a",
        "status": "CONFIRMED"
      }
    ],
    "scene_kinds": [
      {
        "value": "BEREAVEMENT_SCENE",
        "source": "S2 1:3",
        "status": "CONFIRMED"
      },
      {
        "value": "MARRIAGE_SCENE",
        "source": "S3 1:4",
        "status": "CONFIRMED"
      },
      {
        "value": "OPENING_CHRONICLE_SCENE",
        "source": "S1 1:1-2",
        "status": "CONFIRMED"
      }
    ],
    "presence_values": [
      { "value": "PRESENT_BECOMES_DECEASED", "source": "Elimelech S2; Mahlon and Chilion S4", "status": "CONFIRMED", "note": "Captures within-scene transition from living-and-present to deceased." }
    ],
    "role_in_scene_beings": [
      {
        "value": "CLAN",
        "source": "B6 @S1",
        "status": "CONFIRMED"
      },
      {
        "value": "DAUGHTER_IN_LAW",
        "source": "B8 @S3",
        "status": "CONFIRMED"
      },
      {
        "value": "ERA_REFERENT",
        "source": "B1 @S1",
        "status": "CONFIRMED"
      },
      {
        "value": "HUSBAND",
        "source": "B2 @S1",
        "status": "CONFIRMED"
      },
      {
        "value": "MOTHER_IN_LAW",
        "source": "B3 @S3",
        "status": "CONFIRMED"
      },
      {
        "value": "SON",
        "source": "B4 @S1",
        "status": "CONFIRMED"
      },
      {
        "value": "SOURCE_GROUP",
        "source": "B7 @S3",
        "status": "CONFIRMED"
      },
      {
        "value": "WIDOW",
        "source": "B3 @S2",
        "status": "CONFIRMED"
      },
      {
        "value": "WIFE",
        "source": "B3 @S1",
        "status": "CONFIRMED"
      }
    ],
    "referential_forms": [
      { "value": "UNNAMED_MAN_FROM_BETHLEHEM", "source": "B2 at 1:1b before naming", "status": "CONFIRMED" },
      { "value": "UNNAMED_WIFE_OF_HEAD", "source": "B3 at 1:1b", "status": "CONFIRMED" },
      { "value": "UNNAMED_FIRST_SON", "source": "B4 at 1:1b", "status": "CONFIRMED" },
      { "value": "UNNAMED_SECOND_SON", "source": "B5 at 1:1b", "status": "CONFIRMED" },
      { "value": "HUSBAND_OF_NAOMI", "source": "B2 at 1:3", "status": "CONFIRMED" },
      { "value": "SHE_PRONOMINAL", "source": "B3 at 1:3", "status": "CONFIRMED" },
      { "value": "STRIPPED_TO_HA_ISHAH", "source": "B3 at 1:5", "status": "CONFIRMED" },
      { "value": "HER_HUSBAND", "source": "B2 at 1:5 in cumulative loss listing", "status": "CONFIRMED" }
    ],
    "other": [
      { "category": "PLACE_KIND", "value": "COVENANT_TERRITORY", "source": "PL_HA_ARETZ at 1:1", "status": "CONFIRMED" },
      { "category": "PLACE_KIND", "value": "FOREIGN_REGION", "source": "PL2 fields of Moab", "status": "CONFIRMED" },
      { "category": "TIME_KIND", "value": "HISTORICAL_ERA_ANCHOR", "source": "TM_PERIOD_OF_JUDGES at 1:1", "status": "CONFIRMED" },
      { "category": "OBJECT_KIND", "value": "RESIDUAL_SURVIVAL_VERB", "source": "TH_TISHAER at 1:3 and 1:5", "status": "CONFIRMED" },
      { "category": "OBJECT_KIND", "value": "NAMING_DOWN_REFERENTIAL_FORM", "source": "TH_HA_ISHAH at 1:5", "status": "CONFIRMED" },
      { "category": "OBJECT_KIND", "value": "TENDER_CHILD_REFERENTIAL_FORM", "source": "TH_YELADIM at 1:5", "status": "CONFIRMED" },
      { "category": "OBJECT_KIND", "value": "CHRONICLE_OPENING_FORMULA", "source": "TH_WAYHI_BIMEI_FORMULA at 1:1", "status": "CONFIRMED" },
      { "category": "OBJECT_KIND", "value": "RELATIONAL_REFRAMING_PHRASE", "source": "TH_HUSBAND_OF_NAOMI_FRAMING at 1:3", "status": "CONFIRMED" },
      { "category": "OBJECT_KIND", "value": "INITIATIVE_MARRIAGE_PHRASING", "source": "TH_TOOK_WIVES_FOR_THEMSELVES_PHRASING at 1:4", "status": "CONFIRMED" },
      { "category": "OBJECT_KIND", "value": "CLAN_IDENTIFIER_PHRASE", "source": "TH_EPHRATHITE_CLAN_IDENTIFIER at 1:2", "status": "CONFIRMED" }
    ]
  },

  "proposition_kind_slot_sets": [
    {
      "proposition_kind": "DIED",
      "slot_set": ["deceased", "referential_form_at_verse", "where", "agent_named", "totality_marker"],
      "status": "CONFIRMED",
      "occurrences_in_pericope": ["P7", "P12"],
      "note": "Single-death case (P7) uses deceased as a single B-code. Paired-death case (P12) uses deceased as an array. totality_marker slot present only when the text marks the totality explicitly."
    },
    {
      "proposition_kind": "LEFT_AS_RESIDUAL",
      "slot_set": ["residual", "referential_form_at_verse", "remaining_with", "residual_verb_form", "naming_down_form", "bereft_of_listing", "listing_order_form", "compression_form"],
      "component_record_shape": {
        "loss_target": "required - B-code or array",
        "referential_form": "conditional - present when the narrator uses a marked form",
        "list_position": "required - FIRST | SECOND | THIRD",
        "speech_act": "required - always STATES_AS_TRUE for narrator chronicle"
      },
      "status": "CONFIRMED",
      "occurrences_in_pericope": ["P8", "P13"],
      "note": "Simple residual case (P8) uses only residual, remaining_with, residual_verb_form. Cumulative-loss case (P13) additionally uses naming_down_form, bereft_of_listing, listing_order_form, compression_form."
    },
    {
      "proposition_kind": "MIGRATED",
      "slot_set": ["household_head", "accompanying_household", "origin", "destination", "purpose", "departure_intent_marker"],
      "status": "CONFIRMED",
      "occurrences_in_pericope": ["P3"]
    },
    {
      "proposition_kind": "NAMED",
      "slot_set": ["naming_order", "naming_components"],
      "component_record_shape": {
        "named_party": "required - B-code",
        "given_name": "required - string",
        "role_in_household": "conditional",
        "speech_act": "required - STATES_AS_TRUE"
      },
      "status": "CONFIRMED",
      "occurrences_in_pericope": ["P4", "P10"]
    },
    {
      "proposition_kind": "TOOK_AS_WIFE",
      "slot_set": ["marriage_components", "marriage_phrasing_form", "where"],
      "component_record_shape": {
        "action": "required - TOOK_AS_WIFE",
        "taker": "required - B-code",
        "wife_taken": "required - B-code or B? when withheld per source discipline",
        "wife_origin_pool": "required - B-code",
        "for_self_marker": "conditional",
        "speech_act": "required - STATES_AS_TRUE"
      },
      "status": "CONFIRMED",
      "occurrences_in_pericope": ["P9"],
      "note": "wife_taken uses B? when the source text does not disclose the pairing. Do not infer pairings not stated in the text."
    }
  ],

  "high_risk_register_audit": [
    {
      "id": "R1",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "FIG_0007 NARRATOR_FRAME_FROM_LATER_TIME at 1:1 (P1)",
      "note": "Chronicle-opening formula wayhi bimei. PREFERRED keep-image. If the target tradition has a parallel chronicle-opening convention, prefer it over literal translation.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 5B Figure Flags; Section 3C Scene 1 Objects"
    },
    {
      "id": "R2",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0013 BREAD_HOUSE_IN_FAMINE at 1:1 (P2)",
      "note": "PREFERRED keep-image. Place-name irony cannot survive most target languages without paratext. Cross-pericope pair closes at P02. Acceptable ceiling if paratext is unavailable.",
      "required_in_audit": true,
      "carries_forward_to": "P02_audit",
      "source_in_meaning_map": "Section 5B Figure Flags"
    },
    {
      "id": "R3",
      "kind": "CROSS_OCCURRENCE_INTRA_PERICOPE",
      "applies_to": "FIG_0052 TISHAER_RESIDUAL_RHYME at 1:3 (P8) and 1:5 (P13)",
      "note": "REQUIRED keep-image. Both occurrences must render the same residual-survival verb frame so the rhyme is audible. The first occurrence (1:3) establishes the frame; the second (1:5) completes it. Do not vary the rendering between the two.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 5B Figure Flags; Section 3C Scene 2 and Scene 4 Objects"
    },
    {
      "id": "R4",
      "kind": "NAMING_SHIFT",
      "applies_to": "B3 Naomi stripped to ha-ishah at 1:5 (P13)",
      "note": "Narrator strips Naomi to 'the woman' at the moment of complete bereavement. The shift is a structural defamiliarization marker. Full name is restored at 1:6. If the target language's natural reference would use a name here, an alternative tonal marker for the reduction must be found.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3A Scene 4 (B3 reference form); Section 3C Scene 4 Objects (TH_HA_ISHAH_STRIPPED_REFERENCE)"
    },
    {
      "id": "R5",
      "kind": "CUMULATIVE_LOSS_LISTING_REQUIRED_FORM",
      "applies_to": "TH_CUMULATIVE_LOSS_LISTING at 1:5 (P13)",
      "note": "REQUIRED keep-image. Single-phrase compression must survive. The reverse-natural-order (children before husband) must be preserved. Do not split into separate sentences if the target language permits the single-phrase form.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3C Scene 4 Objects (TH_CUMULATIVE_LOSS_LISTING)"
    },
    {
      "id": "R6",
      "kind": "STRUCTURAL_ABSENCE_OF_DIVINE_AGENCY",
      "applies_to": "agent_named NONE on P2 (famine), P7 (Elimelech's death), P12 (sons' deaths)",
      "note": "YHWH is not named as agent of any event in P01. The withholding is structural and intentional; it contrasts with the first divine action at 1:6 in P02. Reconstructor must not assign divine causation.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Significant Absence in Scenes 1, 2, 4; T6_yhwh_at_work thread state STRUCTURALLY_ABSENT"
    },
    {
      "id": "R7",
      "kind": "STRUCTURAL_ABSENCE_OF_GRIEF",
      "applies_to": "All three deaths at 1:3 and 1:5",
      "note": "The narrator reports each death in a single brief clause. No grief, no mourning ritual, no successor is named. The compression carries the weight. Reconstruction must not add grief language not present in the source.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Significant Absence in Scenes 2 and 4"
    },
    {
      "id": "R8",
      "kind": "NUMBER_MEASURE_EXACT_RENDERING",
      "applies_to": "two sons (1:1, 1:3, 1:5); both of them (1:5); about ten years (1:4)",
      "note": "Exact numbers and approximate measures must survive reconstruction without paraphrase. The approximate marker 'about ten years' must render the approximation explicitly.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3C Scene 3 Objects (TH_TEN_YEARS_APPROXIMATELY); Section 3C Scene 4 Objects (TH_BOTH_OF_THEM)"
    },
    {
      "id": "R9",
      "kind": "NAMING_SEQUENCE_PRESERVATION",
      "applies_to": "P4 (family naming at 1:2) and P10 (brides naming at 1:4)",
      "note": "The parallel naming-pair structure at 1:2 and 1:4 plants every name the book will reactivate. The parallelism between the two namings is part of the chronicle pattern. Both naming sequences must be complete.",
      "required_in_audit": true,
      "source_in_meaning_map": "Propositions 3 and 6 (parallel naming structure)"
    },
    {
      "id": "R10",
      "kind": "WITHHELD_PAIRING_PER_SOURCE_DISCIPLINE",
      "applies_to": "Mahlon-Ruth and Chilion-Orpah pairings at 1:4 (P9)",
      "note": "The source text does not pair the wives with their husbands at 1:4. Pairing is disclosed at 4:10. The MEANING_COORDINATES preserves the withholding via wife_taken: B? in P9 marriage_components. Reconstructor must not infer or state the pairing here.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 4 Proposition 6 (brides named without husband-pairing in the text)"
    },
    {
      "id": "R11",
      "kind": "TENDER_CHILD_REFERENCE_PRESERVATION",
      "applies_to": "TH_YELADIM_TENDER_CHILD_FORM at 1:5 (P13)",
      "note": "The narrator uses yeladim (boys, tender child-form) rather than banim (sons). The shift reframes the loss as the loss of children, not adult heirs. If the target language permits the distinction, preserve the tender-child framing.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3C Scene 4 Objects (TH_YELADIM_TENDER_CHILD_FORM)"
    },
    {
      "id": "R12",
      "kind": "DISCOURSE_THREAD_OPENED",
      "applies_to": "T1 and T2 OPENED_AND_THREATENED at 1:1-5; T5 OPENED at 1:4",
      "note": "Three discourse threads are opened by this pericope. T1 and T2 are immediately threatened by the deaths; T5 is opened by the naming of Moabite wives. The opening-and-threatening pattern is the initial state for the book.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 6 Discourse Threads Advanced"
    },
    {
      "id": "R13",
      "kind": "PROVIDENTIAL_ANSWER_ANTICIPATED",
      "applies_to": "FIG_0013 BREAD_HOUSE_IN_FAMINE paired with 1:6",
      "note": "The irony opened at 1:1 is answered at 1:6 when YHWH visits his people to give them bread. Cross-pericope audit anchor.",
      "required_in_audit": false,
      "carries_forward_to": "P02_audit",
      "source_in_meaning_map": "Section 5B Figure Flags (FIG_0013 cross-pericope pairing)"
    },
    {
      "id": "R14",
      "kind": "STRUCTURAL_CONTRAST",
      "applies_to": "Bethlehem/Moab; fullness/emptiness; intended sojourn/ten-year stay",
      "note": "Three structural contrasts opened by the pericope. Reconstruction must allow each contrast to remain visible without editorial addition.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 2.1 Prose Arc; Section 3C Scene 1 (CB_0030 sojourning); Section 3C Scene 3 (TH_TEN_YEARS_APPROXIMATELY)"
    },
    {
      "id": "R15",
      "kind": "STRUCTURAL_ABSENCE_OF_OFFSPRING",
      "applies_to": "Ten years of childless marriage (Scene 3)",
      "note": "No children are born to either marriage during the ten years of dwelling. The narrator records the duration without naming offspring. This structural absence anticipates the inheritance crisis that T2 will track through the book.",
      "required_in_audit": true,
      "source_in_meaning_map": "Significant Absence in Scene 3"
    }
  ],

  "cross_pericope_pair_verification": {
    "pairs": [
      {
        "fig_id": "FIG_0013",
        "opens_at": "P2",
        "closes_at": "P02 (1:6); reactivated at P04 (1:22)",
        "verification_status": "DEFERRED",
        "note": "P02 not yet compiled under Pilot 2. Verification deferred pending P02 compilation."
      },
      {
        "fig_id": "FIG_0001",
        "opens_at": "P10",
        "closes_at": "Recurs at P04 P05 P07 P11 P12",
        "verification_status": "DEFERRED",
        "note": "Book-wide recurrence pattern. Verification deferred pending later pericope compilation."
      },
      {
        "fig_id": "FIG_0052",
        "opens_at": "P8",
        "closes_at": "P13 (within-pericope pair)",
        "verification_status": "VERIFIED",
        "note": "Within-pericope image-rhyme pair verified at P01 compilation."
      }
    ]
  },

  "validation_checklist": {
    "meaning_map_contains_only_story_content": true,
    "meaning_coordinates_contains_only_inference_signal": true,
    "every_proposition_has_cb_flags_and_figure_flags": true,
    "every_being_in_propositions_declared_in_scenes": true,
    "every_place_in_propositions_declared_in_scenes": true,
    "every_object_in_propositions_declared_in_scenes": true,
    "every_time_in_propositions_declared_in_scenes": true,
    "no_grammatical_frame_slot_names": true,
    "speech_act_present_on_all_component_records": true,
    "speech_act_values_used": ["STATES_AS_TRUE"],
    "negation_not_double_encoded": "N/A - no negations in P01",
    "cross_pericope_cross_refs_present_on_correct_propositions": true,
    "empty_slot_rule_applied_to_times_in_scene": true,
    "discourse_threads_tracked_in_audit_only": true,
    "known_limitations_tracked_in_audit_only": true,
    "high_risk_register_complete": true,
    "every_high_risk_entry_traces_to_meaning_map": true,
    "significant_absences_traced_to_meaning_map": true,
    "no_content_added_beyond_meaning_map": true,
    "wife_pairing_withholding_enforced": true,
    "b_codes_match_bcd_version": "All B-codes verified against ruth_pilot_BCD_v0_3",
    "registry_additions_extracted_to_bcd_delta": true,
    "no_reviewer_facing_prompts_in_compilation_log": true
  },

  "known_limitations": [
    "PL_HA_ARETZ used as a working code pending formal PL-code assignment in BCD v0.4.",
    "Cross-pericope pair verification for FIG_0013 and FIG_0001 deferred pending P02 and later pericope compilations.",
    "Wife pairings at 1:4 deliberately withheld per source-text discipline. Pairing disclosure carried forward to P13 audit at 4:10.",
    "Name meanings (Elimelech, Mahlon, Chilion, Naomi) held at FIG keep-image UNKNOWN pending target tradition assessment.",
    "community_verified and translation_team_verified remain false; this is a pilot compilation."
  ]
}
```

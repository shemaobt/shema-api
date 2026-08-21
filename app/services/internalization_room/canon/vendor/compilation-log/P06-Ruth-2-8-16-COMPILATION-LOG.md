---
type: "sta-compilation-log"
pericope: "P06"
pericope-title: "Boaz speaks to Ruth in the field: instructions, blessing, meal, and harvester protocol"
source-meaning-map: [[P06-Ruth-2-8-16]]
source-meaning-coordinates: [[P06-Ruth-2-8-16-MEANING-COORDINATES]]
related-bcd-delta: [[P06-Ruth-2-8-16-BCD-DELTA]]
status: "valid"
pilot: "pilot-2"
---

# P06 — Ruth 2:8–16 — COMPILATION-LOG

This page renders the COMPILATION-LOG JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder. Registry promotions for this pericope live in the paired BCD-DELTA page.

```json
{
  "sta_id": "ruth_pericope_06_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Ruth 2:8-16",
  "pericope_id": "P06",
  "pericope_title": "Boaz speaks to Ruth in the field: instructions, blessing, meal, and harvester protocol",
  "compiled_at": "2026-05-24",
  "review_status": {
    "meaning_map_status": "APPROVED",
    "sta_compilation_status": "PILOT_2_COMPILATION_REVISED_POST_GATE_F",
    "community_verified": false,
    "translation_team_verified": false,
    "consultant_review_required": false,
    "production_use": false
  },
  "confidence_overall": "HIGH",
  "confidence_overall_note": "P06 compiles cleanly under the corrected v2.0 architecture. Nineteen propositions across four scenes. Pericope register INFORMAL_CASUAL with one scene-level INTIMATE override (S2) and one moment-level CEREMONIAL override (v.12 blessing). Wife-pairing withheld per P01-D2. CB_0004, CB_0011, FIG_0001 correctly do not fire here. Three-prohibition cluster distributed across P3, P17, P19. FIG_0011 wing-of-refuge pair opens at P9; FIG_0132 shifchah-amah pair opens at P11. Revised per Gate F reviewer feedback: removed moment_level_register_override from P9, replaced act_recipient with loyalty_act_toward_party in P7, replaced beneficiary with for_party_to_glean in P18, removed PL_LAND_OF_JUDAH from S2 places.",
  "compilation_decisions": [
    {
      "decision_id": "P06-D1",
      "decision": "Wife-pairing withheld at v.11 husband reference.",
      "description": "At v.11 Boaz says 'after the death of your husband' without naming which son. The Mahlon-Ruth / Chilion-Orpah pairing is withheld in narrator-readable text until 4:10. P7 recital_components uses after_whose_death: B? rather than B4. Carries P01-D2 forward into Boaz's recital."
    },
    {
      "decision_id": "P06-D2",
      "decision": "CB_0004 Moabite-Outsider does not fire in P06.",
      "description": "The Moabite ethnic epithet is not lexically present in vv. 8-16. Ruth self-names as nokhriyah (CB_0038 fires at P6); Boaz characterizes her origin as 'the land of your birth' without naming Moab. CB_0004 next fires at P07 v.21 when the narrator reasserts 'Ruth the Moabitess.'"
    },
    {
      "decision_id": "P06-D3",
      "decision": "CB_0011 Hesed does not fire in P06.",
      "description": "The hesed lexeme is not present in vv. 8-16. Boaz recites Ruth's loyalty in narrative substance at v.11, but the lexeme first appears at 2:20 (P07). Flagging CB_0011 here would record a lexical occurrence that does not exist."
    },
    {
      "decision_id": "P06-D4",
      "decision": "Boaz's 'land of your birth' encoded as withheld, not as PL2.",
      "description": "At v.11 Boaz says erets moladtekh, not 'Moab.' P8 encodes the origin via TH_LAND_OF_BIRTH_UNNAMED_FORM and moab_naming_status: WITHHELD_IN_BOAZ_SPEECH. The destination people at v.11c is encoded as 'people previously unknown' via TH_TEMOL_SHILSHOM_BEFORE_NOW_IDIOM, not as PL_LAND_OF_JUDAH or any named land. The audience knows the referents; the surface text holds both off."
    },
    {
      "decision_id": "P06-D5",
      "decision": "FIG_0132 shifchah-amah pair opens at first half (v.13 shifchah).",
      "description": "FIG_0132 is encoded as opening at P11 with Ruth's shifchah self-designation. The second half (amah at 3:9) closes the pair at P09. Both halves carry the same figure code per the canonical convention; opening-at-first-half is documented here for clarity since the pair-closing figure (parallel to FIG_0131 for wings) is not pre-registered."
    },
    {
      "decision_id": "P06-D6",
      "decision": "Three-prohibition cluster distributed across three propositions.",
      "description": "FIG_0105 (touch, v.9 reported prior command) at P3; FIG_0106 (shame, v.15) at P17; FIG_0107 (rebuke, v.16) at P19. The cluster is intentionally distributed in the source text — touch is reported prior speech inside instruction, shame is bundled with permission-to-glean, rebuke is bundled with leave-them. Collapsing into one figure entry would erase that structural distribution."
    },
    {
      "decision_id": "P06-D7",
      "decision": "FIG_0104 abundance triplet encoded as three component records.",
      "description": "P15 encodes the three verbs (ate / was satisfied / had leftover) as three triplet_components. The third verb (had leftover) is structurally available for the forward link to P07 v.18 (Ruth carrying leftover to Naomi). Required keep-image."
    },
    {
      "decision_id": "P06-D8",
      "decision": "FIG_0001 Ruth-the-Moabitess does not fire in P06.",
      "description": "The narrator-epithet 'Ruth the Moabitess' is withheld through this pericope; Ruth's ethnicity surfaces only via her own nokhriyah self-designation at v.10 (CB_0038, not FIG_0001). The narrator-voice epithet returns at P07 v.21."
    },
    {
      "decision_id": "P06-D9",
      "decision": "v.12 CEREMONIAL declared at pericope_classification only.",
      "description": "Boaz's blessing at v.12 is declared as CEREMONIAL via pericope_classification.register_overrides.moment_level. P9 itself does not carry a moment_level_register_override field, matching canonical P01 (no proposition in P01 carries moment_level_register_override). The pericope-level declaration is sufficient."
    },
    {
      "decision_id": "P06-D10",
      "decision": "Slot naming uses event-participant terminology only.",
      "description": "All slot names use event-participant-and-modifier terminology (loyalty_act_toward_party, for_party_to_glean, given_party, addressee, etc.). No grammatical-frame slot names (actor, agent, patient, theme, recipient, beneficiary, experiencer, instrument) appear. Revised post-Gate F: replaced act_recipient with loyalty_act_toward_party in P7; replaced beneficiary with for_party_to_glean in P18."
    },
    {
      "decision_id": "P06-D11",
      "decision": "Address-form encoding at component-record level.",
      "description": "P1 carries address_form MY_DAUGHTER for Boaz to Ruth at v.8 (a non-kin elder addressing a young foreigner). P10 carries address_form MY_LORD for Ruth to Boaz at v.13 (deferential). P6 and P10 also carry name_known_status: NAME_NOT_YET_KNOWN_TO_RUTH to record that Ruth still does not know Boaz's name."
    }
  ],
  "vocabulary_additions": {
    "action_values": [
      { "value": "ATE", "source": "first introduced in P06 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "HAD_LEFTOVER", "source": "first introduced in P06 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "PERMITTED", "source": "first introduced in P06 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "WAS_SATISFIED", "source": "first introduced in P06 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" }
    ],
    "proposition_kinds": [
      {
        "value": "ATE",
        "source": "P15 2:14d",
        "status": "CONFIRMED"
      },
      {
        "value": "DECLARED",
        "source": "P7 2:11a",
        "status": "CONFIRMED"
      },
      {
        "value": "HANDED",
        "source": "P14 2:14c",
        "status": "CONFIRMED"
      },
      {
        "value": "INSTRUCTION",
        "source": "P1 2:8",
        "status": "CONFIRMED"
      },
      {
        "value": "PROSTRATED",
        "source": "P5 2:10a",
        "status": "CONFIRMED"
      },
      {
        "value": "ROSE",
        "source": "P16 2:15a",
        "status": "CONFIRMED"
      },
      {
        "value": "SAT",
        "source": "P13 2:14b",
        "status": "CONFIRMED"
      }
    ],
    "scene_kinds": [
      {
        "value": "BLESSING_SCENE",
        "source": "S2 2:10-13",
        "status": "CONFIRMED"
      },
      {
        "value": "INSTRUCTION_SCENE",
        "source": "S1 2:8-9",
        "status": "CONFIRMED"
      },
      {
        "value": "MEAL_SCENE",
        "source": "S3 2:14",
        "status": "CONFIRMED"
      }
    ],
    "presence_values": [
      {
        "value": "PRESENT_COLLECTIVE",
        "source": "P06 level_2 presence — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      }
    ],
    "role_in_scene_beings": [
      {
        "value": "FEMALE_WORKERS",
        "source": "B16 @S1",
        "status": "CONFIRMED"
      },
      {
        "value": "MALE_WORKERS",
        "source": "B17 @S1",
        "status": "CONFIRMED"
      }
    ],
    "referential_forms": [],
    "other": [],
    "arc_elements": [
      {
        "value": "BLESSING_INVOCATION",
        "source": "P06 level_1.arc_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      },
      {
        "value": "HARVESTER_PROTOCOL_EXTENSION",
        "source": "P06 level_1.arc_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      },
      {
        "value": "MEAL_INCLUSION",
        "source": "P06 level_1.arc_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      },
      {
        "value": "PROTECTIVE_INSTRUCTION",
        "source": "P06 level_1.arc_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      },
      {
        "value": "RECOGNITION_EXCHANGE",
        "source": "P06 level_1.arc_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      }
    ],
    "context_elements": [
      {
        "value": "DIVINE_CONTEXT",
        "source": "P06 level_1.context_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      },
      {
        "value": "PRIOR_ACTION_CONTEXT",
        "source": "P06 level_1.context_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      }
    ],
    "tone_elements": [
      { "value": "WARM", "source": "P06 level_1.tone_elements convergent value (Gate-F 2026-05-30)", "status": "CONFIRMED" }
    ],
    "pace_elements": [],
    "communicative_function_elements": []
  },
  "proposition_kind_slot_sets": [
    {
      "proposition_kind": "SPOKE_PROTECTIVE_INSTRUCTION",
      "slot_set": [
        "speaker",
        "addressee",
        "address_form",
        "opening_form",
        "instruction_components"
      ],
      "component_record_shape": {
        "action": "required",
        "list_position": "required",
        "speech_act": "required — DIRECTS_HEARER_TO_DO or DIRECTS_HEARER_NOT_TO_DO"
      },
      "status": "CONFIRMED",
      "occurrences_in_pericope": [
        "P1",
        "P2",
        "P4"
      ]
    },
    {
      "proposition_kind": "REPORTED_OWN_PRIOR_PROHIBITION",
      "slot_set": [
        "speaker",
        "addressee",
        "prior_command_giver",
        "prior_command_addressees",
        "prior_prohibition_target_party",
        "prior_prohibited_action",
        "report_form"
      ],
      "status": "CONFIRMED",
      "occurrences_in_pericope": [
        "P3"
      ],
      "note": "Reported speech; speech_act is REPORTS_OWN_PRIOR_PROHIBITION; the present speech-act is the report, not the prior prohibition itself."
    },
    {
      "proposition_kind": "ASKED_RECOGNITION_QUESTION_AND_SELF_NAMED_AS_FOREIGNER",
      "slot_set": [
        "speaker",
        "addressee",
        "name_known_status",
        "exchange_components"
      ],
      "status": "CONFIRMED",
      "occurrences_in_pericope": [
        "P6"
      ]
    },
    {
      "proposition_kind": "ANSWERED_WITH_FULL_KNOWLEDGE_RECITAL",
      "slot_set": [
        "speaker",
        "addressee",
        "full_knowledge_doubling_form",
        "recital_components"
      ],
      "component_record_shape": {
        "action": "required",
        "loyalty_act_toward_party": "B-code of party toward whom Ruth's loyalty was directed",
        "after_whose_death": "B-code or B? when pairing withheld",
        "speech_act": "required"
      },
      "status": "CONFIRMED",
      "occurrences_in_pericope": [
        "P7"
      ]
    },
    {
      "proposition_kind": "RECITED_RUTH_LEAVING_AND_COMING",
      "slot_set": [
        "speaker",
        "addressee",
        "recital_components"
      ],
      "status": "CONFIRMED",
      "occurrences_in_pericope": [
        "P8"
      ]
    },
    {
      "proposition_kind": "PRONOUNCED_FORMAL_BLESSING_UNDER_WINGS_OF_REFUGE",
      "slot_set": [
        "blesser",
        "blessing_recipient",
        "invoked_divine_agent",
        "invoked_divine_agent_referential_form",
        "blessing_form",
        "blessing_components"
      ],
      "status": "CONFIRMED",
      "occurrences_in_pericope": [
        "P9"
      ]
    },
    {
      "proposition_kind": "RESPONDED_WITH_FAVOR_WISH",
      "slot_set": [
        "speaker",
        "addressee",
        "address_form",
        "address_form_object",
        "name_known_status",
        "wish_form",
        "wished_state"
      ],
      "status": "CONFIRMED",
      "occurrences_in_pericope": [
        "P10"
      ]
    },
    {
      "proposition_kind": "DESCRIBED_BOAZ_EFFECT_AND_LOWER_SELF_NAMED",
      "slot_set": [
        "speaker",
        "addressee",
        "self_designation_form",
        "response_components"
      ],
      "status": "CONFIRMED",
      "occurrences_in_pericope": [
        "P11"
      ]
    },
    {
      "proposition_kind": "INVITED_TO_MEAL",
      "slot_set": [
        "speaker",
        "addressee",
        "when",
        "invitation_components"
      ],
      "status": "CONFIRMED",
      "occurrences_in_pericope": [
        "P12"
      ]
    },
    {
      "proposition_kind": "ATE_WAS_SATISFIED_AND_HAD_LEFTOVER",
      "slot_set": [
        "eater",
        "abundance_triplet_form",
        "triplet_components"
      ],
      "component_record_shape": {
        "action": "required — ATE / WAS_SATISFIED / HAD_LEFTOVER",
        "list_position": "required — FIRST / SECOND / THIRD",
        "speech_act": "required — STATES_AS_TRUE"
      },
      "status": "CONFIRMED",
      "occurrences_in_pericope": [
        "P15"
      ]
    },
    {
      "proposition_kind": "COMMANDED_HARVESTERS_PERMISSION_AND_SHAME_PROHIBITION",
      "slot_set": [
        "speaker",
        "addressees",
        "about_party",
        "command_components"
      ],
      "status": "CONFIRMED",
      "occurrences_in_pericope": [
        "P17"
      ]
    },
    {
      "proposition_kind": "COMMANDED_DELIBERATE_PULLING_FROM_BUNDLES",
      "slot_set": [
        "speaker",
        "addressees",
        "for_party_to_glean",
        "material_referent",
        "manner",
        "deliberate_pulling_doubling_form"
      ],
      "status": "CONFIRMED",
      "occurrences_in_pericope": [
        "P18"
      ]
    },
    {
      "proposition_kind": "COMMANDED_LEAVING_AND_REBUKE_PROHIBITION",
      "slot_set": [
        "speaker",
        "addressees",
        "for_party_to_glean",
        "command_components"
      ],
      "status": "CONFIRMED",
      "occurrences_in_pericope": [
        "P19"
      ]
    }
  ],
  "high_risk_register_audit": [
    {
      "id": "R1",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0011 Wing-of-Refuge at 2:12 (P9)",
      "note": "REQUIRED keep-image. The Hebrew word kanaph must render the same way at 2:12 and at 3:9 so the petition lands as an answer to the blessing. Cross-pericope pair opens here.",
      "required_in_audit": true,
      "do_not_decide": true,
      "carries_forward_to": "P09_audit",
      "source_in_meaning_map": "Section 3C Scene 2 Objects (TH_KANAPH_WING_OF_REFUGE_FORM); Section 5B Figure Flags (FIG_0011)"
    },
    {
      "id": "R2",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0132 Amah-Vs-Shifchah at 2:13 (P11)",
      "note": "PREFERRED keep-image. Opens here with shifchah self-designation; closes at P09 3:9 with amah. Status-shift signals positioning for marriage proposal.",
      "required_in_audit": true,
      "carries_forward_to": "P09_audit",
      "source_in_meaning_map": "Section 3C Scene 2 Objects (TH_SHIFCHAH_SELF_NAMING_FORM); Section 5B Figure Flags (FIG_0132)"
    },
    {
      "id": "R3",
      "kind": "CROSS_OCCURRENCE_INTRA_PERICOPE",
      "applies_to": "Three-prohibition cluster distributed across P3 (FIG_0105 touch), P17 (FIG_0106 shame), P19 (FIG_0107 rebuke)",
      "note": "The cluster is distributed structurally across the pericope. Touch at v.9 is reported prior speech; shame at v.15 is bundled with permission-to-glean; rebuke at v.16 is bundled with leave-them. Each member must remain visible in its own structural slot. Do not collapse into a single instruction.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3C Scene 1 Objects (TH_REPORTED_PRIOR_TOUCH_PROHIBITION_FORM); Section 3C Scene 4 Objects (TH_SHAME_PROHIBITION_FORM, TH_REBUKE_PROHIBITION_FORM); Section 5B Figure Flags"
    },
    {
      "id": "R4",
      "kind": "WITHHELD_PAIRING_PER_SOURCE_DISCIPLINE",
      "applies_to": "Husband reference at v.11 (P7) — pairing withheld",
      "note": "Boaz says 'after the death of your husband' without naming which son. The pairing Mahlon-Ruth is disclosed at 4:10. P7 uses after_whose_death: B? per P01-D2 carry-forward. Reconstructor must not infer the pairing here.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3A Scene 2 Beings (Ruth's deceased husband — pair withheld; see P01-D2); Section 4 Proposition 7"
    },
    {
      "id": "R5",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "CEREMONIAL blessing form at v.12 inside INFORMAL_CASUAL chronicle",
      "note": "Boaz's v.12 utterance carries formal-blessing weight invoking YHWH the God of Israel; declared at pericope-level register_overrides.moment_level. The blessing form must read as ceremonial against the casual narrator frame.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 1 Metadata multi-level register tagging; Section 3C Scene 2 Objects (TH_BLESSING_FORM_VERSE_TWELVE); Section 4 Proposition 9"
    },
    {
      "id": "R6",
      "kind": "STRUCTURAL_ABSENCE_OF_DIVINE_AGENCY",
      "applies_to": "Moab not named by Boaz at v.11 (P8)",
      "note": "Boaz uses 'the land of your birth' (erets moladtekh) and 'a people you did not know' (am asher lo yadaat) without naming Moab or Israel. Both halves hold the named referent off. The audience knows the referents; the surface text withholds them.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3C Scene 2 Objects (TH_LAND_OF_BIRTH_UNNAMED_FORM); Section 3B Scene 2 Places (am asher lo yadaat — collective destination referenced obliquely); Significant Absence in Scene 2"
    },
    {
      "id": "R7",
      "kind": "DISCOURSE_THREAD_OPENED",
      "applies_to": "T7 harvest-provision ADVANCED_FIRST_MAJOR at 2:8-16; T5 outsider-incorporation advanced at 2:10-13; T4 hesed-answered-with-hesed enacted in substance at 2:11-12 (lexeme withheld until P07)",
      "note": "Three discourse threads are substantially advanced by this pericope. T7 is major-advanced: Boaz extends gleaning beyond legal minimum. T5: Boaz recites Ruth's loyalty in his own voice. T4: hesed is enacted but the lexeme is not yet present.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 2.4 Communicative Function; discourse-thread continuity slice in retrieved BCD context"
    },
    {
      "id": "R8",
      "kind": "NAMING_SHIFT",
      "applies_to": "Ruth self-naming as nokhriyah at v.10 (P6) and as shifchah at v.13 (P11)",
      "note": "Ruth self-designates twice across this pericope — once by outsider category (nokhriya, v.10) and once by servant-girl status (shifchah, v.13). Both shifts come from Ruth's own mouth. The narrator does not impose either label.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3C Scene 2 Objects (TH_NOKHRIYA_SELF_DESIGNATION_FORM, TH_SHIFCHAH_SELF_NAMING_FORM)"
    },
    {
      "id": "R9",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "Boaz does not name himself; Ruth addresses him as adoni",
      "note": "Throughout the pericope Boaz does not name himself to Ruth. Ruth addresses him as adoni at v.13 — a deferential form, not a name. The audience knows his name; the character does not. P6 and P10 carry name_known_status: NAME_NOT_YET_KNOWN_TO_RUTH.",
      "required_in_audit": true,
      "source_in_meaning_map": "Significant Absence in Scene 1; Section 3C Scene 2 Objects (TH_ADONI_MY_LORD_DEFERENTIAL_FORM); Section 4 Proposition 10"
    },
    {
      "id": "R10",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0104 Abundance Triplet at 2:14 (P15)",
      "note": "REQUIRED keep-image. Three verbs (ate / was satisfied / had leftover) must render as a clear triplet. The third verb is structurally available for the forward link to P07 v.18 (Ruth carrying leftover to Naomi).",
      "required_in_audit": true,
      "do_not_decide": true,
      "carries_forward_to": "P07_audit",
      "source_in_meaning_map": "Section 3C Scene 3 Objects (TH_ABUNDANCE_TRIPLET_FORM); Section 5B Figure Flags (FIG_0104)"
    },
    {
      "id": "R11",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0102 Heart-Reaching-Speech at 2:13 (P11)",
      "note": "PREFERRED keep-image. 'You have spoken to the heart of your servant-girl' must read as warmer than ordinary speech.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3C Scene 2 Objects (TH_DIBBARTA_AL_LEV_HEART_REACHING_SPEECH_FORM); Section 5B Figure Flags (FIG_0102)"
    },
    {
      "id": "R12",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0100 Full-Knowledge-Doubling at 2:11 (P7); FIG_0101 Deliberate-Pulling-Doubling at 2:16 (P18)",
      "note": "Two infinitive-absolute doublings within the pericope. FIG_0100 marks Boaz's full knowledge of what Ruth did. FIG_0101 marks the harvesters' pulling as deliberate. Both PREFERRED keep-images.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3C Scene 2 Objects (TH_HUGGAD_HUGGAD_FULL_KNOWLEDGE_DOUBLING); Section 3C Scene 4 Objects (TH_SHOL_TASHOLLU_DELIBERATE_PULLING_DOUBLING)"
    },
    {
      "id": "R13",
      "kind": "CROSS_OCCURRENCE_INTRA_PERICOPE",
      "applies_to": "TH_HEN_BE_EINEKHA_FAVOR_IDIOM at v.10 (P6) and v.13 (P10)",
      "note": "The hen-be-einekha idiom occurs twice in the pericope — once in Ruth's information-seeking question at v.10, once in Ruth's hoped-for wish at v.13. One TH-code, two illocutionary uses (ASKS_INFORMATION_SEEKING_QUESTION at P6 component; STATES_HOPED_FOR_CONDITION at P10). The lexical repetition should remain visible.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3C Scene 2 Objects (TH_HEN_BE_EINEKHA_FAVOR_IDIOM with cross_occurrences 2:10 and 2:13)"
    },
    {
      "id": "R14",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "Ruth-Naomi covenant-strength image at v.8 (P1) via TH_DABAQ_STAY_CLOSE_DIRECTIVE",
      "note": "Boaz's directive uses the dabaq root that earlier described Ruth's clinging to Naomi at 1:14 (FIG_0012). The image-rhyme links Ruth's first act of loyalty to her placement under Boaz's protection. PREFERRED keep-image if the target language can carry the verbal echo.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3C Scene 1 Objects (TH_DABAQ_STAY_CLOSE_DIRECTIVE — image-rhyme with Ruth's clinging to Naomi at 1:14)"
    }
  ],
  "cross_pericope_pair_verification": {
    "pairs": [
      {
        "fig_id": "FIG_0011",
        "opens_at": "P06 P9 (2:12)",
        "closes_at": "P09 3:9 (FIG_0131 Wing-of-Refuge-Requested)",
        "verification_status": "PENDING",
        "note": "P09 not yet compiled under Pilot 2. Verification deferred pending P09 compilation."
      },
      {
        "fig_id": "FIG_0132",
        "opens_at": "P06 P11 (2:13 shifchah)",
        "closes_at": "P09 3:9 (amah)",
        "verification_status": "PENDING",
        "note": "P09 not yet compiled under Pilot 2. Verification deferred pending P09 compilation."
      },
      {
        "fig_id": "FIG_0104",
        "opens_at": "P06 P15 (2:14 third verb 'had leftover')",
        "closes_at": "P07 (2:18 Ruth carrying leftover to Naomi)",
        "verification_status": "PENDING",
        "note": "P07 not yet compiled under Pilot 2 in current pipeline order. Forward link verified at meaning-map level; structural verification deferred pending P07 compilation."
      },
      {
        "fig_id": "FIG_0105",
        "opens_at": "P06 P3 (2:9 touch, reported prior command)",
        "closes_at": "P06 P19 (2:16 rebuke; within-pericope cluster closure)",
        "verification_status": "VERIFIED",
        "note": "Three-prohibition cluster distributed within P06 across P3, P17, P19. Within-pericope distribution verified at P06 compilation."
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
    "speech_act_values_used": [
      "STATES_AS_TRUE",
      "STATES_HOPED_FOR_CONDITION",
      "STATES_LAMENT_OBSERVATION",
      "DIRECTS_HEARER_TO_DO",
      "DIRECTS_HEARER_NOT_TO_DO",
      "GRANTS_PERMISSION_TO_DO",
      "WISHES_FOR_HEARER",
      "ASKS_INFORMATION_SEEKING_QUESTION",
      "REPORTS_OWN_PRIOR_PROHIBITION"
    ],
    "negation_not_double_encoded": true,
    "cross_pericope_cross_refs_present_on_correct_propositions": true,
    "empty_slot_rule_applied_to_times_in_scene": true,
    "discourse_threads_tracked_in_audit_only": true,
    "known_limitations_tracked_in_audit_only": true,
    "high_risk_register_complete": true,
    "every_high_risk_entry_traces_to_meaning_map": true,
    "significant_absences_traced_to_meaning_map": true,
    "no_content_added_beyond_meaning_map": true,
    "wife_pairing_withholding_enforced": true,
    "b_codes_match_bcd_version": "All B-codes verified against ruth_pilot_BCD_v0_3 (B3, B9, B10, B13, B14, B16, B17, B? for withheld pairing)",
    "registry_additions_extracted_to_bcd_delta": true,
    "no_reviewer_facing_prompts_in_compilation_log": true
  },
  "known_limitations": [
    "PL_AMONG_SHEAVES used as a working code pending formal PL-code assignment in BCD v0.4.",
    "Cross-pericope pair verification for FIG_0011, FIG_0132, and FIG_0104 deferred pending P07 and P09 compilations.",
    "Wife pairing at v.11 withheld per P01-D2 source-text discipline. Pairing disclosure carried forward to P13 audit at 4:10.",
    "FIG_0001 Ruth-the-Moabitess narrator-epithet does not fire in P06; carries forward to P07 v.21 where the narrator-voice epithet returns.",
    "CB_0011 Hesed lexeme does not fire in P06; hesed is enacted in narrative substance but the word first appears at 2:20 (P07).",
    "community_verified and translation_team_verified remain false; this is a pilot compilation."
  ]
}
```

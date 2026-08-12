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
  "confidence_overall_note": "Judgment half machine-drafted (SC-0063, patch-only contract) and ruled by Marcia axis-by-axis under SC-0064 (§A–§E + arc_element). The graduated MEANING_COORDINATES validates block-clean with 0 convergent drift and is lint-clean. Mechanized log: vocabulary_additions are this pericope's ruled mints; the high-risk register audit remains the R1 placeholder (judgment, not hand-authored in this pass).",
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
      "kind": "SKELETON_PENDING_HIGH_RISK_REVIEW",
      "applies_to": "(whole pericope — high-risk register audit not yet assigned)",
      "note": "Deterministic skeleton: the high-risk register audit (figures to keep, naming shifts, structural absences) is judgment and is deferred to Agent 3 / the READING_QUALITY gate. This is a placeholder so the COMPILATION-LOG is schema-valid; it is not a finding.",
      "required_in_audit": true,
      "source_in_meaning_map": "(skeleton — pending judgment)"
    }
  ],
  "cross_pericope_pair_verification": {
    "pairs": []
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
    "high_risk_register_complete": false,
    "every_high_risk_entry_traces_to_meaning_map": false,
    "no_content_added_beyond_meaning_map": true,
    "registry_additions_extracted_to_bcd_delta": true,
    "no_reviewer_facing_prompts_in_compilation_log": true
  },
  "known_limitations": [
    "Mechanized ruled log (SC-0064 close part 2): the judgment half was machine-drafted (SC-0063) and reviewer-ruled; vocabulary_additions are assembled from this pericope's per-axis ruling-logs.",
    "The high-risk register audit (figures to keep, naming shifts, structural absences) is NOT hand-authored — the R1 placeholder remains honest; it is judgment for the READING_QUALITY gate.",
    "Propositions stay at meaning-map granularity; multi-event propositions decompose in-slot per the granularity contract."
  ]
}
```

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
  "confidence_overall_note": "Judgment half machine-drafted (50/50 gaps, patch-only contract, 0 rejected), all four gates green, ruled by Marcia (bless with amendments). High-risk register audit still pending (placeholder retained).",
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
      "DIRECTS_HEARER_NOT_TO_DO",
      "DIRECTS_HEARER_TO_DO",
      "STATES_AS_TRUE",
      "STATES_HOPED_FOR_CONDITION"
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
    "Judgment half machine-drafted under SC-0063 and ruled by the reviewer; the high-risk register audit is NOT yet authored — the R1 placeholder remains honest.",
    "Propositions stay at meaning-map granularity (9); P4 and P7 decompose in-slot via instruction_components per the granularity contract.",
    "Commanded steps are content (commanded_step), not action-axis values — Marcia idiom ruling 2026-06-12."
  ]
}
```

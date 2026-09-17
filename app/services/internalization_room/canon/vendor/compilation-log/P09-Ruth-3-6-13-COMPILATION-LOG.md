---
type: "sta-compilation-log"
pericope: "P09"
status: "valid"
pilot: "pilot-2"
---

# P09 — Ruth 3:6-13 — COMPILATION-LOG

```json
{
  "sta_id": "ruth_pericope_09_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Ruth 3:6-13",
  "pericope_id": "P09",
  "pericope_title": "The threshing-floor night: the wing asked for, the redeemer named, the oath",
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
      "decision_id": "P09-D1",
      "decision": "Deterministically compiled a MEANING_COORDINATES skeleton from the approved Meaning Map.",
      "description": "Extracted header/classification, scene + entity IDs + presence, verse-ranges, significant_absence, communicative purpose, proposition anchors/scene-links/cross-refs, and Section-5 concept/figure flags. 101 judgment fields left as typed placeholders for Agent 3. No values invented (extract-only)."
    },
    {
      "decision_id": "P09-D2",
      "decision": "Judgment gaps filled by the SC-0063 drafter (Slice 4).",
      "description": "claude-opus-4-8 under the pinned fm-drafter prompt; structured-output fills merged by the patch-only layer. Provenance: _working/P09/drafts/run-2026-06-12T15-02-29-206Z/."
    },
    {
      "decision_id": "P09-D3",
      "decision": "Ruled by Marcia under SC-0064 (the batch ruling), axis by axis.",
      "description": "§A–§E + the five §B axes (action+tone, proposition_kind, role_in_scene_being, scene_kind, arc_element) ruled across 2026-06-12→19; 12 vocabulary addition(s) CONFIRMED for promotion for this pericope (per-axis ruling-logs in _working/P09/P09-SC-0064-*-RULING-LOG.md). Renames/collapses applied to the MEANING_COORDINATES as recorded amendments where ruled."
    }
  ],
  "vocabulary_additions": {
    "proposition_kinds": [
      {
        "value": "LAY_DOWN",
        "source": "P09-MEANING-COORDINATES + P10-MEANING-COORDINATES · SC-0063 drafter (claude-opus-4-8; P09 run-2026-06-12T15-02-29-206Z req a8b2dd69…) · ruled dual-axis by Marcia 2026-06-13 (proposition_kind Group A)",
        "status": "CONFIRMED",
        "note": "A lying-down event (P09 3:7 'he came to lie down at the end of the grain heap'; P10 3:14 'she lay until the morning'). Its `action` half was promoted in B1; this completes the deferred dual-axis by adding the `proposition_kind` half."
      },
      {
        "value": "WENT_DOWN",
        "source": "P09-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-02-29-206Z (claude-opus-4-8, req a8b2dd692305aee9…) · ruled by Marcia 2026-06-13 (proposition_kind Group B)",
        "status": "CONFIRMED",
        "note": "The narrative yarad descent (Ruth 3:6 'she went down to the threshing floor'; also J01 1:3 'going down to Joppa', J02 1:5 'gone down into the hold'). Kept distinct (Marcia's B-3 keep) from the psalm's DESCENDED — same root, different register."
      },
      {
        "value": "APPROACHED",
        "source": "P09-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-02-29-206Z (claude-opus-4-8, req a8b2dd692305aee9…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). MM P4: 'she came softly, uncovered the place of his feet, and lay down' — a multi-action approach with no approved proposition_kind fit."
      },
      {
        "value": "REASSURED",
        "source": "P09-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-02-29-206Z (claude-opus-4-8, req a8b2dd692305aee9…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). MM P14: 'do not fear; all that you say I will do for you' — a reassurance/pledge act (FIG_0123/FIG_0136) with no approved proposition_kind fit."
      },
      {
        "value": "TREMBLED",
        "source": "P09-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-02-29-206Z (claude-opus-4-8, req a8b2dd692305aee9…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). MM P5: 'the man trembled and twisted' — the vayyecherad startle, with no approved proposition_kind fit."
      }
    ],
    "scene_kinds": [
      {
        "value": "NIGHT_APPROACH_SCENE",
        "source": "P09-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-02-29-206Z (claude-opus-4-8, req a8b2dd692305aee9…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM 3F-S1: 'Executes the plan to the letter and sets the night's stage' — a wordless nighttime approach scene with no approved fit (MEAL_SCENE/INSTRUCTION_SCENE miss the staging focus)."
      }
    ],
    "presence_values": [],
    "referential_forms": [],
    "other": [],
    "arc_elements": [
      {
        "value": "NEARER_REDEEMER_DISCLOSURE",
        "source": "P09-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-02-29-206Z (claude-opus-4-8, req a8b2dd692305aee9…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 3:12: 'there is a redeemer nearer than I' turns 2:20's comfort into a legal queue; distinct beat with no approved fit."
      },
      {
        "value": "PLAN_EXECUTION",
        "source": "P09-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-02-29-206Z (claude-opus-4-8, req a8b2dd692305aee9…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1/3F-S1: Ruth 'does all her mother-in-law commanded' — the carrying-out of P08's plan; no approved arc token names execution of a prior plan."
      },
      {
        "value": "WING_PETITION",
        "source": "P09-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-02-29-206Z (claude-opus-4-8, req a8b2dd692305aee9…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 3:9: 'spread your wing over your servant' — the kanaf marriage/protection petition closing the 2:12 image; no approved arc token covers this petition."
      }
    ],
    "action_values": [
      {
        "value": "UNCOVERED_FEET",
        "source": "P09-MEANING-COORDINATES P4@3:7c · SC-0063 drafter run-2026-06-12T15-02-29-206Z (claude-opus-4-8, request a8b2dd692305aee9…) · declared mint (fills.json) · ruled tick by Marcia 2026-06-12 (SC-0064 §B sitting 1, item 5)",
        "status": "CONFIRMED",
        "note": "Uncovered the place of his feet (margelot, CB_0042) — the plan's central act (3:7); no approved action token covers uncovering."
      },
      {
        "value": "LAY_DOWN",
        "source": "P09-MEANING-COORDINATES P4@3:7c · SC-0063 drafter run-2026-06-12T15-02-29-206Z (claude-opus-4-8, request a8b2dd692305aee9…) · declared mint (fills.json) · ruled tick by Marcia 2026-06-12 (SC-0064 §B sitting 1, item 6)",
        "status": "CONFIRMED",
        "note": "And lay down (3:7) — no approved action-axis fit. ACTION half only: the dual-axis proposition_kind LAY_DOWN proposal (P09 P3 + P10 P1) was explicitly DEFERRED by Marcia (sitting-1 item 13) to the proposition_kind sitting."
      }
    ],
    "role_in_scene_beings": [
      {
        "value": "POTENTIAL_SUITORS",
        "source": "P09-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-02-29-206Z (claude-opus-4-8, req a8b2dd692305aee9…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM 3A-S3: 'the young men of marrying age, poor or rich; none of them chosen' — their scene function is the unchosen marital alternative, with no approved role_in_scene_being fit."
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
      "DIRECTS_HEARER_NOT_TO_DO",
      "DIRECTS_HEARER_TO_DO",
      "INVOKES_DIVINE_AS_OATH_GUARANTOR",
      "STATES_AS_TRUE",
      "VOWS",
      "WISHES_FOR_HEARER"
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

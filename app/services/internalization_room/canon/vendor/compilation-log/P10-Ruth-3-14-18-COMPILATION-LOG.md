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
  "confidence_overall_note": "Judgment half machine-drafted (SC-0063, patch-only contract) and ruled by Marcia axis-by-axis under SC-0064 (§A–§E + arc_element). The graduated MEANING_COORDINATES validates block-clean with 0 convergent drift and is lint-clean. Mechanized log: vocabulary_additions are this pericope's ruled mints; the high-risk register audit remains the R1 placeholder (judgment, not hand-authored in this pass).",
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
      "ASKS_KINSHIP_BELONGING_QUESTION",
      "DIRECTS_HEARER_NOT_TO_DO",
      "DIRECTS_HEARER_TO_DO",
      "REPORTS_PRIOR_SPEECH_INSTRUCTION",
      "STATES_AS_TRUE"
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

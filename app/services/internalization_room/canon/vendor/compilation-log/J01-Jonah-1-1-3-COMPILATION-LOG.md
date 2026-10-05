---
type: "sta-compilation-log"
pericope: "J01"
status: "valid"
pilot: "pilot-2"
---

# J01 — Jonah 1:1–3 — COMPILATION-LOG

```json
{
  "sta_id": "jonah_pericope_01_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Jonah 1:1-3",
  "pericope_id": "P01",
  "pericope_title": "The word comes to Jonah, and Jonah flees",
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
      "decision_id": "P01-D1",
      "decision": "Deterministically compiled a MEANING_COORDINATES skeleton from the approved Meaning Map.",
      "description": "Extracted header/classification, scene + entity IDs + presence, verse-ranges, significant_absence, communicative purpose, proposition anchors/scene-links/cross-refs, and Section-5 concept/figure flags. 40 judgment fields left as typed placeholders for Agent 3. No values invented (extract-only)."
    },
    {
      "decision_id": "P01-D2",
      "decision": "Judgment gaps filled by the SC-0063 drafter (Slice 4).",
      "description": "claude-opus-4-8 under the pinned fm-drafter prompt; structured-output fills merged by the patch-only layer. Provenance: _working/J01/drafts/run-2026-06-12T15-40-51-526Z/."
    },
    {
      "decision_id": "P01-D3",
      "decision": "Ruled by Marcia under SC-0064 (the batch ruling), axis by axis.",
      "description": "§A–§E + the five §B axes (action+tone, proposition_kind, role_in_scene_being, scene_kind, arc_element) ruled across 2026-06-12→19; 8 vocabulary addition(s) CONFIRMED for promotion for this pericope (per-axis ruling-logs in _working/J01/J01-SC-0064-*-RULING-LOG.md). Renames/collapses applied to the MEANING_COORDINATES as recorded amendments where ruled."
    }
  ],
  "vocabulary_additions": {
    "proposition_kinds": [
      {
        "value": "WORD_OF_YHWH_CAME",
        "source": "J01-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-40-51-526Z (claude-opus-4-8, req eaff46d1b0f65fbe…) · ruled by Marcia 2026-06-13 (proposition_kind Group B)",
        "status": "CONFIRMED",
        "note": "Collapse SURVIVOR (Marcia's B-1 ruling): the 'word of YHWH came to Jonah' formula — J01 1:1 (this code, amended here from the drafter's DIVINE_WORD_CAME) and J04 3:1 'a second time'. DIVINE_WORD_CAME is collapsed into WORD_OF_YHWH_CAME (the literal form); the J01 FM is amended and DIVINE_WORD_CAME is NOT promoted."
      },
      {
        "value": "EMBARKED",
        "source": "J01-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-40-51-526Z (claude-opus-4-8, req eaff46d1b0f65fbe…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). MM P5: 'paying / going down into it / to sail / with the crew / away from before YHWH' — boarding the vessel to flee; no approved proposition_kind names embarkation."
      },
      {
        "value": "FLED",
        "source": "J01-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-40-51-526Z (claude-opus-4-8, req eaff46d1b0f65fbe…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). MM P3: 'getting up / to flee / to Tarshish / away from before YHWH' — a flight; no approved proposition_kind names fleeing (ROSE and DEPARTED understate the refusal)."
      }
    ],
    "scene_kinds": [
      {
        "value": "FLIGHT_SCENE",
        "source": "J01-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-40-51-526Z (claude-opus-4-8, req eaff46d1b0f65fbe…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM Scene 2 / 3F: 'Records the flight: the prophet's refusal, carried out as a journey the opposite way' — no approved scene_kind names a flight."
      }
    ],
    "presence_values": [],
    "referential_forms": [],
    "other": [],
    "arc_elements": [
      {
        "value": "DIVINE_COMMISSION",
        "source": "J01-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-40-51-526Z (claude-opus-4-8, req eaff46d1b0f65fbe…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1/2.4: the passage opens with YHWH's word/charge to go to Nineveh — the commission the rest of the book answers; no approved arc token names a divine commissioning."
      },
      {
        "value": "FLIGHT_FROM_PRESENCE",
        "source": "J01-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-40-51-526Z (claude-opus-4-8, req eaff46d1b0f65fbe…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1: Jonah runs the opposite way 'away from before YHWH' — the flight is the structural turn; approved DEPARTURE connotes ordinary leave-taking, not flight from the divine presence."
      },
      {
        "value": "REFUSAL_OF_COMMISSION",
        "source": "J01-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-40-51-526Z (claude-opus-4-8, req eaff46d1b0f65fbe…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.4: 'a prophet who answers it with his heels' — the refusal is the burden of the pericope; no approved token captures a refused charge."
      }
    ],
    "role_in_scene_beings": [
      {
        "value": "PATRONYMIC_REFERENT",
        "source": "J01-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-40-51-526Z (claude-opus-4-8, req eaff46d1b0f65fbe…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM 3A: Amittai 'fixes who Jonah is by naming his father'; he functions only as an identity anchor, like the approved ERA_REFERENT but for parentage."
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
      "DIRECTS_HEARER_TO_DO"
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

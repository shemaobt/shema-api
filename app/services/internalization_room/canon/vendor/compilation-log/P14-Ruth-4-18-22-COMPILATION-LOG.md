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
  "confidence_overall_note": "Judgment half machine-drafted (SC-0063, patch-only contract) and ruled by Marcia axis-by-axis under SC-0064 (§A–§E + arc_element). The graduated MEANING_COORDINATES validates block-clean with 0 convergent drift and is lint-clean. Mechanized log: vocabulary_additions are this pericope's ruled mints; the high-risk register audit remains the R1 placeholder (judgment, not hand-authored in this pass).",
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
    "speech_act_values_used": [],
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

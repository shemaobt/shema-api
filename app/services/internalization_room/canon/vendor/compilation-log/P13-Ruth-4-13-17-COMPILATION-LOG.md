---
type: "sta-compilation-log"
pericope: "P13"
status: "valid"
pilot: "pilot-2"
---

# P13 — Ruth 4:13-17 — COMPILATION-LOG

```json
{
  "sta_id": "ruth_pericope_13_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Ruth 4:13-17",
  "pericope_id": "P13",
  "pericope_title": "Obed: the conception YHWH gives, the women's blessing, the child on Naomi's lap",
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
      "decision_id": "P13-D1",
      "decision": "Deterministically compiled a MEANING_COORDINATES skeleton from the approved Meaning Map.",
      "description": "Extracted header/classification, scene + entity IDs + presence, verse-ranges, significant_absence, communicative purpose, proposition anchors/scene-links/cross-refs, and Section-5 concept/figure flags. 75 judgment fields left as typed placeholders for Agent 3. No values invented (extract-only)."
    },
    {
      "decision_id": "P13-D2",
      "decision": "Judgment gaps filled by the SC-0063 drafter (Slice 4).",
      "description": "claude-opus-4-8 under the pinned fm-drafter prompt; structured-output fills merged by the patch-only layer. Provenance: _working/P13/drafts/run-2026-06-12T15-32-24-490Z/."
    },
    {
      "decision_id": "P13-D3",
      "decision": "Ruled by Marcia under SC-0064 (the batch ruling), axis by axis.",
      "description": "§A–§E + the five §B axes (action+tone, proposition_kind, role_in_scene_being, scene_kind, arc_element) ruled across 2026-06-12→19; 10 vocabulary addition(s) CONFIRMED for promotion for this pericope (per-axis ruling-logs in _working/P13/P13-SC-0064-*-RULING-LOG.md). Renames/collapses applied to the MEANING_COORDINATES as recorded amendments where ruled."
    }
  ],
  "vocabulary_additions": {
    "proposition_kinds": [
      {
        "value": "BORE",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). MM P3 'bearing' — Ruth bears a son; no approved proposition_kind (DIED, GAVE, TOOK, etc.) covers a birth event."
      }
    ],
    "scene_kinds": [
      {
        "value": "BIRTH_SCENE",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM Scene 1 title 'The marriage, the gift, the birth' and 3F centers on the divine gift of conception and the birth of the son; no approved scene_kind covers a birth/gift resolution."
      },
      {
        "value": "NAMING_SCENE",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM Scene 3 title 'The child on Naomi's lap; the naming' and 3F center on the communal naming of the child; no approved scene_kind covers a naming event."
      }
    ],
    "presence_values": [],
    "referential_forms": [],
    "other": [],
    "arc_elements": [
      {
        "value": "BIRTH_OF_HEIR",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1: 'she bears a son' — the line's future delivered; no approved birth/heir arc token exists."
      },
      {
        "value": "COMMUNAL_NAMING",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.4: 'closes the communal-naming the book opened in Naomi's bitter homecoming' — the women name the child for Naomi; no approved naming arc token."
      },
      {
        "value": "DIVINE_GIFT_OF_CONCEPTION",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1/2.4: 'YHWH gives her conception' — the book's second direct divine act, a distinct arc beat with no approved equivalent."
      },
      {
        "value": "MARRIAGE_CONSUMMATED",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1: 'Boaz takes Ruth, she becomes his wife, he comes to her' — the redemption completed in marriage; no existing arc token covers a consummated marriage."
      }
    ],
    "role_in_scene_beings": [
      {
        "value": "GRANDMOTHER",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM Scene 2/3: 'the grandmother' to whom the child is reckoned (the once-empty widow now holding the line's future); no approved role captures the grandmother function central to this scene."
      },
      {
        "value": "LINEAGE_REFERENT",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM Scene 3: Jesse and David are 'the names the narrator reaches to past the story' — forward genealogical referents; ANCESTOR is wrong-direction and ERA_REFERENT is time-setting only."
      },
      {
        "value": "TOWNSWOMEN",
        "source": "P13-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-32-24-490Z (claude-opus-4-8, req 3debd94f41dc8452…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM Scene 2/3 'the women' / 'the neighbor-women' act as the female counterpart to the men's gate-blessing (FIG_0187); approved TOWNSPEOPLE is gender-blind and FEMALE_WORKERS is field-specific."
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

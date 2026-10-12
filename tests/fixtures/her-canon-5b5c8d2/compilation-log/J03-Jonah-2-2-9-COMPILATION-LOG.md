---
type: "sta-compilation-log"
pericope: "J03"
status: "valid"
pilot: "pilot-2"
---

# J03 — Jonah 2:2–9 — COMPILATION-LOG

```json
{
  "sta_id": "jonah_pericope_03_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Jonah 2:2-9",
  "pericope_id": "P03",
  "pericope_title": "The prayer from the deep: down to Sheol, up from the pit",
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
      "decision_id": "P03-D1",
      "decision": "Deterministically compiled a MEANING_COORDINATES skeleton from the approved Meaning Map.",
      "description": "Extracted header/classification, scene + entity IDs + presence, verse-ranges, significant_absence, communicative purpose, proposition anchors/scene-links/cross-refs, and Section-5 concept/figure flags. 72 judgment fields left as typed placeholders for Agent 3. No values invented (extract-only)."
    },
    {
      "decision_id": "P03-D2",
      "decision": "Judgment gaps filled by the SC-0063 drafter (Slice 4).",
      "description": "claude-opus-4-8 under the pinned fm-drafter prompt; structured-output fills merged by the patch-only layer. Provenance: _working/J03/drafts/run-2026-06-12T15-55-25-198Z/."
    },
    {
      "decision_id": "P03-D3",
      "decision": "Ruled by Marcia under SC-0064 (the batch ruling), axis by axis.",
      "description": "§A–§E + the five §B axes (action+tone, proposition_kind, role_in_scene_being, scene_kind, arc_element) ruled across 2026-06-12→19; 19 vocabulary addition(s) CONFIRMED for promotion for this pericope (per-axis ruling-logs in _working/J03/J03-SC-0064-*-RULING-LOG.md). Renames/collapses applied to the MEANING_COORDINATES as recorded amendments where ruled."
    }
  ],
  "vocabulary_additions": {
    "proposition_kinds": [
      {
        "value": "AFFIRMED_RESOLVE",
        "source": "J03-MEANING-COORDINATES P6@2:4 · SC-0063 drafter run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e…) · drafter value RESOLVED, renamed by Marcia 2026-06-13 (proposition_kind Group A, option b)",
        "status": "CONFIRMED",
        "note": "J03 2:4 'yet I will look again toward your holy temple' — a forward resolve, distinct from a vow or a plain speech act (the drafter's framing). Renamed from the drafter's RESOLVED to avoid the cross-axis collision with the approved `discourse_thread_state` value RESOLVED (status axis). The J03 FM proposition_kind is amended RESOLVED → AFFIRMED_RESOLVE under this ruling."
      },
      {
        "value": "DESCENDED",
        "source": "J03-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e34b1775c…) · ruled by Marcia 2026-06-13 (proposition_kind Group B)",
        "status": "CONFIRMED",
        "note": "The psalm's 'I went down to the roots of the mountains' (2:6), the descent's lowest point. Kept distinct (Marcia's B-3 keep) from the narrative WENT_DOWN."
      },
      {
        "value": "BROUGHT_UP",
        "source": "J03-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e34b1775c…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). P9: 'And you brought my life up from the pit, YHWH my God' — the lift, no approved kind covers it."
      },
      {
        "value": "ENGULFED",
        "source": "J03-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e34b1775c…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). P4: 'the flood was all around me; all your breakers and your waves passed over me' — no approved kind covers engulfment."
      },
      {
        "value": "FORSOOK",
        "source": "J03-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e34b1775c…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). P12: 'Those who hold to vain idols forsake their hesed' — no approved kind covers forsaking."
      },
      {
        "value": "REMEMBERED",
        "source": "J03-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e34b1775c…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). P10: 'As my soul fainted within me, I remembered YHWH' — remembering, distinct from PERCEIVED."
      },
      {
        "value": "CAST_INTO_DEEP",
        "source": "J03-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e34b1775c…) · ruled by Marcia 2026-06-13 (proposition_kind Group C)",
        "status": "CONFIRMED",
        "note": "YHWH's act in the psalm (2:3 'You cast me into the deep, into the heart of the seas'). Kept (Group C glance — passes: a casting event, parallel to the approved HURLED)."
      }
    ],
    "scene_kinds": [
      {
        "value": "DELIVERANCE_SCENE",
        "source": "J03-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e34b1775c…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). scene type"
      },
      {
        "value": "DISTRESS_RECOUNTING_SCENE",
        "source": "J03-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e34b1775c…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). Scene 2 recounts the casting into the deep and banishment answered by a face turned to the temple."
      },
      {
        "value": "RESCUE_DECLARATION_SCENE",
        "source": "J03-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e34b1775c…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). Scene 1 title/3F: 'States the rescue before the road: the answered call is the headline.'"
      }
    ],
    "presence_values": [],
    "referential_forms": [],
    "other": [],
    "arc_elements": [
      {
        "value": "TEMPLE_TURN",
        "source": "J03-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e34b1775c…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19); renamed from BANISHMENT_AND_TEMPLE_TURN (atomize the AND-compound to the hinge; banishment is carried by the descent beats). Map 2.1/Scene 2: 'banished from God's eyes yet turning toward his temple' — the prayer's hinge."
      },
      {
        "value": "DESCENT_INTO_THE_DEEP",
        "source": "J03-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e34b1775c…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19). Survivor of the descent collapse (Marcia 2026-06-19): J03's DESCENT_TO_THE_BOTTOM folded into this (one downward arc-movement; the staging stays in the scenes/propositions). DESCENT_TO_THE_BOTTOM not promoted. Map 2.1: 'hurled into the deep, the seas closing' — the casting into the heart of the seas."
      },
      {
        "value": "LIFT_FROM_THE_PIT",
        "source": "J03-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e34b1775c…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. Map 2.1: 'and then the lift, you brought my life up from the pit' — the single reversing movement."
      },
      {
        "value": "RESCUE_DECLARED",
        "source": "J03-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e34b1775c…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19); renamed from RESCUE_DECLARED_FIRST (strip-to-type: drop the narration-order suffix). Map 2.1/2.4: 'the rescue stated first' — the prayer tells its whole story in the first breath, I called/he answered, before walking the road."
      },
      {
        "value": "SALVATION_THESIS",
        "source": "J03-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e34b1775c…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. Map 2.1/2.4: 'The last word is the book's thesis... salvation belongs to YHWH.'"
      },
      {
        "value": "THANKSGIVING_VOW",
        "source": "J03-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e34b1775c…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. Map 2.1/Scene 4: 'the speaker will sacrifice with a voice of thanksgiving and pay what he vowed.'"
      }
    ],
    "role_in_scene_beings": [
      {
        "value": "SUPPLIANT",
        "source": "J03-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e34b1775c…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). Scene 1 role prose: 'the one praying — he called from his distress and was answered.' No approved role covers a praying suppliant."
      },
      {
        "value": "VOWER",
        "source": "J03-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e34b1775c…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). Scene 4 role prose: 'the one vowing — sacrifice with thanksgiving, payment of what he vowed.'"
      },
      {
        "value": "IDOL_KEEPERS",
        "source": "J03-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-55-25-198Z (claude-opus-4-8, req 2b28cf5e34b1775c…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). Scene 4 role prose: 'the contrast — the ones who forsake their hesed' (those who hold to vain idols)."
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
      "STATES_LAMENT_OBSERVATION",
      "VOWS"
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

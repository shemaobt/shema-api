---
type: "sta-compilation-log"
pericope: "P12"
status: "valid"
pilot: "pilot-2"
---

# P12 — Ruth 4:9-12 — COMPILATION-LOG

```json
{
  "sta_id": "ruth_pericope_12_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Ruth 4:9-12",
  "pericope_id": "P12",
  "pericope_title": "You are witnesses this day: the names spoken and the gate's blessing",
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
      "decision_id": "P12-D1",
      "decision": "Deterministically compiled a MEANING_COORDINATES skeleton from the approved Meaning Map.",
      "description": "Extracted header/classification, scene + entity IDs + presence, verse-ranges, significant_absence, communicative purpose, proposition anchors/scene-links/cross-refs, and Section-5 concept/figure flags. 79 judgment fields left as typed placeholders for Agent 3. No values invented (extract-only)."
    },
    {
      "decision_id": "P12-D2",
      "decision": "Judgment gaps filled by the SC-0063 drafter (Slice 4).",
      "description": "claude-opus-4-8 under the pinned fm-drafter prompt; structured-output fills merged by the patch-only layer. Provenance: _working/P12/drafts/run-2026-06-12T15-25-23-642Z/."
    },
    {
      "decision_id": "P12-D3",
      "decision": "Ruled by Marcia under SC-0064 (the batch ruling), axis by axis.",
      "description": "§A–§E + the five §B axes (action+tone, proposition_kind, role_in_scene_being, scene_kind, arc_element) ruled across 2026-06-12→19; 6 vocabulary addition(s) CONFIRMED for promotion for this pericope (per-axis ruling-logs in _working/P12/P12-SC-0064-*-RULING-LOG.md). Renames/collapses applied to the MEANING_COORDINATES as recorded amendments where ruled."
    }
  ],
  "vocabulary_additions": {
    "proposition_kinds": [
      {
        "value": "ACQUIRED",
        "source": "P12-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-25-23-642Z (claude-opus-4-8, req 4ded8ce0a993d3b2…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). MM P2/P3: 'I have bought all that was Elimelech's... I have bought Ruth' — the redemption-purchase; no existing proposition_kind names a legal acquisition/redemption (TOOK is take-as-wife; DECLARED is the speech frame). Reviewer may prefer a registry REDEEMED if one exists in P11."
      },
      {
        "value": "NAME_PRESERVED",
        "source": "P12-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-25-23-642Z (claude-opus-4-8, req 4ded8ce0a993d3b2…) · ruled by Marcia 2026-06-13 (proposition_kind Group C)",
        "status": "CONFIRMED",
        "note": "Consolidated neutral type (Marcia's Group-C ruling, option a): the levirate name-preservation formula's two halves — NAME_RAISED (4:10b 'raise up the name of the dead upon his inheritance') and the sentence-shaped NAME_NOT_CUT_OFF (4:10c 'so that the name is not cut off from his kindred') — BOTH renamed to NAME_PRESERVED, one neutral kind. NAME_RAISED + NAME_NOT_CUT_OFF retire; the P12 FM's P4 + P5 are amended to NAME_PRESERVED."
      }
    ],
    "scene_kinds": [],
    "presence_values": [],
    "referential_forms": [],
    "other": [],
    "arc_elements": [
      {
        "value": "COMMUNITY_WITNESS_ATTESTATION",
        "source": "P12-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-25-23-642Z (claude-opus-4-8, req 4ded8ce0a993d3b2…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1: 'The assembly answers as one: we are witnesses' — the choral attestation; distinct from BLESSING_INVOCATION; no existing token for the witness response."
      },
      {
        "value": "DEAD_NAME_RAISED",
        "source": "P12-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-25-23-642Z (claude-opus-4-8, req 4ded8ce0a993d3b2…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1/2.4: 'to raise up the name of the dead upon his inheritance, so that the name of the dead is not cut off' — the raise-up-the-name beat, distinct from the declaration and the blessing; no existing token."
      },
      {
        "value": "PUBLIC_REDEMPTION_DECLARATION",
        "source": "P12-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-25-23-642Z (claude-opus-4-8, req 4ded8ce0a993d3b2…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1: 'Boaz turns... to the whole assembly and declares what he has done... you are witnesses today that I have bought...' — the public legal attestation that completes the redemption; no existing arc token covers a witnessed redemption declaration."
      }
    ],
    "role_in_scene_beings": [
      {
        "value": "WITNESSING_ASSEMBLY",
        "source": "P12-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-25-23-642Z (claude-opus-4-8, req 4ded8ce0a993d3b2…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM 3A: 'the wider assembly called to witness alongside the elders'; TOWNSPEOPLE/PEOPLE name the group but not its scene-defining witnessing function ('you are witnesses today')."
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
      "WISHES_FOR_HEARER",
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

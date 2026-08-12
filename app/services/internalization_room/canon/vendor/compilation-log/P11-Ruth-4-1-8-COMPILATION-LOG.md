---
type: "sta-compilation-log"
pericope: "P11"
status: "valid"
pilot: "pilot-2"
---

# P11 — Ruth 4:1-8 — COMPILATION-LOG

```json
{
  "sta_id": "ruth_pericope_11_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Ruth 4:1-8",
  "pericope_id": "P11",
  "pericope_title": "The gate: the non-name, the field before Ruth, and the sandal",
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
      "decision_id": "P11-D1",
      "decision": "Deterministically compiled a MEANING_COORDINATES skeleton from the approved Meaning Map.",
      "description": "Extracted header/classification, scene + entity IDs + presence, verse-ranges, significant_absence, communicative purpose, proposition anchors/scene-links/cross-refs, and Section-5 concept/figure flags. 89 judgment fields left as typed placeholders for Agent 3. No values invented (extract-only)."
    },
    {
      "decision_id": "P11-D2",
      "decision": "Judgment gaps filled by the SC-0063 drafter (Slice 4).",
      "description": "claude-opus-4-8 under the pinned fm-drafter prompt; structured-output fills merged by the patch-only layer. Provenance: _working/P11/drafts/run-2026-06-12T15-18-11-527Z/."
    },
    {
      "decision_id": "P11-D3",
      "decision": "Ruled by Marcia under SC-0064 (the batch ruling), axis by axis.",
      "description": "§A–§E + the five §B axes (action+tone, proposition_kind, role_in_scene_being, scene_kind, arc_element) ruled across 2026-06-12→19; 17 vocabulary addition(s) CONFIRMED for promotion for this pericope (per-axis ruling-logs in _working/P11/P11-SC-0064-*-RULING-LOG.md). Renames/collapses applied to the MEANING_COORDINATES as recorded amendments where ruled."
    }
  ],
  "vocabulary_additions": {
    "proposition_kinds": [
      {
        "value": "DECLINED",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). MM P11: 'I cannot redeem it for myself, lest I ruin my own inheritance' — the redeemer declines; no approved kind covers a refusal."
      },
      {
        "value": "PASSED_BY",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). MM P2: 'the redeemer of whom Boaz had spoken is passing by' — incidental passage with no approved kind."
      }
    ],
    "scene_kinds": [
      {
        "value": "GATE_COURT_CONVENING_SCENE",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM S1 title and 3F: the court convened in three sittings at the gate; no approved scene_kind covers a legal convening."
      },
      {
        "value": "REDEMPTION_DECLINE_SCENE",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM S3: the second stage springs and the claim reverses into the decline that frees Boaz; no approved scene_kind for the declination."
      },
      {
        "value": "REDEMPTION_OFFER_SCENE",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM S2: the first stage — the field offered, the confident claim drawn; no approved scene_kind for a redemption offer."
      }
    ],
    "presence_values": [],
    "referential_forms": [],
    "other": [],
    "arc_elements": [
      {
        "value": "ATTESTATION_BY_SANDAL",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM Scene 4: the right transferred and confirmed by the drawn-off sandal, the proceeding's one physical act."
      },
      {
        "value": "GATE_COURT_CONVENED",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1/Scene 1: Boaz takes the gate, seats the redeemer and ten elders — the court is convened; no approved arc token covers a legal convening."
      },
      {
        "value": "REDEMPTION_DECLINED",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM Scene 3: the nearer redeemer reverses his claim and declines; no approved token for a declination."
      },
      {
        "value": "REDEMPTION_OFFER",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM Scene 2: the field-portion laid before the court with first right of redemption offered; no approved token for a redemption offer."
      },
      {
        "value": "STAGED_DISCLOSURE",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1/2.4: the disclosure deliberately staged — field first, Ruth second — the load-bearing shape of the passage."
      }
    ],
    "action_values": [
      {
        "value": "DREW_OFF_SANDAL",
        "source": "P11-MEANING-COORDINATES P15@4:8 · SC-0063 drafter run-2026-06-12T15-18-11-527Z (claude-opus-4-8, request 4196ff4e280a003f…) · declared mint (fills.json) · ruled tick by Marcia 2026-06-12 (SC-0064 §B sitting 1, item 7)",
        "status": "CONFIRMED",
        "note": "The redeemer draws off his sandal as the attestation act (4:8; attestation_token O26). HANDED (an approved proposition_kind) was avoided by the drafter because the MM marks the handing as not narrated — only the drawing-off is."
      }
    ],
    "tone_elements": [
      {
        "value": "PROCEDURAL",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-2026-06-12T15-18-11-527Z (claude-opus-4-8, request 4196ff4e280a003f…) · declared mint (fills.json) · ruled tick by Marcia 2026-06-12 (SC-0064 §B sitting 1, item 10)",
        "status": "CONFIRMED",
        "note": "Brisk, public, and procedural — the opposite key from the night before (MM 2.3); the gate-court's legal-transactional texture has no approved tone token."
      }
    ],
    "role_in_scene_beings": [
      {
        "value": "WITNESSING_ELDERS",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM S1: 'the seated witnesses who make the gate a court'; no approved role for legal witnesses."
      },
      {
        "value": "CONVENER",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM S1: Boaz 'takes the gate, calls the redeemer aside, and seats the elders'; no approved role names a convener of a proceeding."
      },
      {
        "value": "NEARER_REDEEMER",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM S1: 'kinsman of Elimelech's line, nearer in the queue than Boaz (3:12)'; the queue-priority role is distinct from the generic REDEEMER_KIN."
      },
      {
        "value": "REDEMPTION_OFFEROR",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM S2: 'the one who lays out the field-matter before the court'; no approved role for the one tendering a redemption offer."
      },
      {
        "value": "SELLER",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM S2: 'the seller — the widow whose hand holds Elimelech's portion'; the seller function is not among approved roles."
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
      "DIRECTS_HEARER_TO_DO",
      "GRANTS_PERMISSION_TO_DO",
      "REFUSES_REQUEST_WITH_COUNTER_DECLARATION",
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

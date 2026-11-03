---
type: "sta-compilation-log"
pericope: "E09"
status: "valid"
pilot: "pilot-2"
---

# E09 — Esther 4:9–17 — COMPILATION-LOG

```json
{
  "sta_id": "esther_pericope_09_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Esther 4:9-17",
  "pericope_id": "P09",
  "pericope_title": "The summons refused, then accepted: 'who knows whether for such a time as this' and 'if I perish, I perish'",
  "compiled_at": "2026-07-06",
  "review_status": {
    "meaning_map_status": "PARSED_BY_COMPILER",
    "sta_compilation_status": "WORKFLOW_AUTHORED_REVIEWER_RULED",
    "community_verified": false,
    "translation_team_verified": false,
    "consultant_review_required": true,
    "production_use": false
  },
  "confidence_overall": "MEDIUM",
  "confidence_overall_note": "Judgment half authored by the SC-0079 hand-authoring fan-out (adversarially cold-read) and ruled by Marcia: the promote ruling 2026-06-28 (option 1 + the action=4 amendment), the Evaluator's 52 QA corrections, the modality cold-read (fix-stream A), and the speech-act decision card 2026-07-06. The graduated MEANING_COORDINATES validates block-clean with 0 convergent drift and is lint-clean. Mechanized log: vocabulary_additions are this pericope's ruled mints (enum v0.22 per-value provenance); the high-risk register audit remains the R1 placeholder (judgment, not hand-authored in this pass).",
  "compilation_decisions": [
    {
      "decision_id": "P09-D1",
      "decision": "Deterministically compiled a MEANING_COORDINATES skeleton from the approved Meaning Map.",
      "description": "Extracted header/classification, scene + entity IDs + presence, verse-ranges, significant_absence, communicative purpose, proposition anchors/scene-links/cross-refs, and Section-5 concept/figure flags. 117 judgment fields left as typed placeholders for Agent 3. No values invented (extract-only)."
    },
    {
      "decision_id": "P09-D2",
      "decision": "MEANING_COORDINATES judgment half authored modality-aware by the SC-0079 fan-out; adversarially cold-read.",
      "description": "Authored 2026-06-28 by the SC-0079 authoring fan-out (workflow wf_63e8a4e6-a77: author -> self-validate-to-0-block -> adversarial cold-read), grounded in the pinned BHSA packet, the approved Meaning Map, and the 54-entity registry. SC-0078 modality applied at authoring time (bounded-open status axis; ASSERTED = omit)."
    },
    {
      "decision_id": "P09-D3",
      "decision": "Fix-stream B (Marcia's ruled remapping + Evaluator QA + dedup) and fix-stream A (modality cold-read) applied.",
      "description": "Fix-stream B per SC-0079-remapping-LOCKED.json: Marcia's promote ruling 2026-06-28 (option 1 + the action=4 amendment), the Evaluator's QA-FINAL 52 corrections, and the surgical per-array dedup-by-parking (canonical kept; co-occurring variants parked as themselves in quarantined-vocabulary 0.4.0). Fix-stream A: the deterministic modality status edits from the Evaluator's cold-read — A is authoritative for status over B. Applied 2026-06-29 on sc-0079-esther-compile. This pericope's A-edits: P19 -> COUNTERFACTUAL ('if I perish' — A authoritative over the table's FORESEEN). Scene #33 reverted + parked as CHARGE_AND_PROVIDENCE_QUESTION_SCENE."
    }
  ],
  "vocabulary_additions": {
    "proposition_kinds": [],
    "scene_kinds": [],
    "presence_values": [],
    "referential_forms": [],
    "other": [],
    "arc_elements": [
      {
        "value": "RESOLVE_TO_ACT",
        "source": "E09-Esther-4-9-17-MEANING-COORDINATES · SC-0079 fan-out (wf_63e8a4e6-a77, 2026-06-28) + fix-stream B remap (SC-0079-remapping-LOCKED) · ruled by Marcia 2026-06-28 (option 1 + the action=4 amendment)",
        "status": "CONFIRMED",
        "note": "Mechanized from enum v0.22 provenance: axis arc_element, first_seen E09 (this pericope). Per-axis ruling basis in tripod-eval-artifacts/SC-0079-REMAPPING-QA-HANDOFF.md; dedup + quarantine ledgered in quarantined-vocabulary.json 0.4.0."
      }
    ],
    "communicative_function_elements": [
      {
        "value": "REVERSES",
        "source": "E09-Esther-4-9-17-MEANING-COORDINATES · SC-0079 fan-out (wf_63e8a4e6-a77, 2026-06-28) + fix-stream B remap (SC-0079-remapping-LOCKED) · ruled by Marcia 2026-06-28 (option 1 + the action=4 amendment)",
        "status": "CONFIRMED",
        "note": "Mechanized from enum v0.22 provenance: axis communicative_function_element, first_seen E09 (this pericope). Per-axis ruling basis in tripod-eval-artifacts/SC-0079-REMAPPING-QA-HANDOFF.md; dedup + quarantine ledgered in quarantined-vocabulary.json 0.4.0."
      },
      {
        "value": "STATES_DANGER",
        "source": "E09-Esther-4-9-17-MEANING-COORDINATES · SC-0079 fan-out (wf_63e8a4e6-a77, 2026-06-28) + fix-stream B remap (SC-0079-remapping-LOCKED) · ruled by Marcia 2026-06-28 (option 1 + the action=4 amendment)",
        "status": "CONFIRMED",
        "note": "Mechanized from enum v0.22 provenance: axis communicative_function_element, first_seen E09 (this pericope). Per-axis ruling basis in tripod-eval-artifacts/SC-0079-REMAPPING-QA-HANDOFF.md; dedup + quarantine ledgered in quarantined-vocabulary.json 0.4.0."
      }
    ],
    "tone_elements": [
      {
        "value": "DECISIVE",
        "source": "E09-Esther-4-9-17-MEANING-COORDINATES · SC-0079 fan-out (wf_63e8a4e6-a77, 2026-06-28) + fix-stream B remap (SC-0079-remapping-LOCKED) · ruled by Marcia 2026-06-28 (option 1 + the action=4 amendment)",
        "status": "CONFIRMED",
        "note": "Mechanized from enum v0.22 provenance: axis tone_element, first_seen E09 (this pericope). Per-axis ruling basis in tripod-eval-artifacts/SC-0079-REMAPPING-QA-HANDOFF.md; dedup + quarantine ledgered in quarantined-vocabulary.json 0.4.0."
      },
      {
        "value": "SETTLED",
        "source": "E09-Esther-4-9-17-MEANING-COORDINATES · SC-0079 fan-out (wf_63e8a4e6-a77, 2026-06-28) + fix-stream B remap (SC-0079-remapping-LOCKED) · ruled by Marcia 2026-06-28 (option 1 + the action=4 amendment)",
        "status": "CONFIRMED",
        "note": "Mechanized from enum v0.22 provenance: axis tone_element, first_seen E09 (this pericope). Per-axis ruling basis in tripod-eval-artifacts/SC-0079-REMAPPING-QA-HANDOFF.md; dedup + quarantine ledgered in quarantined-vocabulary.json 0.4.0."
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
      "ADVISES_COURSE_OF_ACTION",
      "ASKS_DELIBERATIVE_QUESTION",
      "DIRECTS_HEARER_TO_DO",
      "REPORTS_PRIOR_SPEECH_REQUEST",
      "RESOLVES_TO_ACT",
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
    "Mechanized ruled log (SC-0079 compile close): the judgment half was workflow-authored and reviewer-ruled; vocabulary_additions are assembled from the enum v0.22 per-value provenance (first_seen = this pericope).",
    "The high-risk register audit (figures to keep, naming shifts, structural absences) is NOT hand-authored — the R1 placeholder remains honest; it is judgment for the READING_QUALITY gate.",
    "Propositions stay at meaning-map granularity; multi-event propositions decompose in-slot per the granularity contract."
  ]
}
```

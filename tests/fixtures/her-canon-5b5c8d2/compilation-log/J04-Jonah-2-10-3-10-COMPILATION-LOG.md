---
type: "sta-compilation-log"
pericope: "J04"
status: "valid"
pilot: "pilot-2"
---

# J04 — Jonah 2:10–3:10 — COMPILATION-LOG

```json
{
  "sta_id": "jonah_pericope_04_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Jonah 2:10-3:10",
  "pericope_id": "P04",
  "pericope_title": "Nineveh believes, and God relents",
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
      "decision_id": "P04-D1",
      "decision": "Deterministically compiled a MEANING_COORDINATES skeleton from the approved Meaning Map.",
      "description": "Extracted header/classification, scene + entity IDs + presence, verse-ranges, significant_absence, communicative purpose, proposition anchors/scene-links/cross-refs, and Section-5 concept/figure flags. 106 judgment fields left as typed placeholders for Agent 3. No values invented (extract-only)."
    },
    {
      "decision_id": "P04-D2",
      "decision": "Judgment gaps filled by the SC-0063 drafter (Slice 4).",
      "description": "claude-opus-4-8 under the pinned fm-drafter prompt; structured-output fills merged by the patch-only layer. Provenance: _working/J04/drafts/run-2026-06-12T16-03-24-411Z/."
    },
    {
      "decision_id": "P04-D3",
      "decision": "Ruled by Marcia under SC-0064 (the batch ruling), axis by axis.",
      "description": "§A–§E + the five §B axes (action+tone, proposition_kind, role_in_scene_being, scene_kind, arc_element) ruled across 2026-06-12→19; 25 vocabulary addition(s) CONFIRMED for promotion for this pericope (per-axis ruling-logs in _working/J04/J04-SC-0064-*-RULING-LOG.md). Renames/collapses applied to the MEANING_COORDINATES as recorded amendments where ruled."
    }
  ],
  "vocabulary_additions": {
    "proposition_kinds": [
      {
        "value": "BELIEVED",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). 'The men of Nineveh believe God' (Jonah 3:5)."
      },
      {
        "value": "FASTED",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). 'They call a fast and put on sackcloth, from the greatest of them to the least of them.'"
      },
      {
        "value": "RELENTED",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). 'God relents of the evil he had said he would do to them, and he does not do it' (Jonah 3:10)."
      },
      {
        "value": "VOMITED",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). 'it vomits Jonah out onto the dry land' (Jonah 2:10)."
      }
    ],
    "scene_kinds": [
      {
        "value": "COMMISSIONING_SCENE",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Collapse survivor (Marcia 2026-06-13): absorbs COMMISSION_SCENE (J01) — both name the divine-commissioning scene-kind (J01 first call, J04 second); J01 FM amended COMMISSION_SCENE→COMMISSIONING_SCENE, COMMISSION_SCENE not promoted. 'The word of YHWH comes to Jonah a second time: get up, go to Nineveh ... call to her' — a divine commissioning."
      },
      {
        "value": "DECREE_SCENE",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). 'He has it proclaimed in Nineveh, by decree of the king and his nobles' — the royal edict."
      },
      {
        "value": "DIVINE_RELENTING_SCENE",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). 'God relents of the evil he had said he would do to them, and he does not do it.'"
      },
      {
        "value": "PROCLAMATION_SCENE",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). 'he cries out: forty more days, and Nineveh is overthrown' — a public oracle proclaimed in the city."
      },
      {
        "value": "REPENTANCE_SCENE",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). 'The men of Nineveh believe God. They call a fast and put on sackcloth' — the city's turning enacted."
      }
    ],
    "presence_values": [],
    "referential_forms": [],
    "other": [],
    "arc_elements": [
      {
        "value": "DELIVERANCE_TO_DRY_LAND",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. 'The fish gives Jonah back to the dry land at a word' — the opening release."
      },
      {
        "value": "DIVINE_RELENTING",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. 'God sees what they did, and relents of the evil he had spoken, and does not do it.'"
      },
      {
        "value": "MASS_REPENTANCE",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. 'the Ninevites believe God, fast, and put on sackcloth from the greatest to the least.'"
      },
      {
        "value": "OBEDIENT_DEPARTURE",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. 'This time Jonah gets up and goes.'"
      },
      {
        "value": "ORACLE_PROCLAMATION",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. 'he carries five words: forty more days and Nineveh is overthrown.'"
      },
      {
        "value": "RECOMMISSION",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. 'the word of YHWH comes a second time — the same charge.'"
      },
      {
        "value": "ROYAL_DECREE",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. 'his decree pushes the fast out to the herds and flocks and calls every man to turn.'"
      }
    ],
    "action_values": [
      {
        "value": "AROSE",
        "source": "J04-MEANING-COORDINATES P5@3:3 + P12@3:6 · SC-0063 drafter run-2026-06-12T16-03-24-411Z (claude-opus-4-8, request 9c8abbd647feb1b6…) · declared mint ×2 (fills.json) · ruled 'approve as proposed' by Marcia 2026-06-12 (SC-0064 §B sitting 1, item 1)",
        "status": "CONFIRMED",
        "note": "The plain wayyaqom rising, no return sense — Jonah gets up and goes (3:3); the king rises from his throne (3:6, step FIRST). Approved AROSE_TO_RETURN does not fit (the drafter knew it and distinguished)."
      },
      {
        "value": "REMOVED_ROBE",
        "source": "J04-MEANING-COORDINATES P12@3:6 · SC-0063 drafter run-2026-06-12T16-03-24-411Z (claude-opus-4-8, request 9c8abbd647feb1b6…) · declared mint (fills.json) · ruled 'approve as proposed' by Marcia 2026-06-12 (SC-0064 §B sitting 1, item 2)",
        "status": "CONFIRMED",
        "note": "The king puts off his robe (3:6, step SECOND of the narrated four-step sequence)."
      },
      {
        "value": "DONNED_SACKCLOTH",
        "source": "J04-MEANING-COORDINATES P12@3:6 · SC-0063 drafter run-2026-06-12T16-03-24-411Z (claude-opus-4-8, request 9c8abbd647feb1b6…) · declared mint (fills.json) · ruled tick by Marcia 2026-06-12 (SC-0064 §B sitting 1, item 3)",
        "status": "CONFIRMED",
        "note": "Covers himself with sackcloth (3:6, step THIRD; garment O9)."
      },
      {
        "value": "SAT_ON_ASHES",
        "source": "J04-MEANING-COORDINATES P12@3:6 · SC-0063 drafter run-2026-06-12T16-03-24-411Z (claude-opus-4-8, request 9c8abbd647feb1b6…) · declared mint (fills.json) · ruled tick by Marcia 2026-06-12 (SC-0064 §B sitting 1, item 4)",
        "status": "CONFIRMED",
        "note": "And sits on the ashes (3:6, step FOURTH; seat O10)."
      }
    ],
    "tone_elements": [
      {
        "value": "WONDER_UNDERSTATED",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-2026-06-12T16-03-24-411Z (claude-opus-4-8, request 9c8abbd647feb1b6…) · declared mint (fills.json) · ruled tick by Marcia 2026-06-12 (SC-0064 §B sitting 1, item 11)",
        "status": "CONFIRMED",
        "note": "The wonder rides on how little resistance there is — a quiet astonishment the narrator never names."
      }
    ],
    "role_in_scene_beings": [
      {
        "value": "PROPHET",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Cluster survivor (Principle A, Marcia 2026-06-13): absorbs COMMISSIONED_PROPHET (J01 commissioned/acting prophet folds in). Jonah's book-spanning function as the one YHWH sends to call out to Nineveh."
      },
      {
        "value": "KING",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). 'the king of Nineveh ... rises, strips, covers, sits in ashes, and decrees.'"
      },
      {
        "value": "LIVESTOCK",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). 'man and beast, herd and flock ... covered with sackcloth' — the city's animals made part of its repentance."
      },
      {
        "value": "NOBLES",
        "source": "J04-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-03-24-411Z (claude-opus-4-8, req 9c8abbd647feb1b6…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). 'by decree of the king and his nobles' — co-issuers of the edict."
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
    "Mechanized ruled log (SC-0064 close part 2): the judgment half was machine-drafted (SC-0063) and reviewer-ruled; vocabulary_additions are assembled from this pericope's per-axis ruling-logs.",
    "The high-risk register audit (figures to keep, naming shifts, structural absences) is NOT hand-authored — the R1 placeholder remains honest; it is judgment for the READING_QUALITY gate.",
    "Propositions stay at meaning-map granularity; multi-event propositions decompose in-slot per the granularity contract."
  ]
}
```

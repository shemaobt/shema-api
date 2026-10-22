---
type: "sta-compilation-log"
pericope: "J05"
status: "valid"
pilot: "pilot-2"
---

# J05 — Jonah 4:1–11 — COMPILATION-LOG

```json
{
  "sta_id": "jonah_pericope_05_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Jonah 4:1-11",
  "pericope_id": "P05",
  "pericope_title": "The qiqayon and the last question",
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
      "decision_id": "P05-D1",
      "decision": "Deterministically compiled a MEANING_COORDINATES skeleton from the approved Meaning Map.",
      "description": "Extracted header/classification, scene + entity IDs + presence, verse-ranges, significant_absence, communicative purpose, proposition anchors/scene-links/cross-refs, and Section-5 concept/figure flags. 97 judgment fields left as typed placeholders for Agent 3. No values invented (extract-only)."
    },
    {
      "decision_id": "P05-D2",
      "decision": "Judgment gaps filled by the SC-0063 drafter (Slice 4).",
      "description": "claude-opus-4-8 under the pinned fm-drafter prompt; structured-output fills merged by the patch-only layer. Provenance: _working/J05/drafts/run-2026-06-12T16-11-20-694Z/."
    },
    {
      "decision_id": "P05-D3",
      "decision": "Ruled by Marcia under SC-0064 (the batch ruling), axis by axis.",
      "description": "§A–§E + the five §B axes (action+tone, proposition_kind, role_in_scene_being, scene_kind, arc_element) ruled across 2026-06-12→19; 23 vocabulary addition(s) CONFIRMED for promotion for this pericope (per-axis ruling-logs in _working/J05/J05-SC-0064-*-RULING-LOG.md). Renames/collapses applied to the MEANING_COORDINATES as recorded amendments where ruled."
    }
  ],
  "vocabulary_additions": {
    "proposition_kinds": [
      {
        "value": "QUESTIONED",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-13 (proposition_kind Group B)",
        "status": "CONFIRMED",
        "note": "God's probing question 'is it good that it burns to you?' (4:4). Kept distinct (Marcia's B-2 keep) from ASKED (plain info-seeking, promoted Group A) and INTERROGATED (rapid-fire) — three distinct question speech-acts."
      },
      {
        "value": "MADE_SHELTER",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). P8: 'making a booth... sitting under it in the shade.' Jonah builds his own watcher's shade (O13); no approved kind covers constructing a shelter."
      },
      {
        "value": "REJOICED",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). P11: 'rejoicing... over the qiqayon, a great joy' — the only joy in the book."
      },
      {
        "value": "STRUCK",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). P13: 'striking... the worm struck the qiqayon, and it withered.' Reused at P15 (the sun strikes Jonah's head)."
      },
      {
        "value": "ANGER_KINDLED",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-13 (proposition_kind Group C)",
        "status": "CONFIRMED",
        "note": "Jonah's burning anger (4:1 'it was evil to Jonah, a great evil, and his anger burned'). Kept (Group C glance — passes strip-to-type: a discrete becoming-angry event-beat, not a content-restatement)."
      },
      {
        "value": "CREED_RECITED",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-13 (proposition_kind Group C)",
        "status": "CONFIRMED",
        "note": "The five-fold creed recited as accusation (4:2 'gracious and compassionate, slow to anger, abounding in hesed, relenting of evil', CB_0058). Kept (Group C glance — passes: a recitation act)."
      }
    ],
    "scene_kinds": [
      {
        "value": "ANGRY_PRAYER_SCENE",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM S1: Jonah burns and prays a furious, accusatory prayer asking to die (4:1-3); no approved scene_kind covers an angry complaint-prayer."
      },
      {
        "value": "APPOINTMENT_SCENE",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM S3 (4:6-8): YHWH-God appoints plant, worm, and wind in sequence — the book's quiet signature verb building the object lesson."
      },
      {
        "value": "CLOSING_ARGUMENT_SCENE",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM S4 (4:9-11): the sharpened question, Jonah's defiant answer, and YHWH's argument from plant to city left hanging — the book's open end."
      },
      {
        "value": "WATCH_POST_SCENE",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM S2 (4:4-5): God's question hangs unanswered while Jonah goes out, builds a booth, and sits to watch the city; no approved scene_kind fits."
      }
    ],
    "presence_values": [],
    "referential_forms": [],
    "other": [],
    "arc_elements": [
      {
        "value": "ANGER_AT_DIVINE_MERCY",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. 2.1: 'The mercy that saved Nineveh lands on Jonah as a great evil, and he burns.'"
      },
      {
        "value": "APPOINTED_OBJECT_LESSON",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. 2.1: 'God's appointings come one a verse: a qiqayon plant... a worm... a cutting east wind' — the staged lesson."
      },
      {
        "value": "ARGUMENT_FROM_LESSER_TO_GREATER",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. 2.1: 'YHWH's argument from the lesser to the greater: you pitied a plant... and I, should I not pity Nineveh.'"
      },
      {
        "value": "DEATH_WISH",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. 2.1: 'He asks to die' (and again at 4:8) — the recurring death-request."
      },
      {
        "value": "DIVINE_PROBING_QUESTION",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. 2.1: 'gets a question instead — is it good that it burns to you?'"
      },
      {
        "value": "LOSS_OF_COMFORT",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. 2.1: 'a worm at dawn that kills the plant; a cutting east wind and a hammering sun, until he faints.'"
      },
      {
        "value": "UNANSWERED_QUESTION_CLOSE",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. 2.1: 'No one answers. The book ends inside the question.'"
      },
      {
        "value": "WITHDRAWAL_TO_WATCH",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. 2.1: 'walks out east of the city to watch what will become of it.'"
      },
      {
        "value": "MOTIVE_DISCLOSED",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19); renamed from WITHHELD_MOTIVE_DISCLOSED (strip-to-type: the delayed-disclosure type is MOTIVE_DISCLOSED). 2.1: 'His prayer finally says what the story has withheld since the flight: this is why I ran.'"
      }
    ],
    "tone_elements": [
      {
        "value": "HEATED",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-2026-06-12T16-11-20-694Z (claude-opus-4-8, request 84c5070972afc2d7…) · declared mint (fills.json) · ruled tick by Marcia 2026-06-12 (SC-0064 §B sitting 1, item 8)",
        "status": "CONFIRMED",
        "note": "The chapter runs on heat — Jonah burns, the sun blazes, the east wind cuts dry (MM 2.3); no approved tone token names the governing heat/anger texture."
      }
    ],
    "role_in_scene_beings": [
      {
        "value": "COMPLAINANT",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Cluster survivor (Principle A, Marcia 2026-06-13): absorbs AFFLICTED_ONE + RESPONDENT (Jonah's transient ch.4 states; WATCHER kept as the other defining posture). MM S1 role prose: 'the angry pray-er; the one who asks to die'; 3F: 'turns Israel's oldest praise into a prophet's accusation.'"
      },
      {
        "value": "WATCHER",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM S2 role prose: 'the unanswering one — he walks out and sits down to watch'; 3F: 'The watcher's post east of the city stages the lesson.'"
      },
      {
        "value": "ANIMAL_REFERENT",
        "source": "J05-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T16-11-20-694Z (claude-opus-4-8, req 84c5070972afc2d7…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM S4 role prose: 'the book's last word — the animals stand inside the final mercy'; the same beasts of the J04 decree."
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
    },
    {
      "id": "R2",
      "kind": "NAMING_SHIFT",
      "applies_to": "(whole pericope — the divine name across Jonah 4)",
      "note": "SC-0071 Phase 3 §B: the deity's name alternates deliberately across the scene — Elohim-dominant through the appointings (the plant/worm/wind: ELOHIM, with the hinge form YHWH_ELOHIM at v.6) and YHWH at the frame (the prayer v.2-3 and the close). The B2 scene referential_form was resolved from the analysis-value ELOHIM_TO_YHWH_SHIFT to the bare name YHWH (the frame/terminus name); this note preserves the deliberate alternation explicitly so it is not left to re-inference. The per-moment names remain recorded in the appointer/questioner referential_form slots. Reconstructor must preserve the Elohim->YHWH movement, not flatten it to one name.",
      "required_in_audit": true,
      "source_in_meaning_map": "Jonah 4 — the divine-name alternation (the resolved B2 referential_form + this note)"
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
      "ASKS_RHETORICAL_QUESTION_AS_DISSUASION",
      "ASKS_RHETORICAL_QUESTION_AS_PROTEST",
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

---
type: "sta-compilation-log"
pericope: "J02"
status: "valid"
pilot: "pilot-2"
---

# J02 — Jonah 1:4–2:1 — COMPILATION-LOG

```json
{
  "sta_id": "jonah_pericope_02_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Jonah 1:4-2:1",
  "pericope_id": "P02",
  "pericope_title": "The storm finds Jonah, and the sea is stilled",
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
      "decision_id": "P02-D1",
      "decision": "Deterministically compiled a MEANING_COORDINATES skeleton from the approved Meaning Map.",
      "description": "Extracted header/classification, scene + entity IDs + presence, verse-ranges, significant_absence, communicative purpose, proposition anchors/scene-links/cross-refs, and Section-5 concept/figure flags. 115 judgment fields left as typed placeholders for Agent 3. No values invented (extract-only)."
    },
    {
      "decision_id": "P02-D2",
      "decision": "Judgment gaps filled by the SC-0063 drafter (Slice 4).",
      "description": "claude-opus-4-8 under the pinned fm-drafter prompt; structured-output fills merged by the patch-only layer. Provenance: _working/J02/drafts/run-2026-06-12T15-49-40-305Z/."
    },
    {
      "decision_id": "P02-D3",
      "decision": "Ruled by Marcia under SC-0064 (the batch ruling), axis by axis.",
      "description": "§A–§E + the five §B axes (action+tone, proposition_kind, role_in_scene_being, scene_kind, arc_element) ruled across 2026-06-12→19; 35 vocabulary addition(s) CONFIRMED for promotion for this pericope (per-axis ruling-logs in _working/J02/J02-SC-0064-*-RULING-LOG.md). Renames/collapses applied to the MEANING_COORDINATES as recorded amendments where ruled."
    }
  ],
  "vocabulary_additions": {
    "proposition_kinds": [
      {
        "value": "ASKED",
        "source": "J02-MEANING-COORDINATES + P09-MEANING-COORDINATES · SC-0063 drafter (claude-opus-4-8; J02 run-2026-06-12T15-49-40-305Z req ca888faf…, P09 run-2026-06-12T15-02-29-206Z req a8b2dd69…) · ruled dual-axis by Marcia 2026-06-13 (proposition_kind Group A)",
        "status": "CONFIRMED",
        "note": "The crew's information-seeking question (J02 'what shall we do to you'; P09 3:9a 'who are you'). Already approved on `action`; promoted on proposition_kind per the dual-axis pattern. ALSO CLOSES the §D-deferred undeclared ASKED (P09 P7) — one promotion covers both pericopes."
      },
      {
        "value": "PROPOSED",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf…) · ruled dual-axis by Marcia 2026-06-13 (proposition_kind Group A)",
        "status": "CONFIRMED",
        "note": "J02 'come, let us cast lots' — a cohortative proposal (CONSULTATIVE shift at v.7). Already approved on `action`; promoted on proposition_kind per the dual-axis pattern."
      },
      {
        "value": "INTERROGATED",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-13 (proposition_kind Group B)",
        "status": "CONFIRMED",
        "note": "The crew's rapid-fire questioning of the exposed man — 'whose fault is this? what is your work?' (1:8). Kept distinct (Marcia's B-2 keep) from ASKED and QUESTIONED."
      },
      {
        "value": "ANSWERED",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). \"he answers: lift me and hurl me into the sea\" — a response to the crew's question that is itself a directive counsel."
      },
      {
        "value": "APPOINTED",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). \"YHWH appoints a great fish to swallow Jonah\" — the manah/appoint verb."
      },
      {
        "value": "CAST_LOTS",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). \"they cast, and the lot falls on Jonah\" — the lot-casting that exposes the runaway."
      },
      {
        "value": "CONFESSED",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). \"I fear YHWH, God of heaven, who made the sea and the dry land\" — Jonah's confession of the God he flees."
      },
      {
        "value": "FEARED",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). \"the sailors are afraid; each cries to his own god\" — first step of the fear escalation."
      },
      {
        "value": "HURLED",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). \"hurling ... YHWH hurled a great wind at the sea\" — the hetil/hurl verb that recurs four times in the pericope."
      },
      {
        "value": "PRAYED",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). \"Jonah prays to YHWH his God from the belly of the fish\" — the prayer the prophet never prayed on deck."
      },
      {
        "value": "ROWED",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). \"the men dig their oars in to get back to the dry land — and they cannot\" — the failed rescue effort."
      },
      {
        "value": "SWALLOWED",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). \"the fish swallows him. Jonah is in the belly of the fish three days and three nights.\""
      },
      {
        "value": "WORSHIPED",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). \"the men fear YHWH with a great fear, and they offer a sacrifice ... and they vow vows\" — the pagan crew's full worship as the storm's outcome."
      },
      {
        "value": "SEA_STILLED",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-13 (proposition_kind Group C)",
        "status": "CONFIRMED",
        "note": "The sudden calm (1:15 'the sea stood still from its raging'). Kept (Group C glance — passes: a discrete stilling event-beat)."
      },
      {
        "value": "STORM_AROSE",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-13 (proposition_kind Group C)",
        "status": "CONFIRMED",
        "note": "The storm onset (1:4 'a great storm rose on the sea, and the ship was about to break apart'). Kept (Group C glance — passes: a discrete storm-onset beat)."
      }
    ],
    "scene_kinds": [
      {
        "value": "CRISIS_DELIBERATION_SCENE",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). \"'Hurl me in' — and they row instead\" — the crew weighs what to do as the sea rises, trying to spare him before throwing him."
      },
      {
        "value": "EXPOSURE_AND_CONFESSION_SCENE",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). \"The lot finds him, and he confesses\" — the lot exposes Jonah and his own mouth confesses YHWH."
      },
      {
        "value": "HURLING_AND_WORSHIP_SCENE",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). \"Overboard: the sea stands still, and the men worship\" — the prayer, the hurling, the calm, and the crew's worship in one scene."
      },
      {
        "value": "STORM_ONSET_SCENE",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). \"The storm hits, and the prophet sleeps\" — YHWH hurls the wind, the storm rises, the crew responds while Jonah sleeps."
      },
      {
        "value": "SWALLOWING_SCENE",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). \"The fish: swallowed, three days, and a prayer begins\" — YHWH appoints the fish, it swallows Jonah, and the prayer begins."
      }
    ],
    "presence_values": [],
    "referential_forms": [],
    "other": [],
    "arc_elements": [
      {
        "value": "CREW_CRISIS_RESPONSE",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. \"The sailors do everything — pray, jettison, cast lots, interrogate, row.\""
      },
      {
        "value": "DIVINE_PURSUIT_BY_STORM",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. \"YHWH hurls a great wind at the sea, and the storm that follows hunts one man\" — the storm as divine pursuit opens the arc."
      },
      {
        "value": "EXPOSURE_BY_LOT",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. \"the lot finds Jonah\" — the runaway is exposed."
      },
      {
        "value": "HURLING_OVERBOARD",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. \"Hurled at last into the sea.\""
      },
      {
        "value": "PAGAN_WORSHIP",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. \"the pagan crew worships YHWH\" — fear, sacrifice, vows."
      },
      {
        "value": "PROVIDENTIAL_SWALLOWING",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. \"YHWH appoints a great fish to swallow the man\" — rescue in the shape of judgment closes the arc."
      },
      {
        "value": "RESCUE_ATTEMPT_FAILS",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. \"the men dig their oars in to get back to the dry land — and they cannot.\""
      },
      {
        "value": "SELF_CONFESSION",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. \"his own mouth confesses the God he is fleeing.\""
      },
      {
        "value": "SELF_SURRENDER",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19); renamed from SELF_SURRENDER_COUNSEL (strip-to-type: the beat is SELF_SURRENDER). \"his only counsel is 'hurl me in.'\""
      },
      {
        "value": "STORM_STILLED",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. \"the storm stops dead\" / \"the sea stands still from its raging.\""
      }
    ],
    "tone_elements": [
      {
        "value": "IRONIC",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-2026-06-12T15-49-40-305Z (claude-opus-4-8, request ca888faf39db84a0…) · declared mint (fills.json) · ruled tick by Marcia 2026-06-12 (SC-0064 §B sitting 1, item 9)",
        "status": "CONFIRMED",
        "note": "The prophet of YHWH fast asleep below while every pagan aboard is praying — irony named as the passage's pervasive tone; no approved token for it."
      }
    ],
    "role_in_scene_beings": [
      {
        "value": "FUGITIVE",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Cluster survivor (Principle A, Marcia 2026-06-13): absorbs FLEEING_PROPHET (Jonah's fleeing posture J01-J02). \"the runaway ... the prophet fleeing YHWH\" — Jonah's scene function throughout the pericope; no approved fit."
      },
      {
        "value": "APPOINTED_CREATURE",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Cluster survivor (Principle A, Marcia 2026-06-13): absorbs CREATURE_AGENT (J04 fish) + APPOINTED_STRIKER (J05 worm) — one role for YHWH's appointed non-human agents. \"the appointed swallower ... YHWH's creature, doing YHWH's errand without argument\" — no approved role for an appointed non-human agent."
      },
      {
        "value": "CREW",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Cluster survivor (Principle A, Marcia 2026-06-13): absorbs SHIP_CREW (the J01 sailors). \"the sailors\" / \"the men\" — the ship's working crew, with no approved maritime collective role in the list."
      },
      {
        "value": "SHIP_CAPTAIN",
        "source": "J02-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-49-40-305Z (claude-opus-4-8, req ca888faf39db84a0…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). \"the captain ... rab hachovel, the chief of the sailors\" — master of the ship; no approved equivalent."
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
      "ASKS_INFORMATION_SEEKING_QUESTION",
      "ASKS_RHETORICAL_QUESTION_AS_PROTEST",
      "DIRECTS_HEARER_NOT_TO_DO",
      "DIRECTS_HEARER_TO_DO",
      "STATES_AS_TRUE",
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

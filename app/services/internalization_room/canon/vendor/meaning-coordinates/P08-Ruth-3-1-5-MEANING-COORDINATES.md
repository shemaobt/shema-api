---
type: "sta-meaning-coordinates"
pericope: "P08"
pericope-title: "Naomi's plan for rest; Ruth's total consent"
source-meaning-map: [[P08-Ruth-3-1-5]]
status: "valid"
pilot: "pilot-2"
drafter: "claude-opus-4-8 · fm-drafter-0.1.2 · run-2026-06-12T07-25-05-695Z · ruled by Marcia 2026-06-12 (bless with amendments: P02-gold action idiom; speech acts as drafted; 6 mints approved)"
---

# P08 — Ruth 3:1-5 — MEANING_COORDINATES

Machine-drafted judgment half (SC-0063 drafter) over the deterministic skeleton; ruled and amended per Marcia's word 2026-06-12.

```json
{
  "sta_id": "ruth_pericope_08_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Ruth 3:1-5",
    "pericope_title": "Naomi's plan for rest; Ruth's total consent",
    "book_context_ref": "ruth_pilot_BCD_v0_3",
    "source_meaning_map_ref": "P08-Ruth-3-1-5",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "Both scenes shift to INTIMATE at scene level — a talk between Naomi and her daughter-in-law: Naomi's plan and Ruth's one-line answer (per MM Section 1). No moment-level register or NARRATIVE_FRAMING shifts are marked in the prose.",
      "scene_level": [
        {
          "scene_id": "S1",
          "override_value": "INTIMATE"
        },
        {
          "scene_id": "S2",
          "override_value": "INTIMATE"
        }
      ],
      "moment_level": null
    }
  },
  "level_1": {
    "arc_elements": [
      "REST_SEEKING_INITIATIVE",
      "NIGHT_PLAN_INSTRUCTION",
      "INITIATIVE_HANDOFF",
      "TOTAL_CONSENT"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "PHYSICAL_LOCATION",
      "KINSHIP_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "TEMPORAL_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT",
      "PRIOR_PERICOPE_CARRY_FORWARD"
    ],
    "tone_elements": [
      "QUIET",
      "INTIMATE",
      "RESTRAINED",
      "ANTICIPATORY",
      "UNRESOLVED_AT_CLOSE"
    ],
    "pace_elements": [
      "DELIBERATE",
      "STEADY",
      "RISES",
      "PAUSED"
    ],
    "communicative_function_elements": [
      "OPENS",
      "STAGES",
      "ADVANCES",
      "REACTIVATES",
      "WITHHOLDS"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "3:1-4",
      "scene_kind": "INSTRUCTION_SCENE",
      "scene_communicative_purpose": "Naomi asks Ruth: shall I not seek a resting place for you, that it may be well with you? She names Boaz, our kinsman, winnowing the barley at the threshing floor tonight, and gives the steps: wash, anoint yourself, put your garments on you, and go down to the threshing floor; do not be known to the man until he has finished eating and drinking; when he lies down, know the place where he lies; go in, uncover the place of his feet, and lie down. She ends: he will tell you what you shall do.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B3",
            "role_in_scene": "PLANNER",
            "presence": "PRESENT",
            "referential_form": "NAOMI_HER_MOTHER_IN_LAW"
          },
          {
            "being_id": "B9",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "PRESENT",
            "referential_form": "MY_DAUGHTER"
          },
          {
            "being_id": "B13",
            "role_in_scene": "KINSMAN",
            "presence": "REFERENCED",
            "referential_form": "OUR_KINSMAN_MODA"
          },
          {
            "being_id": "B16",
            "role_in_scene": "FEMALE_WORKERS",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL6"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0014"
          },
          {
            "object_id": "O2"
          },
          {
            "object_id": "O13"
          },
          {
            "object_id": "CB_0042"
          }
        ]
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "After \"lie down\" she says only: he will tell you what you shall do. The word redeemer (2:20) is not said here; Naomi calls Boaz \"our kinsman\"."
    },
    {
      "scene_id": "S2",
      "verse_range": "3:5",
      "scene_kind": "CONSENT_SCENE",
      "scene_communicative_purpose": "Ruth answers Naomi in one line: all that you say I will do.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B9",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "PRESENT"
          },
          {
            "being_id": "B3",
            "role_in_scene": "MOTHER_IN_LAW",
            "presence": "PRESENT"
          }
        ]
      },
      "places_in_scene": {
        "_note": "the text names no place in this scene (per meaning map)",
        "entries": null
      },
      "objects_in_scene": {
        "entries": []
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "Ruth asks nothing; she answers in one line. The narrator does not say what she thinks or feels."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "3:1",
      "proposition_kind": "APPEAL",
      "event_specific_slots": {
        "speaker": "B3",
        "speaker_referential_form": "NAOMI_HER_MOTHER_IN_LAW",
        "addressee": "B9",
        "address_form": "MY_DAUGHTER",
        "rest_sought": "CB_0014",
        "sought_rest_for": "B9",
        "question_form": "RHETORICAL_PROMISE_QUESTION",
        "speech_act": "STATES_HOPED_FOR_CONDITION"
      },
      "inter_proposition_links": {
        "forward_link_to": "P2"
      },
      "cb_flags": [
        "CB_0014"
      ],
      "figure_flags": [
        "FIG_0120"
      ]
    },
    {
      "prop_id": "P2",
      "scene_link": "S1",
      "verse_anchor": "3:2a",
      "proposition_kind": "IDENTIFIED",
      "event_specific_slots": {
        "speaker": "B3",
        "identified_kinsman": "B13",
        "kinsman_referential_form": "OUR_KINSMAN_MODA",
        "named_tie": "B16",
        "question_form": "RHETORICAL_RECOGNITION_QUESTION",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P3"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P3",
      "scene_link": "S1",
      "verse_anchor": "3:2b",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "speaker": "B3",
        "reported_about": "B13",
        "winnowed_grain": "O2",
        "location": "PL6",
        "timing": "TONIGHT",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P4"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P4",
      "scene_link": "S1",
      "verse_anchor": "3:3a",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B3",
        "instructed_party": "B9",
        "instruction_components": [
          {
            "action": "DIRECTED",
            "step_order": "FIRST",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "action": "DIRECTED",
            "step_order": "SECOND",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "action": "DIRECTED",
            "garment": "O13",
            "step_order": "THIRD",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "action": "DIRECTED",
            "destination": "PL6",
            "step_order": "FOURTH",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          }
        ]
      },
      "inter_proposition_links": {
        "forward_link_to": "P5"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0121"
      ]
    },
    {
      "prop_id": "P5",
      "scene_link": "S1",
      "verse_anchor": "3:3b",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B3",
        "instructed_party": "B9",
        "the_man_referential_form": "THE_MAN_HA_ISH",
        "speech_act": "DIRECTS_HEARER_NOT_TO_DO"
      },
      "inter_proposition_links": {
        "forward_link_to": "P6"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P6",
      "scene_link": "S1",
      "verse_anchor": "3:4a",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B3",
        "instructed_party": "B9",
        "speech_act": "DIRECTS_HEARER_TO_DO"
      },
      "inter_proposition_links": {
        "forward_link_to": "P7"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P7",
      "scene_link": "S1",
      "verse_anchor": "3:4b",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B3",
        "instructed_party": "B9",
        "instruction_components": [
          {
            "action": "DIRECTED",
            "step_order": "FIRST",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "action": "DIRECTED",
            "uncovered_place": "CB_0042",
            "step_order": "SECOND",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "action": "DIRECTED",
            "step_order": "THIRD",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          }
        ]
      },
      "inter_proposition_links": {
        "forward_link_to": "P8"
      },
      "cb_flags": [
        "CB_0042"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P8",
      "scene_link": "S1",
      "verse_anchor": "3:4c",
      "proposition_kind": "HANDED",
      "event_specific_slots": {
        "speaker": "B3",
        "future_speaker": "B13",
        "the_man_referential_form": "THE_MAN_HA_ISH",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P9"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0122"
      ]
    },
    {
      "prop_id": "P9",
      "scene_link": "S2",
      "verse_anchor": "3:5",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "speaker": "B9",
        "addressee": "B3",
        "assent_completeness": "TOTAL_NO_QUESTIONS",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P8",
        "paired_with": "P1"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0123"
      ]
    }
  ]
}
```

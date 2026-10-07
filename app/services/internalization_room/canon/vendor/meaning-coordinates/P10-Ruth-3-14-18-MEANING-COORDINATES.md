---
type: "sta-meaning-coordinates"
pericope: "P10"
pericope-title: "The nameless dawn: six measures home, and sit still"
source-meaning-map: [[P10-Ruth-3-14-18]]
status: "valid"
pilot: "pilot-2"
drafter: "claude-opus-4-8 · fm-drafter prompt (see _spec/pins.json) · machine-drafted, ruled by Marcia (SC-0064 batch ruling §A–§E + arc_element, 2026-06-19); MODEL_DRAFTED_REVIEWER_RULED"
---

# P10 — Ruth 3:14-18 — MEANING_COORDINATES

> Judgment gaps filled by the SC-0063 drafter (`tripod draft --live`); the merge layer enforced the patch-only contract. NOT canon until ruled.

```json
{
  "sta_id": "ruth_pericope_10_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Ruth 3:14-18",
    "pericope_title": "The nameless dawn: six measures home, and sit still",
    "book_context_ref": "ruth_pilot_BCD_v0_3",
    "source_meaning_map_ref": "P10-Ruth-3-14-18",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "MM Section 1 marks Scene 1 shifting to CONSULTATIVE at scene level (at the threshing floor at dawn, as in the night, under Boaz's word of 3:14) and Scene 2 to INTIMATE (Ruth and her mother-in-law, 3:16–18). No moment-level register shift and no NARRATIVE_FRAMING override are marked.",
      "scene_level": [
        {
          "scene_id": "S1",
          "override_value": "CONSULTATIVE"
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
      "SECRECY_INJUNCTION",
      "EMPTYING_REVERSED",
      "RECOGNITION_EXCHANGE",
      "INITIATIVE_HANDOFF"
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
      "STILLED",
      "ANTICIPATORY"
    ],
    "pace_elements": [
      "BRISK",
      "RISES",
      "SLOWED",
      "HOLDS"
    ],
    "communicative_function_elements": [
      "CLOSES",
      "REACTIVATES",
      "WITHHOLDS",
      "ADVANCES",
      "STAGES"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "3:14-15",
      "scene_kind": "INSTRUCTION_SCENE",
      "scene_communicative_purpose": "Ruth lies at the place of his feet until the morning and rises before one person could recognize another. Boaz says: let it not be known that the woman came to the threshing floor. He says: hold out the cloak that is on you; she holds it, and he measures six measures of barley and lays it on her, and he goes into the town.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B9",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "PRESENT",
            "referential_form": "HA_ISHAH_THE_WOMAN"
          },
          {
            "being_id": "B13",
            "role_in_scene": "REDEEMER_KIN",
            "presence": "PRESENT"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL6"
          },
          {
            "place_id": "PL4"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0042"
          },
          {
            "object_id": "O13"
          },
          {
            "object_id": "O16"
          }
        ]
      },
      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_NIGHT_TO_MORNING"
          }
        ]
      },
      "significant_absence": "The narrator tells no farewell. The narrator does not tell Boaz saying \"do not go empty to your mother-in-law\" at the threshing floor; those words are heard only in Ruth's report (3:17). The text says \"six of barley\" and does not say six of what measure."
    },
    {
      "scene_id": "S2",
      "verse_range": "3:16-18",
      "scene_kind": "REPORT_SCENE",
      "scene_communicative_purpose": "Ruth comes to her mother-in-law, who asks: who are you, my daughter? Ruth tells her all that the man did for her, and says: these six measures of barley he gave me, for he said to me, do not go empty to your mother-in-law. Naomi tells her to sit still until she knows how the matter falls, for the man will not rest unless he has finished the matter today.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B3",
            "role_in_scene": "MOTHER_IN_LAW",
            "presence": "PRESENT",
            "referential_form": "HER_MOTHER_IN_LAW_CHAMOT"
          },
          {
            "being_id": "B9",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "PRESENT",
            "referential_form": "MY_DAUGHTER"
          },
          {
            "being_id": "B13",
            "role_in_scene": "REDEEMER_KIN",
            "presence": "REFERENCED",
            "referential_form": "HA_ISH_THE_MAN"
          }
        ]
      },
      "places_in_scene": {
        "_note": "the text names no place in this scene (per meaning map)",
        "entries": null
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "O16"
          },
          {
            "object_id": "CB_0044"
          },
          {
            "object_id": "CB_0043"
          },
          {
            "object_id": "O19"
          }
        ]
      },
      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_TODAY"
          }
        ]
      },
      "significant_absence": "To Naomi's question, Ruth tells her all that the man did for her. The narrator does not tell Boaz saying \"do not go empty\" at the threshing floor; it is heard only in Ruth's report."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "3:14a",
      "proposition_kind": "LAY_DOWN",
      "event_specific_slots": {
        "reclining_woman": "B9",
        "position": "MARGELOT",
        "until_boundary": "BOQER_MORNING",
        "referential_form_at_verse": "HA_ISHAH_THE_WOMAN"
      },
      "inter_proposition_links": {
        "forward_link_to": "P2"
      },
      "cb_flags": [
        "CB_0042"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P2",
      "scene_link": "S1",
      "verse_anchor": "3:14b",
      "proposition_kind": "ROSE",
      "event_specific_slots": {
        "riser": "B9",
        "timing": "BEFORE_RECOGNITION",
        "referential_form_at_verse": "SHE_PRONOMINAL"
      },
      "inter_proposition_links": {
        "caused_by": "P1",
        "forward_link_to": "P3"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0150"
      ]
    },
    {
      "prop_id": "P3",
      "scene_link": "S1",
      "verse_anchor": "3:14c",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B13",
        "about_referential_form": "HA_ISHAH_THE_WOMAN",
        "speech_act": "DIRECTS_HEARER_NOT_TO_DO"
      },
      "inter_proposition_links": {
        "forward_link_to": "P4"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0151"
      ]
    },
    {
      "prop_id": "P4",
      "scene_link": "S1",
      "verse_anchor": "3:15a",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B13",
        "addressee": "B9",
        "garment": "O13",
        "compliance": "SHE_HELD_IT",
        "speech_act": "DIRECTS_HEARER_TO_DO"
      },
      "inter_proposition_links": {
        "forward_link_to": "P5"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P5",
      "scene_link": "S1",
      "verse_anchor": "3:15b",
      "proposition_kind": "MEASURED_OUT",
      "event_specific_slots": {
        "measurer": "B13",
        "measured_substance": "O16",
        "quantity": "SIX_MEASURES",
        "measure_unit": "UNSPECIFIED",
        "placed_on": "B9",
        "receiving_garment": "O13"
      },
      "inter_proposition_links": {
        "caused_by": "P4",
        "forward_link_to": "P6"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0152"
      ]
    },
    {
      "prop_id": "P6",
      "scene_link": "S1",
      "verse_anchor": "3:15c",
      "proposition_kind": "DEPARTED",
      "event_specific_slots": {
        "goer": "B13",
        "destination": "PL4",
        "referential_form_at_verse": "HE_PRONOMINAL"
      },
      "inter_proposition_links": {
        "forward_link_to": "P7"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P7",
      "scene_link": "S2",
      "verse_anchor": "3:16a",
      "proposition_kind": "ARRIVED_AT",
      "event_specific_slots": {
        "arriver": "B9",
        "arrival_target": "B3",
        "target_referential_form": "HER_MOTHER_IN_LAW_CHAMOT"
      },
      "inter_proposition_links": {
        "forward_link_to": "P8"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P8",
      "scene_link": "S2",
      "verse_anchor": "3:16b",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "questioner": "B3",
        "addressee": "B9",
        "address_form": "MY_DAUGHTER",
        "question_about": "IDENTITY_RECOGNITION_AND_STANDING",
        "speech_act": "ASKS_KINSHIP_BELONGING_QUESTION"
      },
      "inter_proposition_links": {
        "forward_link_to": "P9"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0154"
      ]
    },
    {
      "prop_id": "P9",
      "scene_link": "S2",
      "verse_anchor": "3:16c",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "reporter": "B9",
        "reported_to": "B3",
        "reported_party": "B13",
        "reported_party_referential_form": "HA_ISH_THE_MAN",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P8",
        "forward_link_to": "P10"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0155"
      ]
    },
    {
      "prop_id": "P10",
      "scene_link": "S2",
      "verse_anchor": "3:17a",
      "proposition_kind": "SHOWED",
      "event_specific_slots": {
        "shower": "B9",
        "shown": "O16",
        "shown_quantity": "SIX_MEASURES",
        "giver_reported": "B13",
        "giver_referential_form": "HA_ISH_THE_MAN",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "paired_with": "P5",
        "forward_link_to": "P11"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0152"
      ]
    },
    {
      "prop_id": "P11",
      "scene_link": "S2",
      "verse_anchor": "3:17b",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "reporter": "B9",
        "original_speaker": "B13",
        "gift_destination": "B3",
        "destination_referential_form": "YOUR_MOTHER_IN_LAW_CHAMOT",
        "speech_act": "REPORTS_PRIOR_SPEECH_INSTRUCTION"
      },
      "inter_proposition_links": {
        "forward_link_to": "P12"
      },
      "cb_flags": [
        "CB_0044",
        "CB_0024",
        "CB_0043"
      ],
      "figure_flags": [
        "FIG_0153"
      ]
    },
    {
      "prop_id": "P12",
      "scene_link": "S2",
      "verse_anchor": "3:18a",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B3",
        "addressee": "B9",
        "address_form": "MY_DAUGHTER",
        "matter": "O19",
        "speech_act": "DIRECTS_HEARER_TO_DO"
      },
      "inter_proposition_links": {
        "forward_link_to": "P13",
        "caused_by": "P13"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P13",
      "scene_link": "S2",
      "verse_anchor": "3:18b",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "speaker": "B3",
        "about": "B13",
        "about_referential_form": "HA_ISH_THE_MAN",
        "completion_time": "TM_TODAY",
        "matter": "O19",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {},
      "cb_flags": [],
      "figure_flags": [
        "FIG_0155",
        "FIG_0156"
      ]
    }
  ]
}
```

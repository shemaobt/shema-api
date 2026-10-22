---
type: "sta-meaning-coordinates"
pericope: "P04"
pericope-title: "Naomi and Ruth arrive in Bethlehem; the women of the town react; Naomi renames herself Mara"
source-meaning-map: [[P04-Ruth-1-19-22]]
status: "valid"
pilot: "pilot-2"
---

# P04 — Ruth 1:19–22 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "ruth_pericope_04_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Ruth 1:19-22",
    "pericope_title": "Naomi and Ruth arrive in Bethlehem; the women of the town react; Naomi renames herself Mara",
    "book_context_ref": "ruth_pilot_BCD_v0_3",
    "source_meaning_map_ref": "P04-Ruth-1-19-22",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "One scene-level INTIMATE override on S2 (Naomi's renaming lament — speaking to women of her own town from her own grief; relational-close register fits the moment better than CEREMONIAL even though renaming and Shaddai-doubling carry institutional weight at form level). S1 and S3 stay at INFORMAL_CASUAL narrator default. No moment-level overrides.",
      "scene_level": [
        {
          "scene_id": "S2",
          "override_value": "INTIMATE",
          "genre_override": null,
          "genre_group_override": null
        }
      ],
      "moment_level": null
    }
  },
  "level_1": {
    "arc_elements": [
      "PUBLIC_ARRIVAL",
      "COMMUNITY_RECOGNITION_FAILURE",
      "PUBLIC_LAMENT",
      "RENAMING_LAMENT",
      "NARRATOR_FRAMING_CLOSE",
      "HARVEST_FRAMING_OPEN"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "PHYSICAL_LOCATION",
      "KINSHIP_CONTEXT",
      "TEMPORAL_CONTEXT",
      "DIVINE_CONTEXT",
      "PRIOR_ACTION_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT"
    ],
    "tone_elements": [
      "STILLED",
      "WEIGHTED",
      "DECLARATIVE",
      "RESTRAINED",
      "UNRESOLVED_AT_CLOSE"
    ],
    "pace_elements": [
      "NARROWS",
      "RISES",
      "SETTLES"
    ],
    "communicative_function_elements": [
      "CLOSES",
      "ESTABLISHES",
      "REACTIVATES",
      "OPENS",
      "STAGES"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "1:19",
      "scene_kind": "ARRIVAL_SCENE",
      "scene_communicative_purpose": "Shows the arrival in Bethlehem out in the open; the town can hardly recognize Naomi; the women's question opens the exchange Naomi answers in Scene 2.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B3",
            "role_in_scene": "WIDOW",
            "presence": "PRESENT"
          },
          {
            "being_id": "B9",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "PRESENT"
          },
          {
            "being_id": "B28",
            "role_in_scene": "TOWNSPEOPLE",
            "presence": "PRESENT_COLLECTIVE"
          },
          {
            "being_id": "B24",
            "role_in_scene": "TOWNSPEOPLE",
            "presence": "PRESENT_COLLECTIVE"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL1"
          }
        ]
      },
      "objects_in_scene": {
        "_note": "No persistent objects in this scene.",
        "entries": null
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; time is continuous with the journey established in P02. The barley-harvest setting is named at v.22 in S3, not here.",
        "entries": null
      },
      "significant_absence": "Narrator never says why the women can hardly recognize Naomi — grief, age, the look on her, how worn she is, all left unsaid. He says nothing of anyone noticing or reacting to Ruth as they come in; no one greets either of them."
    },
    {
      "scene_id": "S2",
      "verse_range": "1:20-21",
      "scene_kind": "LAMENT_SCENE",
      "scene_communicative_purpose": "Gives Naomi's own public account of how she stands — bitter, brought home empty, testified against, treated harshly. She refuses her own name and asks for a new one. She names YHWH twice and Shaddai twice as the ones who did this to her.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B3",
            "role_in_scene": "WIDOW",
            "presence": "PRESENT"
          },
          {
            "being_id": "B24",
            "role_in_scene": "TOWNSPEOPLE",
            "presence": "PRESENT_COLLECTIVE"
          },
          {
            "being_id": "B10",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B12",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "_note": "No proper place is named in the speech; the implicit out/back trajectory between Bethlehem (departure) and Bethlehem (return) brackets the lament-arc but is not a separately named place inside Naomi's speech.",
        "entries": null
      },
      "objects_in_scene": {
        "_note": "No persistent objects in this scene.",
        "entries": null
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; the speech occurs at the moment of arrival; time is continuous.",
        "entries": null
      },
      "significant_absence": "The women say nothing back to Naomi's lament — no comfort, no welcome, nothing more asked, no taking up the new name. Naomi gives no greeting as she arrives, does not bless the women, does not introduce Ruth, does not name her dead husband or sons (only 'I went out full' hints at them). And the narrator passes no judgment on what she says."
    },
    {
      "scene_id": "S3",
      "verse_range": "1:22",
      "scene_kind": "NARRATOR_FRAMING_CLOSE_SCENE",
      "scene_communicative_purpose": "Closes the passage with the narrator's own summing-up: he goes on calling her Naomi over the new name she asked for, calls Ruth 'the Moabite' again at the moment of their public arrival, and opens the harvest season — the very harvest against which Naomi has just called herself empty.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B3",
            "role_in_scene": "WIDOW",
            "presence": "PRESENT",
            "referential_form": "NAMED"
          },
          {
            "being_id": "B9",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "PRESENT",
            "referential_form": "RUTH_THE_MOABITESS_HER_DAUGHTER_IN_LAW"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL1"
          },
          {
            "place_id": "PL2"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0026"
          }
        ]
      },
      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_BARLEY_HARVEST_BEGINNING"
          }
        ]
      },
      "significant_absence": "Narrator gives no hint of what the harvest will bring; does not say whether anyone in the town answers Naomi after her speech; gives Ruth no word and no further act as they arrive; does not name Naomi's dead husband or sons in the closing summary. Ruth has been silent through the whole passage."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "1:19a",
      "proposition_kind": "ARRIVED_AT",
      "event_specific_slots": {
        "walkers": [
          "B3",
          "B9"
        ],
        "destination": "PL1",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P2"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0013"
      ]
    },
    {
      "prop_id": "P2",
      "scene_link": "S1",
      "verse_anchor": "1:19b",
      "proposition_kind": "CITY_STIRRED",
      "event_specific_slots": {
        "stirred_collective": "B28",
        "about_whom": [
          "B3",
          "B9"
        ],
        "at_arrival_to": "PL1",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P1",
        "forward_link_to": "P3"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0013"
      ]
    },
    {
      "prop_id": "P3",
      "scene_link": "S1",
      "verse_anchor": "1:19c",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "question_speakers": "B24",
        "question_addressee_party": [
          "B3"
        ],
        "target_being_in_question": "B3",
        "speech_act": "ASKS_RHETORICAL_QUESTION_OF_SURPRISED_RECOGNITION"
      },
      "inter_proposition_links": {
        "caused_by": "P2",
        "forward_link_to": "P4"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P4",
      "scene_link": "S2",
      "verse_anchor": "1:20",
      "proposition_kind": "RENAMING",
      "event_specific_slots": {
        "speaker": "B3",
        "addressees": [
          "B24"
        ],
        "renaming_components": [
          {
            "action": "REFUSED",
            "refused_name": "Naomi",
            "refused_name_meaning": "SWEET",
            "list_position": "FIRST",
            "speech_act": "REFUSES_USE_OF_OWN_NAME"
          },
          {
            "action": "PROPOSED",
            "proposed_name": "Mara",
            "proposed_name_meaning": "BITTER",
            "referential_form_at_verse": "MARA",
            "list_position": "SECOND",
            "speech_act": "PROPOSES_NEW_NAME_FOR_SELF"
          },
          {
            "action": "STATED",
            "invoked_deity": "B12",
            "invoked_deity_referential_form": "SHADDAI",
            "list_position": "THIRD",
            "speech_act": "ASCRIBES_AFFLICTION_TO_GOD_IN_LAMENT"
          }
        ]
      },
      "inter_proposition_links": {
        "back_reference_to_proposition": "P3",
        "forward_link_to": "P5"
      },
      "cb_flags": [
        "CB_0023"
      ],
      "figure_flags": [
        "FIG_0082",
        "FIG_0083",
        "FIG_0006",
        "FIG_0195"
      ]
    },
    {
      "prop_id": "P5",
      "scene_link": "S2",
      "verse_anchor": "1:21",
      "proposition_kind": "LAMENT",
      "event_specific_slots": {
        "speaker": "B3",
        "addressees": [
          "B24"
        ],
        "lament_components": [
          {
            "action": "STATED",
            "state_at_departure": "FULL",
            "state_at_return": "EMPTY",
            "emptied_by": "B10",
            "list_position": "FIRST",
            "speech_act": "ASCRIBES_AFFLICTION_TO_GOD_IN_LAMENT"
          },
          {
            "action": "ASKED",
            "question_target_referential_form": "NAOMI",
            "list_position": "SECOND",
            "speech_act": "ASKS_RHETORICAL_QUESTION_AS_PROTEST"
          },
          {
            "action": "ASCRIBED",
            "invoked_deity": "B10",
            "list_position": "THIRD",
            "speech_act": "ASCRIBES_AFFLICTION_TO_GOD_IN_LAMENT"
          },
          {
            "action": "ASCRIBED",
            "invoked_deity": "B12",
            "invoked_deity_referential_form": "SHADDAI",
            "list_position": "FOURTH",
            "speech_act": "ASCRIBES_AFFLICTION_TO_GOD_IN_LAMENT"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P4",
        "forward_link_to": "P6"
      },
      "cb_flags": [
        "CB_0024",
        "CB_0025",
        "CB_0044"
      ],
      "figure_flags": [
        "FIG_0084",
        "FIG_0086",
        "FIG_0006",
        "FIG_0088",
        "FIG_0195",
        "FIG_0085"
      ]
    },
    {
      "prop_id": "P6",
      "scene_link": "S3",
      "verse_anchor": "1:22",
      "proposition_kind": "NARRATOR_FRAME",
      "event_specific_slots": {
        "return_components": [
          {
            "action": "RETURNED",
            "returned_party": "B3",
            "returned_referential_form": "NAMED",
            "accompanying_household": [
              "B9"
            ],
            "accompanying_referential_form": "RUTH_THE_MOABITESS_HER_DAUGHTER_IN_LAW",
            "origin_place": "PL2",
            "list_position": "FIRST",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "ARRIVED_AT",
            "arrivers": [
              "B3",
              "B9"
            ],
            "destination": "PL1",
            "time_setting": "TM_BARLEY_HARVEST_BEGINNING",
            "list_position": "SECOND",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P5",
        "paired_with": "P3"
      },
      "cb_flags": [
        "CB_0004",
        "CB_0017",
        "CB_0026"
      ],
      "figure_flags": [
        "FIG_0001",
        "FIG_0013",
        "FIG_0088"
      ]
    }
  ],
  "fidelity":   {
    "elements": [
      {
        "ref": {
          "prop_id": "P5",
          "slot": "lament_components",
          "list_position": "THIRD"
        },
        "preserve_meaning": true,
        "preserve_form": false
      }
    ]
  }
}
```

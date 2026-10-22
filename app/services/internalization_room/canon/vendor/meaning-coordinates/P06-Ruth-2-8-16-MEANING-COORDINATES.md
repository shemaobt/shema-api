---
type: "sta-meaning-coordinates"
pericope: "P06"
pericope-title: "Boaz speaks to Ruth in the field: instructions, blessing, meal, and harvester protocol"
source-meaning-map: [[P06-Ruth-2-8-16]]
status: "valid"
pilot: "pilot-2"
---

# P06 — Ruth 2:8–16 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "ruth_pericope_06_v2_0", 
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Ruth 2:8-16",
    "pericope_title": "Boaz speaks to Ruth in the field: instructions, blessing, meal, and harvester protocol",
    "book_context_ref": "ruth_pilot_BCD_v0_3",
    "source_meaning_map_ref": "P06-Ruth-2-8-16",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "Scene-level INTIMATE override on S2 (Ruth's bowed question, Boaz's recital, Ruth's response — a relational-close exchange between a foreigner and the field-owner). One moment-level CEREMONIAL override at v.12 for Boaz's formal blessing invoking YHWH the God of Israel.",
      "scene_level": [
        {
          "scene_id": "S2",
          "override_value": "INTIMATE",
          "genre_override": null,
          "genre_group_override": null
        }
      ],
      "moment_level": [
        {
          "verse": "2:12",
          "override_value": "CEREMONIAL",
          "genre_override": null,
          "genre_group_override": null
        }
      ]
    }
  },
  "level_1": {
    "arc_elements": [
      "PROTECTIVE_INSTRUCTION",
      "RECOGNITION_EXCHANGE",
      "BLESSING_INVOCATION",
      "MEAL_INCLUSION",
      "HARVESTER_PROTOCOL_EXTENSION"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "PHYSICAL_LOCATION",
      "KINSHIP_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "DIVINE_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT",
      "PRIOR_ACTION_CONTEXT"
    ],
    "tone_elements": [
      "WARM",
      "RESTRAINED",
      "WEIGHTED"
    ],
    "pace_elements": [
      "SLOWED",
      "STEADY"
    ],
    "communicative_function_elements": [
      "ESTABLISHES",
      "RECITES",
      "OPENS",
      "DISTRIBUTES",
      "ADVANCES",
      "WITHHOLDS"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "2:8-9",
      "scene_kind": "INSTRUCTION_SCENE",
      "scene_communicative_purpose": "Boaz sets up his protection of Ruth, through his instructions and the order he says he has already given his men.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B13",
            "role_in_scene": "FIELD_OWNER",
            "presence": "PRESENT",
            "referential_form": "NAMED"
          },
          {
            "being_id": "B9",
            "role_in_scene": "GLEANER",
            "presence": "PRESENT",
            "referential_form": "NAMED"
          },
          {
            "being_id": "B16",
            "role_in_scene": "FEMALE_WORKERS",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B17",
            "role_in_scene": "MALE_WORKERS",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL5_BOAZ_PORTION"
          },
          {
            "place_id": "PL_OTHER_FIELD"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0034"
          }
        ]
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; time is continuous within the harvest day established at P05.",
        "entries": null
      },
      "significant_absence": "Boaz never tells Ruth his name. Ruth says nothing; the whole scene is Boaz giving instructions."
    },
    {
      "scene_id": "S2",
      "verse_range": "2:10-13",
      "scene_kind": "BLESSING_SCENE",
      "scene_communicative_purpose": "The moment Ruth is noticed: Boaz puts her loyalty into words and blesses her in YHWH's name.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B9",
            "role_in_scene": "GLEANER",
            "presence": "PRESENT",
            "referential_form": "NAMED"
          },
          {
            "being_id": "B13",
            "role_in_scene": "FIELD_OWNER",
            "presence": "PRESENT",
            "referential_form": "NAMED"
          },
          {
            "being_id": "B3",
            "role_in_scene": "MOTHER_IN_LAW",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B?",
            "role_in_scene": "HUSBAND",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B10",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL5_BOAZ_PORTION"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0033"
          },
          {
            "object_id": "CB_0038"
          },
          {
            "object_id": "CB_0037"
          },
          {
            "object_id": "CB_0008"
          }
        ]
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; continuous within the field day.",
        "entries": null
      },
      "significant_absence": "Boaz never names Moab; he says 'the land of your birth' instead. Ruth's dead husband is not tied to one son or the other; the pairing is withheld per P01-D2. Boaz never names himself; Ruth still calls him 'my lord.'"
    },
    {
      "scene_id": "S3",
      "verse_range": "2:14",
      "scene_kind": "MEAL_SCENE",
      "scene_communicative_purpose": "Records the plain, bodily welcome of the meal; that she ate, was satisfied, and had some left over sets up the food she will carry back to Naomi.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B13",
            "role_in_scene": "FIELD_OWNER",
            "presence": "PRESENT",
            "referential_form": "NAMED"
          },
          {
            "being_id": "B9",
            "role_in_scene": "GLEANER",
            "presence": "PRESENT",
            "referential_form": "NAMED"
          },
          {
            "being_id": "B14",
            "role_in_scene": "HARVESTERS",
            "presence": "PRESENT_COLLECTIVE"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL5_BOAZ_PORTION"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0012"
          },
          {
            "object_id": "O9"
          },
          {
            "object_id": "O10"
          }
        ]
      },
      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_MEALTIME"
          }
        ]
      },
      "significant_absence": "No conversation is recorded at the meal. Ruth says nothing; the harvesters say nothing."
    },
    {
      "scene_id": "S4",
      "verse_range": "2:15-16",
      "scene_kind": "INSTRUCTION_SCENE",
      "scene_communicative_purpose": "Closes the passage with Boaz's order for extra-generous gleaning, which builds his protection of Ruth right into how the harvesters work.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B13",
            "role_in_scene": "FIELD_OWNER",
            "presence": "PRESENT",
            "referential_form": "NAMED"
          },
          {
            "being_id": "B17",
            "role_in_scene": "MALE_WORKERS",
            "presence": "PRESENT_COLLECTIVE"
          },
          {
            "being_id": "B9",
            "role_in_scene": "GLEANER",
            "presence": "PRESENT",
            "referential_form": "NAMED"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL5_BOAZ_PORTION"
          },
          {
            "place_id": "PL_AMONG_SHEAVES"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0034"
          },
          {
            "object_id": "O11"
          }
        ]
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; continuous within the field day; the rising to glean follows the meal.",
        "entries": null
      },
      "significant_absence": "Ruth is not among those Boaz speaks to; the young men are told about her, not her. Narrator never says Ruth hears the order."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "2:8",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B13",
        "addressee": "B9",
        "address_form": "MY_DAUGHTER",
        "instruction_components": [
          {
            "action": "DIRECTED",
            "field_to_stay_in": "PL5_BOAZ_PORTION",
            "list_position": "FIRST",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "action": "DIRECTED",
            "alternative_field": "PL_OTHER_FIELD",
            "list_position": "SECOND",
            "speech_act": "DIRECTS_HEARER_NOT_TO_DO"
          },
          {
            "action": "DIRECTED",
            "list_position": "THIRD",
            "speech_act": "DIRECTS_HEARER_NOT_TO_DO"
          },
          {
            "action": "DIRECTED",
            "companion_group": "B16",
            "list_position": "FOURTH",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          }
        ]
      },
      "inter_proposition_links": {
        "forward_link_to": "P2"
      },
      "cb_flags": [
        "CB_0034"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P2",
      "scene_link": "S1",
      "verse_anchor": "2:9a",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B13",
        "addressee": "B9",
        "instruction_components": [
          {
            "action": "DIRECTED",
            "field_to_watch": "PL5_BOAZ_PORTION",
            "list_position": "FIRST",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "action": "DIRECTED",
            "companion_group": "B16",
            "list_position": "SECOND",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P1",
        "forward_link_to": "P3"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P3",
      "scene_link": "S1",
      "verse_anchor": "2:9b",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "speaker": "B13",
        "addressee": "B9",
        "prior_command_giver": "B13",
        "prior_command_addressees": "B17",
        "prior_prohibition_target_party": "B9",
        "speech_act": "REPORTS_OWN_PRIOR_PROHIBITION"
      },
      "inter_proposition_links": {
        "caused_by": "P2",
        "forward_link_to": "P4"
      },
      "cross_ref": "FIG_0105 active here as first member of three-prohibition cluster (distributed: P3/P17/P19)",
      "cb_flags": [],
      "figure_flags": [
        "FIG_0105"
      ]
    },
    {
      "prop_id": "P4",
      "scene_link": "S1",
      "verse_anchor": "2:9c",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B13",
        "addressee": "B9",
        "instruction_components": [
          {
            "action": "DIRECTED",
            "drink_from": "WATER_VESSELS",
            "list_position": "FIRST",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "action": "DIRECTED",
            "water_drawers": "B17",
            "list_position": "SECOND",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P3",
        "forward_link_to": "P5"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P5",
      "scene_link": "S2",
      "verse_anchor": "2:10a",
      "proposition_kind": "PROSTRATED",
      "event_specific_slots": {
        "bower": "B9",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P4",
        "forward_link_to": "P6"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P6",
      "scene_link": "S2",
      "verse_anchor": "2:10b",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "speaker": "B9",
        "addressee": "B13",
        "exchange_components": [
          {
            "action": "ASKED",
            "list_position": "FIRST",
            "speech_act": "ASKS_INFORMATION_SEEKING_QUESTION"
          },
          {
            "action": "ASKED",
            "list_position": "SECOND",
            "speech_act": "ASKS_INFORMATION_SEEKING_QUESTION"
          },
          {
            "action": "STATED",
            "list_position": "THIRD",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P5",
        "forward_link_to": "P7"
      },
      "cb_flags": [
        "CB_0033",
        "CB_0038"
      ],
      "figure_flags": [
        "FIG_0018"
      ]
    },
    {
      "prop_id": "P7",
      "scene_link": "S2",
      "verse_anchor": "2:11a",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "speaker": "B13",
        "addressee": "B9",
        "recital_components": [
          {
            "action": "STATED",
            "loyalty_act_toward_party": "B3",
            "loyalty_act_toward_referential_form": "YOUR_MOTHER_IN_LAW",
            "after_whose_death": "B?",
            "after_whose_death_referential_form": "YOUR_HUSBAND",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P6",
        "forward_link_to": "P8"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0100"
      ]
    },
    {
      "prop_id": "P8",
      "scene_link": "S2",
      "verse_anchor": "2:11b",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "speaker": "B13",
        "addressee": "B9",
        "recital_components": [
          {
            "action": "STATED",
            "list_position": "FIRST",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "STATED",
            "list_position": "SECOND",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "STATED",
            "destination_people_form": "PEOPLE",
            "list_position": "THIRD",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P7",
        "forward_link_to": "P9"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0103"
      ]
    },
    {
      "prop_id": "P9",
      "scene_link": "S2",
      "verse_anchor": "2:12",
      "proposition_kind": "BLESSING",
      "event_specific_slots": {
        "blesser": "B13",
        "blessed_party": "B9",
        "invoked_deity": "B10",
        "invoked_deity_referential_form": "YHWH_THE_GOD_OF_ISRAEL",
        "blessing_components": [
          {
            "action": "BLESSED",
            "list_position": "FIRST",
            "speech_act": "WISHES_FOR_HEARER"
          },
          {
            "action": "BLESSED",
            "list_position": "SECOND",
            "speech_act": "WISHES_FOR_HEARER"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P8",
        "forward_link_to": "P10"
      },
      "cross_ref": "FIG_0011 opens here; cross-pericope pair closes at P09 (3:9) with FIG_0131 Wing-of-Refuge-Requested",
      "cb_flags": [
        "CB_0008",
        "CB_0037"
      ],
      "figure_flags": [
        "FIG_0011"
      ]
    },
    {
      "prop_id": "P10",
      "scene_link": "S2",
      "verse_anchor": "2:13a",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "speaker": "B9",
        "addressee": "B13",
        "address_form": "MY_LORD",
        "speech_act": "STATES_HOPED_FOR_CONDITION"
      },
      "inter_proposition_links": {
        "caused_by": "P9",
        "forward_link_to": "P11"
      },
      "cb_flags": [
        "CB_0033"
      ],
      "figure_flags": [
        "FIG_0018"
      ]
    },
    {
      "prop_id": "P11",
      "scene_link": "S2",
      "verse_anchor": "2:13b",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "speaker": "B9",
        "addressee": "B13",
        "response_components": [
          {
            "action": "STATED",
            "list_position": "FIRST",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "STATED_THAT_HE_SPOKE_TO_HEART_OF_HIS_SHIFCHAH",
            "list_position": "SECOND",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "STATED_SHE_IS_NOT_AS_ONE_OF_HIS_SHIFCHOT",
            "list_position": "THIRD",
            "speech_act": "STATES_LAMENT_OBSERVATION"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P10",
        "forward_link_to": "P12"
      },
      "cross_ref": "FIG_0132 opens here at first half (shifchah); cross-pericope pair closes at P09 (3:9) with amah",
      "cb_flags": [],
      "figure_flags": [
        "FIG_0102",
        "FIG_0132"
      ]
    },
    {
      "prop_id": "P12",
      "scene_link": "S3",
      "verse_anchor": "2:14a",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "speaker": "B13",
        "addressee": "B9",
        "when": "TM_MEALTIME",
        "invitation_components": [
          {
            "action": "DIRECTED",
            "list_position": "FIRST",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "action": "DIRECTED",
            "food_item": "CB_0012",
            "list_position": "SECOND",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "action": "DIRECTED",
            "dipping_item": "O9",
            "list_position": "THIRD",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P11",
        "forward_link_to": "P13"
      },
      "cb_flags": [
        "CB_0012"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P13",
      "scene_link": "S3",
      "verse_anchor": "2:14b",
      "proposition_kind": "SAT",
      "event_specific_slots": {
        "sitter": "B9",
        "sitting_position_relation": "BESIDE_THE_HARVESTERS",
        "alongside_party": "B14",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P12",
        "forward_link_to": "P14"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P14",
      "scene_link": "S3",
      "verse_anchor": "2:14c",
      "proposition_kind": "HANDED",
      "event_specific_slots": {
        "giver": "B13",
        "given_party": "B9",
        "given_item": "O10",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P13",
        "forward_link_to": "P15"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P15",
      "scene_link": "S3",
      "verse_anchor": "2:14d",
      "proposition_kind": "ATE",
      "event_specific_slots": {
        "eater": "B9",
        "triplet_components": [
          {
            "action": "ATE",
            "list_position": "FIRST",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "WAS_SATISFIED",
            "list_position": "SECOND",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "HAD_LEFTOVER",
            "list_position": "THIRD",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P14",
        "forward_link_to": "P16"
      },
      "cross_ref": "FIG_0104 active here as required keep-image; third action (had leftover) sets up forward link to P07 v.18 (Ruth carrying leftover to Naomi)",
      "cb_flags": [],
      "figure_flags": [
        "FIG_0104"
      ]
    },
    {
      "prop_id": "P16",
      "scene_link": "S4",
      "verse_anchor": "2:15a",
      "proposition_kind": "ROSE",
      "event_specific_slots": {
        "riser": "B9",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P15",
        "forward_link_to": "P17"
      },
      "cb_flags": [
        "CB_0034"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P17",
      "scene_link": "S4",
      "verse_anchor": "2:15b",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B13",
        "addressees": "B17",
        "about_party": "B9",
        "command_components": [
          {
            "action": "PERMITTED",
            "permitted_location": "PL_AMONG_SHEAVES",
            "material": "O11",
            "list_position": "FIRST",
            "speech_act": "GRANTS_PERMISSION_TO_DO"
          },
          {
            "action": "DIRECTED",
            "list_position": "SECOND",
            "speech_act": "DIRECTS_HEARER_NOT_TO_DO"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P16",
        "forward_link_to": "P18"
      },
      "cross_ref": "FIG_0106 active here as second member of three-prohibition cluster (distributed: P3/P17/P19)",
      "cb_flags": [
        "CB_0034"
      ],
      "figure_flags": [
        "FIG_0106"
      ]
    },
    {
      "prop_id": "P18",
      "scene_link": "S4",
      "verse_anchor": "2:16a",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B13",
        "addressees": "B17",
        "for_party_to_glean": "B9",
        "material": "O11",
        "manner": "DELIBERATELY_INTENTIONALLY",
        "speech_act": "DIRECTS_HEARER_TO_DO"
      },
      "inter_proposition_links": {
        "caused_by": "P17",
        "forward_link_to": "P19"
      },
      "cb_flags": [
        "CB_0034"
      ],
      "figure_flags": [
        "FIG_0101"
      ]
    },
    {
      "prop_id": "P19",
      "scene_link": "S4",
      "verse_anchor": "2:16b",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B13",
        "addressees": "B17",
        "for_party_to_glean": "B9",
        "command_components": [
          {
            "action": "DIRECTED",
            "list_position": "FIRST",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "action": "DIRECTED",
            "list_position": "SECOND",
            "speech_act": "DIRECTS_HEARER_NOT_TO_DO"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P18"
      },
      "cross_ref": "FIG_0107 active here as third member of three-prohibition cluster (distributed: P3/P17/P19)",
      "cb_flags": [
        "CB_0034"
      ],
      "figure_flags": [
        "FIG_0107"
      ]
    }
  ],
  "fidelity":   {
    "elements": [
      {
        "ref": {
          "prop_id": "P6",
          "slot": "exchange_components",
          "list_position": "THIRD"
        },
        "preserve_meaning": true,
        "preserve_form": false
      },
      {
        "ref": {
          "prop_id": "P9",
          "slot": "blessing_components",
          "list_position": "FIRST"
        },
        "preserve_meaning": true,
        "preserve_form": false,
        "group": "blessing_reward_and_refuge"
      },
      {
        "ref": {
          "prop_id": "P9",
          "slot": "blessing_components",
          "list_position": "SECOND"
        },
        "preserve_meaning": true,
        "preserve_form": false,
        "group": "blessing_reward_and_refuge"
      },
      {
        "ref": {
          "prop_id": "P11",
          "slot": "response_components",
          "list_position": "FIRST"
        },
        "preserve_meaning": true,
        "preserve_form": false,
        "group": "ruth_reply_grace_received_in_self_abasement"
      },
      {
        "ref": {
          "prop_id": "P11",
          "slot": "response_components",
          "list_position": "SECOND"
        },
        "preserve_meaning": true,
        "preserve_form": true,
        "group": "ruth_reply_grace_received_in_self_abasement"
      },
      {
        "ref": {
          "prop_id": "P11",
          "slot": "response_components",
          "list_position": "THIRD"
        },
        "preserve_meaning": true,
        "preserve_form": true,
        "group": "ruth_reply_grace_received_in_self_abasement"
      }
    ],
    "groups": [
      {
        "group_id": "blessing_reward_and_refuge",
        "members": [
          {
            "prop_id": "P9",
            "slot": "blessing_components",
            "list_position": "FIRST"
          },
          {
            "prop_id": "P9",
            "slot": "blessing_components",
            "list_position": "SECOND"
          }
        ],
        "preserve_meaning": true,
        "preserve_form": false
      },
      {
        "group_id": "ruth_reply_grace_received_in_self_abasement",
        "members": [
          {
            "prop_id": "P11",
            "slot": "response_components",
            "list_position": "FIRST"
          },
          {
            "prop_id": "P11",
            "slot": "response_components",
            "list_position": "SECOND"
          },
          {
            "prop_id": "P11",
            "slot": "response_components",
            "list_position": "THIRD"
          }
        ],
        "preserve_meaning": true,
        "preserve_form": false
      }
    ]
  }
}
```

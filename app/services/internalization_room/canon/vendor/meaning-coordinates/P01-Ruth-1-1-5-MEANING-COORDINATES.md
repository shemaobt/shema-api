---
type: "sta-meaning-coordinates"
pericope: "P01"
pericope-title: "The famine, the family's sojourn, and the emptying of the household"
source-meaning-map: [[P01-Ruth-1-1-5]]
status: "valid"
pilot: "pilot-2"
---

# P01 — Ruth 1:1–5 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "ruth_pericope_01_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",

  "header": {
    "bcv": "Ruth 1:1-5",
    "pericope_title": "The famine, the family's sojourn, and the emptying of the household",
    "book_context_ref": "ruth_pilot_BCD_v0_3",
    "source_meaning_map_ref": "P01-Ruth-1-1-5",
    "source_language": "Biblical Hebrew"
  },

  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "One moment-level framing override at v.1 (NARRATIVE_FRAMING axis). No scene-level overrides.",
      "scene_level": null,
      "moment_level": [
        {
          "verse": "1:1a",
          "framing_override": "COMMUNITY_MEMORY",
          "genre_override": null,
          "genre_group_override": null
        }
      ]
    }
  },

  "level_1": {
    "arc_elements": [
      "AFFLICTION",
      "DEPARTURE",
      "FOREIGN_RESIDENCE",
      "FAMILY_LOSS",
      "EMPTYING"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "PHYSICAL_LOCATION",
      "KINSHIP_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "TEMPORAL_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT",
      "HISTORICAL_ERA_CONTEXT"
    ],
    "tone_elements": [
      "RESTRAINED",
      "WEIGHTED",
      "CHRONICLE",
      "SOBER",
      "QUIETLY_ACCELERATING"
    ],
    "pace_elements": [
      "STEADY",
      "QUIETLY_ACCELERATING"
    ],
    "communicative_function_elements": [
      "OPENS",
      "ESTABLISHES",
      "PLANTS",
      "TRANSMITS",
      "WITHHOLDS"
    ]
  },

  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "1:1-2",
      "scene_kind": "OPENING_CHRONICLE_SCENE",
      "scene_communicative_purpose": "Establishes era, family, homeland, and famine-driven exile.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B2",
            "role_in_scene": "HUSBAND",
            "presence": "PRESENT",
            "referential_form": "UNNAMED_MAN_FROM_BETHLEHEM"
          },
          {
            "being_id": "B3",
            "role_in_scene": "WIFE",
            "presence": "PRESENT",
            "referential_form": "UNNAMED_WIFE_OF_HEAD"
          },
          {
            "being_id": "B4",
            "role_in_scene": "SON",
            "presence": "PRESENT",
            "referential_form": "UNNAMED_FIRST_SON"
          },
          {
            "being_id": "B5",
            "role_in_scene": "SON",
            "presence": "PRESENT",
            "referential_form": "UNNAMED_SECOND_SON"
          },
          {
            "being_id": "B1",
            "role_in_scene": "ERA_REFERENT",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B6",
            "role_in_scene": "CLAN",
            "presence": "REFERENCED"
          }
        ]
      },

      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL_LAND_OF_JUDAH"
          },
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
            "object_id": "O1"
          },
          {
            "object_id": "CB_0030"
          }
        ]
      },

      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_PERIOD_OF_JUDGES"
          }
        ]
      },

      "significant_absence": "Narrator never says YHWH sent the famine or drove the family out; the book opens with no word of God acting."
    },

    {
      "scene_id": "S2",
      "verse_range": "1:3",
      "scene_kind": "BEREAVEMENT_SCENE",
      "scene_communicative_purpose": "Records the first family loss in foreign exile.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B2",
            "role_in_scene": "HUSBAND",
            "presence": "PRESENT_BECOMES_DECEASED"
          },
          {
            "being_id": "B3",
            "role_in_scene": "WIDOW",
            "presence": "PRESENT"
          },
          {
            "being_id": "B4",
            "role_in_scene": "SON",
            "presence": "PRESENT"
          },
          {
            "being_id": "B5",
            "role_in_scene": "SON",
            "presence": "PRESENT"
          }
        ]
      },

      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL2"
          }
        ]
      },

      "objects_in_scene": {
        "_note": "No persistent objects in this scene.",
        "entries": null
      },

      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; time is continuous within the Moabite sojourn established in S1.",
        "entries": null
      },

      "significant_absence": "Narrator points to no one as the cause of the death. No grief described. No funeral or mourning mentioned."
    },

    {
      "scene_id": "S3",
      "verse_range": "1:4",
      "scene_kind": "MARRIAGE_SCENE",
      "scene_communicative_purpose": "Extends the family in foreign territory across a decade.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "SON",
            "presence": "PRESENT"
          },
          {
            "being_id": "B5",
            "role_in_scene": "SON",
            "presence": "PRESENT"
          },
          {
            "being_id": "B7",
            "role_in_scene": "SOURCE_GROUP",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B8",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "PRESENT"
          },
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
        "entries": [
          {
            "place_id": "PL2"
          }
        ]
      },

      "objects_in_scene": {
        "entries": [
          {
            "object_id": "TH_TEN_YEARS_APPROXIMATELY"
          }
        ]
      },

      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; temporal setting is the continued Moabite sojourn. The duration about ten years is a content element carried in objects_in_scene, not a scene-setting frame.",
        "entries": null
      },

      "significant_absence": "No children born to either marriage in the ten years they live there; narrator gives the length but names no child."
    },

    {
      "scene_id": "S4",
      "verse_range": "1:5",
      "scene_kind": "BEREAVEMENT_SCENE",
      "scene_communicative_purpose": "Records the catastrophic emptying that closes the opening pericope.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "SON",
            "presence": "PRESENT_BECOMES_DECEASED"
          },
          {
            "being_id": "B5",
            "role_in_scene": "SON",
            "presence": "PRESENT_BECOMES_DECEASED"
          },
          {
            "being_id": "B3",
            "role_in_scene": "WIDOW",
            "presence": "PRESENT",
            "referential_form": "STRIPPED_TO_HA_ISHAH"
          },
          {
            "being_id": "B2",
            "role_in_scene": "HUSBAND",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B8",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B9",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "REFERENCED"
          }
        ]
      },

      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL2"
          }
        ]
      },

      "objects_in_scene": {
        "_note": "No persistent objects in this scene.",
        "entries": null
      },

      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; time is continuous within the Moabite sojourn.",
        "entries": null
      },

      "significant_absence": "Narrator tells of no grief, no funeral, no one left to carry on the line, and no act of God. The losses are reported and the line simply stops there."
    }
  ],

  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "1:1a",
      "proposition_kind": "TIME_ANCHOR_ESTABLISHED",
      "event_specific_slots": {
        "era_anchor_being": "B1",
        "era_time_id": "TM_PERIOD_OF_JUDGES",
        "activity_invoked_by_era_name": "JUDGING"
      },
      "inter_proposition_links": {
        "forward_link_to": "P2"
      },
      "cb_flags": ["CB_0029"],
      "figure_flags": ["FIG_0007"]
    },

    {
      "prop_id": "P2",
      "scene_link": "S1",
      "verse_anchor": "1:1a",
      "proposition_kind": "FAMINE_OCCURRED",
      "event_specific_slots": {
        "afflicted_place": "PL_LAND_OF_JUDAH",
        "afflicting_event": "O1",
        "named_doer": "NONE"
      },
      "inter_proposition_links": {
        "caused_by": "P1",
        "forward_link_to": "P3"
      },
      "cb_flags": ["CB_0028"],
      "figure_flags": ["FIG_0013"]
    },

    {
      "prop_id": "P3",
      "scene_link": "S1",
      "verse_anchor": "1:1b",
      "proposition_kind": "MIGRATED",
      "event_specific_slots": {
        "household_head": "B2",
        "accompanying_household": ["B3", "B4", "B5"],
        "origin": "PL1",
        "destination": "PL2",
        "departure_intent_marker": "CB_0030"
      },
      "inter_proposition_links": {
        "caused_by": "P2",
        "forward_link_to": "P4"
      },
      "cb_flags": ["CB_0030", "CB_0004"],
      "figure_flags": ["FIG_0013"]
    },

    {
      "prop_id": "P4",
      "scene_link": "S1",
      "verse_anchor": "1:2a",
      "proposition_kind": "NAMED",
      "event_specific_slots": {
        "naming_components": [
          {
            "named_party": "B2",
            "given_name": "Elimelech",
            "role_in_household": "HUSBAND_AND_FATHER",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "named_party": "B3",
            "given_name": "Naomi",
            "role_in_household": "WIFE_AND_MOTHER",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "named_party": "B4",
            "given_name": "Mahlon",
            "role_in_household": "FIRST_SON",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "named_party": "B5",
            "given_name": "Chilion",
            "role_in_household": "SECOND_SON",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
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
      "verse_anchor": "1:2a",
      "proposition_kind": "IDENTIFIED",
      "event_specific_slots": {
        "identified_household": ["B2", "B3", "B4", "B5"],
        "clan": "B6",
        "clan_anchor_place": "PL1"
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
      "verse_anchor": "1:2b",
      "proposition_kind": "ARRIVED_AT",
      "event_specific_slots": {
        "arrival_components": [
          {
            "action": "ARRIVED_AT",
            "arriver": "THE_FAMILY",
            "destination": "PL2",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "WERE_AT",
            "residents": "THE_FAMILY",
            "where": "PL2",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P3"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P7",
      "scene_link": "S2",
      "verse_anchor": "1:3",
      "proposition_kind": "DIED",
      "event_specific_slots": {
        "deceased": "B2",
        "referential_form_at_verse": "HUSBAND_OF_NAOMI",
        "where": "PL2",
        "named_doer": "NONE"
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
      "verse_anchor": "1:3",
      "proposition_kind": "REMAINED",
      "event_specific_slots": {
        "residual": "B3",
        "referential_form_at_verse": "SHE_PRONOMINAL",
        "remaining_with": ["B4", "B5"]
      },
      "inter_proposition_links": {
        "caused_by": "P7",
        "paired_with": "P13"
      },
      "cross_ref": "FIG_0052 opens here; closes at Proposition P13",
      "cb_flags": [],
      "figure_flags": ["FIG_0052"]
    },

    {
      "prop_id": "P9",
      "scene_link": "S3",
      "verse_anchor": "1:4a",
      "proposition_kind": "TOOK",
      "event_specific_slots": {
        "marriage_components": [
          {
            "action": "TOOK_AS_WIFE",
            "taker": "B4",
            "wife_taken": "B?",
            "wife_origin_pool": "B7",
            "for_self_marker": "OWN_INITIATIVE",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "TOOK_AS_WIFE",
            "taker": "B5",
            "wife_taken": "B?",
            "wife_origin_pool": "B7",
            "for_self_marker": "OWN_INITIATIVE",
            "speech_act": "STATES_AS_TRUE"
          }
        ],
        "where": "PL2"
      },
      "inter_proposition_links": {
        "forward_link_to": "P10"
      },
      "cb_flags": ["CB_0004"],
      "figure_flags": []
    },

    {
      "prop_id": "P10",
      "scene_link": "S3",
      "verse_anchor": "1:4a",
      "proposition_kind": "NAMED",
      "event_specific_slots": {
        "naming_order": "PARALLEL_TWO_BRIDES",
        "naming_components": [
          {
            "named_party": "B8",
            "given_name": "Orpah",
            "role_in_household": "FIRST_NAMED_BRIDE",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "named_party": "B9",
            "given_name": "Ruth",
            "role_in_household": "SECOND_NAMED_BRIDE",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "paired_with": "P4"
      },
      "cb_flags": [],
      "figure_flags": ["FIG_0001"]
    },

    {
      "prop_id": "P11",
      "scene_link": "S3",
      "verse_anchor": "1:4b",
      "proposition_kind": "DWELT_AT",
      "event_specific_slots": {
        "residents": "THE_FAMILY",
        "where": "PL2",
        "duration": "TH_TEN_YEARS_APPROXIMATELY",
        "duration_exactness": "APPROXIMATE"
      },
      "inter_proposition_links": {
        "caused_by": "P6"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P12",
      "scene_link": "S4",
      "verse_anchor": "1:5a",
      "proposition_kind": "DIED",
      "event_specific_slots": {
        "deceased": ["B4", "B5"],
        "where": "PL2",
        "named_doer": "NONE"
      },
      "inter_proposition_links": {
        "paired_with": "P7",
        "forward_link_to": "P13"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P13",
      "scene_link": "S4",
      "verse_anchor": "1:5b",
      "proposition_kind": "REMAINED",
      "event_specific_slots": {
        "residual": "B3",
        "referential_form_at_verse": "STRIPPED_TO_HA_ISHAH",
        "bereft_of_listing": [
          {
            "loss_target": ["B4", "B5"],
            "referential_form": "YELADIM_TENDER_CHILD",
            "list_position": "FIRST",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "loss_target": "B2",
            "referential_form": "HER_HUSBAND",
            "list_position": "SECOND",
            "speech_act": "STATES_AS_TRUE"
          }
        ],
        "listing_order_form": "CHILDREN_BEFORE_HUSBAND_REVERSE_NATURAL_ORDER"
      },
      "inter_proposition_links": {
        "caused_by": "P12",
        "paired_with": "P8"
      },
      "cross_ref": "FIG_0052 closes here; opened at Proposition P8",
      "cb_flags": [],
      "figure_flags": ["FIG_0052"]
    }
  ]
}
```

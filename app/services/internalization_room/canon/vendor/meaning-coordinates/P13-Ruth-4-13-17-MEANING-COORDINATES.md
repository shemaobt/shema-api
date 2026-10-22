---
type: "sta-meaning-coordinates"
pericope: "P13"
pericope-title: "Obed: the conception YHWH gives, the women's blessing, the child on Naomi's lap"
source-meaning-map: [[P13-Ruth-4-13-17]]
status: "valid"
pilot: "pilot-2"
drafter: "claude-opus-4-8 · fm-drafter prompt (see _spec/pins.json) · machine-drafted, ruled by Marcia (SC-0064 batch ruling §A–§E + arc_element, 2026-06-19); MODEL_DRAFTED_REVIEWER_RULED"
---

# P13 — Ruth 4:13-17 — MEANING_COORDINATES

> Judgment gaps filled by the SC-0063 drafter (`tripod draft --live`); the merge layer enforced the patch-only contract. NOT canon until ruled.

```json
{
  "sta_id": "ruth_pericope_13_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Ruth 4:13-17",
    "pericope_title": "Obed: the conception YHWH gives, the women's blessing, the child on Naomi's lap",
    "book_context_ref": "ruth_pilot_BCD_v0_3",
    "source_meaning_map_ref": "P13-Ruth-4-13-17",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "Pericope stays INFORMAL_CASUAL (narrator's telling). MM Section 1 marks one scene-level shift: S2 (4:14-15) the women's benediction lifts to CEREMONIAL. S3 (4:16-17), Naomi taking the child and the neighbor-women naming him, stays in the pericope-level INFORMAL_CASUAL (no override). No moment-level or framing overrides.",
      "scene_level": [
        {
          "scene_id": "S2",
          "override_value": "CEREMONIAL"
        }
      ],
      "moment_level": null
    }
  },
  "level_1": {
    "arc_elements": [
      "MARRIAGE_CONSUMMATED",
      "DIVINE_GIFT_OF_CONCEPTION",
      "BIRTH_OF_HEIR",
      "BLESSING_INVOCATION",
      "EMPTYING_REVERSED",
      "COMMUNAL_NAMING",
      "NARRATOR_FRAMING_CLOSE"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "PHYSICAL_LOCATION",
      "KINSHIP_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "DIVINE_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT",
      "PRIOR_PERICOPE_CARRY_FORWARD",
      "HISTORICAL_ERA_CONTEXT"
    ],
    "tone_elements": [
      "ECONOMICAL",
      "WARM",
      "INTIMATE",
      "STILLED",
      "RISING"
    ],
    "pace_elements": [
      "BRISK",
      "SLOWED",
      "SETTLES",
      "WIDENS"
    ],
    "communicative_function_elements": [
      "CLOSES",
      "ADVANCES",
      "REACTIVATES",
      "OPENS"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "4:13",
      "scene_kind": "BIRTH_SCENE",
      "scene_communicative_purpose": "Tells the marriage and the birth in a single swift line, with YHWH's giving of conception at its center.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B13",
            "role_in_scene": "HUSBAND",
            "presence": "PRESENT"
          },
          {
            "being_id": "B9",
            "role_in_scene": "WIFE",
            "presence": "PRESENT"
          },
          {
            "being_id": "B10",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B?",
            "role_in_scene": "SON",
            "presence": "PRESENT"
          }
        ]
      },
      "places_in_scene": {
        "_note": "the text names no place in this verse (per meaning map)",
        "entries": null
      },
      "objects_in_scene": {
        "_note": "no object or concept is named in this verse (per meaning map)",
        "entries": null
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "The narrator tells no wedding, no span of time, and nothing of the birth itself — only the swift verbs. The child is not named in this verse."
    },
    {
      "scene_id": "S2",
      "verse_range": "4:14-15",
      "scene_kind": "BLESSING_SCENE",
      "scene_communicative_purpose": "The women speak to Naomi and bless YHWH, who has not left her without a redeemer today; the one born will be a restorer of her life and a sustainer of her old age, and her daughter-in-law, who loves her, is better to her than seven sons.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B24",
            "role_in_scene": "TOWNSWOMEN",
            "presence": "PRESENT"
          },
          {
            "being_id": "B3",
            "role_in_scene": "GRANDMOTHER",
            "presence": "PRESENT"
          },
          {
            "being_id": "B10",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B?",
            "role_in_scene": "REDEEMER_KIN",
            "presence": "REFERENCED",
            "referential_form": "REDEEMER_GOEL"
          },
          {
            "being_id": "B9",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "REFERENCED",
            "referential_form": "DAUGHTER_IN_LAW_WHO_LOVES_YOU"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL_ISRAEL"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0008"
          },
          {
            "object_id": "CB_0001"
          },
          {
            "object_id": "CB_0005"
          },
          {
            "object_id": "CB_0046"
          }
        ]
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "The women speak to Naomi; they say nothing to Ruth or to Boaz, and Boaz is not mentioned. They do not say Ruth's name or call her the Moabite; she is \"your daughter-in-law who loves you\"."
    },
    {
      "scene_id": "S3",
      "verse_range": "4:16-17",
      "scene_kind": "NAMING_SCENE",
      "scene_communicative_purpose": "Naomi takes the child to her bosom and becomes his nurse; the neighbor-women call a name — a son has been born to Naomi — and call him Obed; and the narrator names Obed's son and grandson, Jesse and David.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B3",
            "role_in_scene": "GRANDMOTHER",
            "presence": "PRESENT"
          },
          {
            "being_id": "B24",
            "role_in_scene": "TOWNSWOMEN",
            "presence": "PRESENT"
          },
          {
            "being_id": "B25",
            "role_in_scene": "ANCESTOR",
            "presence": "PRESENT"
          },
          {
            "being_id": "B26",
            "role_in_scene": "LINEAGE_REFERENT",
            "presence": "REFERENCED"
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
            "object_id": "CB_0047"
          },
          {
            "object_id": "CB_0048"
          }
        ]
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "Ruth is not mentioned in this scene; the neighbor-women say a son has been born to Naomi. Boaz is not mentioned after 4:13 in this passage. The neighbor-women give the child his name; the text does not say why the name Obed. The narrator names David and says nothing more about him."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "4:13a",
      "proposition_kind": "TOOK",
      "event_specific_slots": {
        "taker": "B13",
        "wife_taken": "B9",
        "consummation_marker": "CAME_TO_HER"
      },
      "inter_proposition_links": {
        "forward_link_to": "P2"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0180",
        "FIG_0188"
      ]
    },
    {
      "prop_id": "P2",
      "scene_link": "S1",
      "verse_anchor": "4:13b",
      "proposition_kind": "GAVE",
      "event_specific_slots": {
        "giver": "B10",
        "gift_given": "CONCEPTION",
        "given_to": "B9"
      },
      "inter_proposition_links": {
        "caused_by": "P1",
        "forward_link_to": "P3"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0180",
        "FIG_0194"
      ]
    },
    {
      "prop_id": "P3",
      "scene_link": "S1",
      "verse_anchor": "4:13c",
      "proposition_kind": "BORE",
      "event_specific_slots": {
        "bearer": "B9",
        "child_borne": "B?",
        "child_sex": "SON"
      },
      "inter_proposition_links": {
        "caused_by": "P2",
        "forward_link_to": "P4"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0180"
      ]
    },
    {
      "prop_id": "P4",
      "scene_link": "S2",
      "verse_anchor": "4:14a",
      "proposition_kind": "BLESSING",
      "event_specific_slots": {
        "blessing_speakers": "B24",
        "blessing_addressee": "B3",
        "invoked_deity": "B10",
        "redeemer": "B?",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P3",
        "forward_link_to": "P5"
      },
      "cb_flags": [
        "CB_0001",
        "CB_0008"
      ],
      "figure_flags": [
        "FIG_0142",
        "FIG_0014",
        "FIG_0187"
      ]
    },
    {
      "prop_id": "P5",
      "scene_link": "S2",
      "verse_anchor": "4:14b",
      "proposition_kind": "BLESSING",
      "event_specific_slots": {
        "wish_speakers": "B24",
        "name_bearer": "B?",
        "where": "PL_ISRAEL",
        "speech_act": "WISHES_FOR_THIRD_PARTY"
      },
      "inter_proposition_links": {
        "forward_link_to": "P6"
      },
      "cb_flags": [
        "CB_0005"
      ],
      "figure_flags": [
        "FIG_0184"
      ]
    },
    {
      "prop_id": "P6",
      "scene_link": "S2",
      "verse_anchor": "4:15a",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "declared_speakers": "B24",
        "child": "B?",
        "born_for": "B3",
        "speech_act": "STATES_AS_TRUE"
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
      "verse_anchor": "4:15b",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "declared_speakers": "B24",
        "praised_bearer": "B9",
        "bearer_referential_form": "DAUGHTER_IN_LAW_WHO_LOVES_YOU",
        "child_borne": "B?",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P8"
      },
      "cb_flags": [
        "CB_0046"
      ],
      "figure_flags": [
        "FIG_0183"
      ]
    },
    {
      "prop_id": "P8",
      "scene_link": "S3",
      "verse_anchor": "4:16a",
      "proposition_kind": "TOOK",
      "event_specific_slots": {
        "taker": "B3",
        "child_taken": "B25",
        "placement": "ON_BOSOM"
      },
      "inter_proposition_links": {
        "forward_link_to": "P9"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0185",
        "FIG_0016"
      ]
    },
    {
      "prop_id": "P9",
      "scene_link": "S3",
      "verse_anchor": "4:16b",
      "proposition_kind": "IDENTIFIED",
      "event_specific_slots": {
        "caregiver": "B3",
        "assumed_role": "NURSE_OMENET",
        "for_child": "B25"
      },
      "inter_proposition_links": {
        "caused_by": "P8",
        "forward_link_to": "P10"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0186"
      ]
    },
    {
      "prop_id": "P10",
      "scene_link": "S3",
      "verse_anchor": "4:17a",
      "proposition_kind": "NAMED",
      "event_specific_slots": {
        "naming_speakers": "B24",
        "reckoned_to": "B3",
        "named_child": "B25",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P11"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0181",
        "FIG_0182"
      ]
    },
    {
      "prop_id": "P11",
      "scene_link": "S3",
      "verse_anchor": "4:17b",
      "proposition_kind": "NAMED",
      "event_specific_slots": {
        "naming_speakers": "B24",
        "name_given": "Obed",
        "named_child": "B25",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P10",
        "forward_link_to": "P12"
      },
      "cb_flags": [
        "CB_0047"
      ],
      "figure_flags": [
        "FIG_0182"
      ]
    },
    {
      "prop_id": "P12",
      "scene_link": "S3",
      "verse_anchor": "4:17c",
      "proposition_kind": "NARRATOR_FRAME",
      "event_specific_slots": {
        "narrator_genealogical_reach": [
          {
            "father": "B25",
            "father_name": "Obed",
            "son_named": "Jesse",
            "son_id": "B26",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "father_named": "Jesse",
            "son_named": "David",
            "son_id": "B26",
            "speech_act": "STATES_AS_TRUE"
          }
        ],
        "narrator_vantage": "LATER_TIME"
      },
      "inter_proposition_links": {},
      "cb_flags": [
        "CB_0048"
      ],
      "figure_flags": [
        "FIG_0182",
        "FIG_0192",
        "FIG_0189",
        "FIG_0007"
      ]
    }
  ]
}
```

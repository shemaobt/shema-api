---
type: "sta-meaning-coordinates"
pericope: "P12"
pericope-title: "You are witnesses this day: the names spoken and the gate's blessing"
source-meaning-map: [[P12-Ruth-4-9-12]]
status: "valid"
pilot: "pilot-2"
drafter: "claude-opus-4-8 · fm-drafter prompt (see _spec/pins.json) · machine-drafted, ruled by Marcia (SC-0064 batch ruling §A–§E + arc_element, 2026-06-19); MODEL_DRAFTED_REVIEWER_RULED"
---

# P12 — Ruth 4:9-12 — MEANING_COORDINATES

> Judgment gaps filled by the SC-0063 drafter (`tripod draft --live`); the merge layer enforced the patch-only contract. NOT canon until ruled.

```json
{
  "sta_id": "ruth_pericope_12_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Ruth 4:9-12",
    "pericope_title": "You are witnesses this day: the names spoken and the gate's blessing",
    "book_context_ref": "ruth_pilot_BCD_v0_3",
    "source_meaning_map_ref": "P12-Ruth-4-9-12",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "Scene-level register shifts per MM Section 1 multi-level tagging: S1 (Boaz's attestation declaration, 4:9-10) FORMAL_OFFICIAL; S2 (people's/elders' blessing, 4:11-12) CEREMONIAL. Pericope value stays INFORMAL_CASUAL (the narrator's framing of the two speeches). No NARRATIVE_FRAMING moment overrides.",
      "scene_level": [
        {
          "scene_id": "S1",
          "override_value": "FORMAL_OFFICIAL"
        },
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
      "PUBLIC_REDEMPTION_DECLARATION",
      "DEAD_NAME_RAISED",
      "COMMUNITY_WITNESS_ATTESTATION",
      "BLESSING_INVOCATION"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "PHYSICAL_LOCATION",
      "KINSHIP_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT",
      "DIVINE_CONTEXT",
      "PRIOR_PERICOPE_CARRY_FORWARD",
      "HISTORICAL_ERA_CONTEXT"
    ],
    "tone_elements": [
      "DECLARATIVE",
      "WEIGHTED",
      "RISING",
      "ANTICIPATORY"
    ],
    "pace_elements": [
      "DELIBERATE",
      "BRISK",
      "WIDENS",
      "RISES"
    ],
    "communicative_function_elements": [
      "CLOSES",
      "REACTIVATES",
      "ADVANCES",
      "STAGES",
      "PLANTS"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "4:9-10",
      "scene_kind": "RATIFICATION_SCENE",
      "scene_communicative_purpose": "Makes the purchase public before witnesses: all that was Elimelech's, Chilion's and Mahlon's, from Naomi's hand, and Ruth the Moabite, the wife of Mahlon, to be Boaz's wife — to raise up the name of the dead upon his inheritance. Here, for the first time, the story says whose wife Ruth was.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B13",
            "role_in_scene": "REDEEMER_KIN",
            "presence": "PRESENT"
          },
          {
            "being_id": "B20",
            "role_in_scene": "WITNESSING_ELDERS",
            "presence": "PRESENT"
          },
          {
            "being_id": "B21",
            "role_in_scene": "WITNESSING_ASSEMBLY",
            "presence": "PRESENT"
          },
          {
            "being_id": "B2",
            "role_in_scene": "DECEASED_KIN",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B5",
            "role_in_scene": "SON",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B4",
            "role_in_scene": "HUSBAND",
            "presence": "REFERENCED",
            "referential_form": "HUSBAND_OF_RUTH"
          },
          {
            "being_id": "B3",
            "role_in_scene": "WIDOW",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B9",
            "role_in_scene": "WIDOW",
            "presence": "REFERENCED",
            "referential_form": "RUTH_THE_MOABITESS"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL7"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0001"
          },
          {
            "object_id": "CB_0005"
          },
          {
            "object_id": "CB_0002"
          },
          {
            "object_id": "CB_0039"
          },
          {
            "object_id": "CB_0003"
          },
          {
            "object_id": "CB_0004"
          },
          {
            "object_id": "CB_0006"
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
      "significant_absence": "Neither Ruth nor Naomi speaks. At the gate no one speaks of the night at the threshing floor. No one says the name of God in Boaz's declaration."
    },
    {
      "scene_id": "S2",
      "verse_range": "4:11-12",
      "scene_kind": "BLESSING_SCENE",
      "scene_communicative_purpose": "All the people at the gate and the elders answer: we are witnesses. Then they bless: may YHWH make the woman coming into Boaz's house like Rachel and Leah; may Boaz do worthily in Ephrathah and call out a name in Bethlehem; may his house be like the house of Perez, from the seed YHWH will give him from this young woman. In the blessing the name of God is said, which no one said in the proceeding.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B21",
            "role_in_scene": "WITNESSING_ASSEMBLY",
            "presence": "PRESENT"
          },
          {
            "being_id": "B20",
            "role_in_scene": "WITNESSING_ELDERS",
            "presence": "PRESENT"
          },
          {
            "being_id": "B10",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B13",
            "role_in_scene": "REDEEMER_KIN",
            "presence": "PRESENT"
          },
          {
            "being_id": "B9",
            "role_in_scene": "WIFE",
            "presence": "REFERENCED",
            "referential_form": "WOMAN_COMING_INTO_HOUSE"
          },
          {
            "being_id": "B22",
            "role_in_scene": "ANCESTOR",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B27",
            "role_in_scene": "ANCESTOR",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B23",
            "role_in_scene": "ANCESTOR",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B30",
            "role_in_scene": "ANCESTOR",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL7"
          },
          {
            "place_id": "PL_ISRAEL"
          },
          {
            "place_id": "PL8"
          },
          {
            "place_id": "PL1"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0008"
          },
          {
            "object_id": "CB_0010"
          },
          {
            "object_id": "CB_0049"
          }
        ]
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "Neither Ruth nor Naomi speaks. The seed is asked for, not told as given. The blessing tells no more of Rachel and Leah, of Tamar, Judah and Perez, than it says here."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "4:9a",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "declarer": "B13",
        "addressed_elders": "B20",
        "addressed_assembly": "B21",
        "summons_day": "TM_TODAY",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P2"
      },
      "cb_flags": [
        "CB_0006"
      ],
      "figure_flags": [
        "FIG_0172",
        "FIG_0005"
      ]
    },
    {
      "prop_id": "P2",
      "scene_link": "S1",
      "verse_anchor": "4:9b",
      "proposition_kind": "ACQUIRED",
      "event_specific_slots": {
        "acquirer": "B13",
        "acquired_estate_of": [
          "B2",
          "B5",
          "B4"
        ],
        "acquired_from": "B3",
        "acquired_from_form": "FROM_THE_HAND_OF_NAOMI",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P3",
        "caused_by": "P1"
      },
      "cb_flags": [
        "CB_0001"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P3",
      "scene_link": "S1",
      "verse_anchor": "4:10a",
      "proposition_kind": "ACQUIRED",
      "event_specific_slots": {
        "acquirer": "B13",
        "acquired_bride": "B9",
        "acquired_bride_referential_form": "RUTH_THE_MOABITE_WIFE_OF_MAHLON",
        "deceased_husband": "B4",
        "purpose_role": "TO_BE_WIFE",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P4",
        "caused_by": "P1"
      },
      "cb_flags": [
        "CB_0001",
        "CB_0002",
        "CB_0004"
      ],
      "figure_flags": [
        "FIG_0001"
      ]
    },
    {
      "prop_id": "P4",
      "scene_link": "S1",
      "verse_anchor": "4:10b",
      "proposition_kind": "NAME_PRESERVED",
      "event_specific_slots": {
        "name_raiser": "B13",
        "name_raised_of": "B4",
        "name_raised_referential_form": "SHEM_HA_MET_NAME_OF_THE_DEAD",
        "upon_inheritance": "CB_0003",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P5"
      },
      "cb_flags": [
        "CB_0005",
        "CB_0002",
        "CB_0003"
      ],
      "figure_flags": [
        "FIG_0002"
      ]
    },
    {
      "prop_id": "P5",
      "scene_link": "S1",
      "verse_anchor": "4:10c",
      "proposition_kind": "NAME_PRESERVED",
      "event_specific_slots": {
        "secured_name_of": "B4",
        "secured_name_referential_form": "SHEM_HA_MET_NAME_OF_THE_DEAD",
        "gate": "PL7",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P6",
        "caused_by": "P4"
      },
      "cb_flags": [
        "CB_0039",
        "CB_0006"
      ],
      "figure_flags": [
        "FIG_0110",
        "FIG_0003"
      ]
    },
    {
      "prop_id": "P6",
      "scene_link": "S1",
      "verse_anchor": "4:10d",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "declarer": "B13",
        "summons_day": "TM_TODAY",
        "repeats_proposition": "P1",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P7",
        "paired_with": "P1"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0172"
      ]
    },
    {
      "prop_id": "P7",
      "scene_link": "S2",
      "verse_anchor": "4:11a",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "responding_assembly": "B21",
        "responding_elders": "B20",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P8",
        "paired_with": "P6",
        "caused_by": "P6"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0171"
      ]
    },
    {
      "prop_id": "P8",
      "scene_link": "S2",
      "verse_anchor": "4:11b",
      "proposition_kind": "BLESSING",
      "event_specific_slots": {
        "blessing_speakers": [
          "B21",
          "B20"
        ],
        "invoked_deity": "B10",
        "blessing_recipients": "B9",
        "blessed_party_referential_form": "WOMAN_COMING_INTO_HOUSE",
        "likened_to_matriarchs": "B22",
        "house_built": "PL_ISRAEL",
        "blessing_content_kind": "FRUITFULNESS_LIKE_MATRIARCHS",
        "speech_act": "WISHES_FOR_THIRD_PARTY"
      },
      "inter_proposition_links": {
        "forward_link_to": "P9"
      },
      "cb_flags": [
        "CB_0008",
        "CB_0010",
        "CB_0009"
      ],
      "figure_flags": [
        "FIG_0014",
        "FIG_0004",
        "FIG_0187"
      ]
    },
    {
      "prop_id": "P9",
      "scene_link": "S2",
      "verse_anchor": "4:11c",
      "proposition_kind": "BLESSING",
      "event_specific_slots": {
        "blessing_speakers": [
          "B21",
          "B20"
        ],
        "blessing_recipients": "B13",
        "worthy_deed_place": "PL8",
        "name_proclamation_place": "PL1",
        "doubled_place_form": "EPHRATHAH_AND_BETHLEHEM",
        "speech_act": "WISHES_FOR_HEARER"
      },
      "inter_proposition_links": {
        "forward_link_to": "P10"
      },
      "cb_flags": [
        "CB_0008",
        "CB_0032"
      ],
      "figure_flags": [
        "FIG_0017"
      ]
    },
    {
      "prop_id": "P10",
      "scene_link": "S2",
      "verse_anchor": "4:12a",
      "proposition_kind": "BLESSING",
      "event_specific_slots": {
        "blessing_speakers": [
          "B21",
          "B20"
        ],
        "blessing_recipients": "B13",
        "house_likened_to": "B27",
        "model_house_form": "HOUSE_OF_PEREZ",
        "borne_by": "B23",
        "borne_to": "B30",
        "blessing_content_kind": "HOUSE_LIKE_PEREZ",
        "speech_act": "WISHES_FOR_HEARER"
      },
      "inter_proposition_links": {
        "forward_link_to": "P11"
      },
      "cb_flags": [
        "CB_0008",
        "CB_0049"
      ],
      "figure_flags": [
        "FIG_0170",
        "FIG_0191"
      ]
    },
    {
      "prop_id": "P11",
      "scene_link": "S2",
      "verse_anchor": "4:12b",
      "proposition_kind": "BLESSING",
      "event_specific_slots": {
        "blessing_speakers": [
          "B21",
          "B20"
        ],
        "seed_giver": "B10",
        "seed_given_to": "B13",
        "seed_from": "B9",
        "seed_from_referential_form": "THIS_YOUNG_WOMAN",
        "speech_act": "WISHES_FOR_HEARER"
      },
      "inter_proposition_links": {
        "back_reference_to_proposition": "P8"
      },
      "cb_flags": [
        "CB_0009"
      ],
      "figure_flags": []
    }
  ]
}
```

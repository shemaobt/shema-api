---
type: "sta-meaning-coordinates"
pericope: "E14"
pericope-title: "The counter-decree: the Jews granted the right to defend their lives, and the turn from dread to gladness"
source-meaning-map: [[E14-Esther-8-9-17]]
status: "valid"
pilot: "pilot-2"
---

# E14 — Esther 8:9–17 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "esther_pericope_14_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",

  "header": {
    "bcv": "Esther 8:9-17",
    "pericope_title": "The counter-decree: the Jews granted the right to defend their lives, and the turn from dread to gladness",
    "book_context_ref": "esther_pilot_BCD_v0_1",
    "source_meaning_map_ref": "E14-Esther-8-9-17",
    "source_language": "Biblical Hebrew"
  },

  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "One scene-level FORMAL_OFFICIAL override on Scene 2 (the decree's own voiced/granted words, v.11-12); the v.13 publication formula reverts to INFORMAL_CASUAL (narrator's report, not the decree's voiced words). Ruled by Marcia 2026-06-27.",
      "scene_level": [
        {
          "scene_id": "S2",
          "override_value": "FORMAL_OFFICIAL",
          "genre_override": null,
          "genre_group_override": null
        }
      ],
      "moment_level": null
    }
  },

  "level_1": {
    "arc_elements": [
      "ROYAL_DECREE",
      "FAVOR_GRANTED",
      "REVERSAL_PROCLAIMED",
      "PUBLIC_HONOR",
      "GREAT_REVERSAL"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "PHYSICAL_LOCATION",
      "TEMPORAL_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT"
    ],
    "tone_elements": [
      "PROCEDURAL",
      "HURRIED",
      "JUBILANT",
      "BRIGHTENING",
      "SHADOWED_BY_FEAR"
    ],
    "pace_elements": [
      "BRISK",
      "RISES",
      "WIDENS"
    ],
    "communicative_function_elements": [
      "ANNOUNCES",
      "GRANTS",
      "PUBLISHES",
      "REVERSES",
      "ADVANCES"
    ]
  },

  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "8:9-10",
      "scene_kind": "DECREE_SCENE",
      "scene_communicative_purpose": "Shows the imperial writing-machine turning over again — same scribes, ring, couriers, and reach — now to issue the rescue.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B1",
            "role_in_scene": "SCRIBES",
            "presence": "PRESENT"
          },
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B17",
            "role_in_scene": "PEOPLE",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B21",
            "role_in_scene": "SCRIBES",
            "presence": "PRESENT"
          },
          {
            "being_id": "B19",
            "role_in_scene": "PROVINCIAL_OFFICIALS",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B22",
            "role_in_scene": "COURIERS",
            "presence": "PRESENT"
          }
        ]
      },

      "places_in_scene": {
        "_note": "The 127 provinces (I5) is an institution-span carried in L3 slots (P2.province_count_ref), not a scene place; the scene places are the far frontiers India and Cush.",
        "entries": [
          {
            "place_id": "PL2"
          },
          {
            "place_id": "PL3"
          }
        ]
      },

      "objects_in_scene": {
        "entries": [
          {
            "object_id": "TH_EDICT"
          },
          {
            "object_id": "TH_SIGNET_RING"
          },
          {
            "object_id": "TH_ROYAL_HORSE"
          }
        ]
      },

      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_SIVAN"
          }
        ]
      },

      "significant_absence": "No prayer, no thanksgiving, no word of God accompanies the rescue's writing — the deliverance is enacted purely as Persian law, by scribe and seal and horse. And there is no act of revoking the first decree: the empire cannot unwrite it, only write against it. God is unnamed at the very moment His people are being saved."
    },

    {
      "scene_id": "S2",
      "verse_range": "8:11-13",
      "scene_kind": "DECREE_SCENE",
      "scene_communicative_purpose": "Voices the legal grant itself — the right to live and defend, set on the very day of the threatened slaughter — the death-decree turned inside out.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B17",
            "role_in_scene": "HONORED_ONE",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B20",
            "role_in_scene": "SLAIN_FOES",
            "presence": "REFERENCED"
          }
        ]
      },

      "places_in_scene": {
        "_note": "The grant reaches every city across the 127 provinces (I5, an institution-span carried in L3 slots P6/P8); no discrete registry place is staged in the decree's own words.",
        "entries": null
      },

      "objects_in_scene": {
        "_note": "The law (I2) and the edict-copy (TH_EDICT) are the published instruments, carried in L3 slots (P9); the granted right itself is a permitted action (P6), not a scene object.",
        "entries": [
          {
            "object_id": "TH_EDICT"
          }
        ]
      },

      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_ADAR"
          }
        ]
      },

      "significant_absence": "The grant gives leave to plunder the enemy's goods — but the narrative will later note the Jews do not lay hands on the plunder. Here the permission stands, the restraint unstated. And though the grant is the rescue of God's people, no divine warrant is claimed; the standing is granted by the king alone, God unnamed."
    },

    {
      "scene_id": "S3",
      "verse_range": "8:14-15",
      "scene_kind": "PROCLAMATION_SCENE",
      "scene_communicative_purpose": "Shows the rescue racing outward and its human face: the once-mourning Mordecai robed in royal honour, and the capital's cheer.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B22",
            "role_in_scene": "COURIERS",
            "presence": "PRESENT"
          },
          {
            "being_id": "B1",
            "role_in_scene": "HONORED_ONE",
            "presence": "PRESENT",
            "referential_form": "MORDECAI_IN_ROYAL_ROBES"
          },
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "REFERENCED"
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
        "_note": "The law (I2) given in Susa is an institution carried in L3 slots (P12); the scene objects are Mordecai's royal robe and the couriers' swift steeds.",
        "entries": [
          {
            "object_id": "TH_ROYAL_ROBE"
          },
          {
            "object_id": "TH_ROYAL_HORSE"
          }
        ]
      },

      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; the couriers' ride and Mordecai's exit follow directly on the issuing of the decree dated in S1.",
        "entries": null
      },

      "significant_absence": "The city that cheers now is the same Susa that, when the first decree went out, was thrown into confusion — but its earlier dismay is left for the reader to remember; the verse names only the joy. And no thanks is lifted to heaven for the rescue; the rejoicing is the city's own, God unnamed."
    },

    {
      "scene_id": "S4",
      "verse_range": "8:16-17",
      "scene_kind": "REVERSAL_SCENE",
      "scene_communicative_purpose": "Shows the reversal spreading to the whole realm — dread turned to light and feasting — and its shadow: outsiders joining the Jews out of fear.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B17",
            "role_in_scene": "DELIVERED_PEOPLE",
            "presence": "PRESENT"
          },
          {
            "being_id": "B17",
            "role_in_scene": "THREATENED_PEOPLE",
            "presence": "REFERENCED",
            "referential_form": "THE_DREAD_OF_THE_JEWS"
          }
        ]
      },

      "places_in_scene": {
        "_note": "The gladness spreads across every province (I5, an institution-span carried in L3 slots P16); no discrete registry place is staged.",
        "entries": null
      },

      "objects_in_scene": {
        "_note": "The law (I2) and the feast (I1) are institutions carried in L3 slots (P16); the arriving edict (TH_EDICT) is the scene object that triggers the local rejoicing.",
        "entries": [
          {
            "object_id": "TH_EDICT"
          }
        ]
      },

      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; the realm-wide gladness follows directly on the decree's arrival.",
        "entries": null
      },

      "significant_absence": "The peoples become Jews out of dread, not faith — the text says fear, not belief, and names no act of God behind that fear. And the Jews' joy is named with four heaped nouns, yet no thanksgiving to the One who delivered them; even at the height of relief, the book keeps its silence about God."
    }
  ],

  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "8:9",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "summoner": "B1",
        "summoned": "B21",
        "summoned_of_whom": "B4",
        "time_anchor": "that_time",
        "anchor_month": "TM_SIVAN",
        "month_ordinal": "third",
        "day_of_month": "twenty_third"
      },
      "inter_proposition_links": {
        "forward_link_to": "P2"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P2",
      "scene_link": "S1",
      "verse_anchor": "8:9",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "decree_writ": "TH_EDICT",
        "commander": "B1",
        "writing_conformity": "AS_COMMANDED",
        "addressed_to": ["B17", "B19"],
        "official_span": "the_provinces",
        "span_origin": "PL2",
        "span_terminus": "PL3",
        "province_count": "127",
        "per_province_form": "OWN_SCRIPT",
        "per_people_form": "OWN_TONGUE",
        "to_jews_form": ["OWN_SCRIPT", "OWN_TONGUE"]
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
      "verse_anchor": "8:10",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "writer": "B1",
        "name_invoked": "B4",
        "name_capacity": "KING"
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
      "scene_link": "S1",
      "verse_anchor": "8:10",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "sealer": "B1",
        "sealing_instrument": "TH_SIGNET_RING",
        "ring_of_whom": "B4"
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
      "scene_link": "S1",
      "verse_anchor": "8:10",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "sender": "B1",
        "dispatched_edict": "TH_EDICT",
        "carriers": "B22",
        "carriers_mount": "TH_ROYAL_HORSE",
        "mount_quality": "SWIFT_STEEDS",
        "mount_breeding": "ROYAL_STUD"
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
      "verse_anchor": "8:11",
      "proposition_kind": "GRANTED",
      "status": "PERMITTED",
      "event_specific_slots": {
        "grant_components": [
          {
            "action": "GAVE",
            "granter": "B4",
            "grantee": "B17",
            "grant_scope": "every_city",
            "speech_act": "PRESCRIBES_AS_LAW"
          },
          {
            "action": "ASSEMBLE",
            "permitted_party": "B17",
            "status": "PERMITTED",
            "speech_act": "PRESCRIBES_AS_LAW"
          },
          {
            "action": "STAND_FOR_LIVES",
            "permitted_party": "B17",
            "stood_for": "their_lives",
            "status": "PERMITTED",
            "speech_act": "PRESCRIBES_AS_LAW"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P2",
        "forward_link_to": "P7"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P7",
      "scene_link": "S2",
      "verse_anchor": "8:11",
      "proposition_kind": "GRANTED",
      "status": "PERMITTED",
      "event_specific_slots": {
        "grantee": "B17",
        "leave_components": [
          {
            "action": "DESTROY",
            "permitted_party": "B17",
            "target": "B20",
            "status": "PERMITTED",
            "speech_act": "PRESCRIBES_AS_LAW"
          },
          {
            "action": "KILL",
            "permitted_party": "B17",
            "target": "B20",
            "status": "PERMITTED",
            "speech_act": "PRESCRIBES_AS_LAW"
          },
          {
            "action": "ANNIHILATE",
            "permitted_party": "B17",
            "target": "B20",
            "target_extent": ["children", "women"],
            "status": "PERMITTED",
            "speech_act": "PRESCRIBES_AS_LAW"
          },
          {
            "action": "PLUNDER",
            "permitted_party": "B17",
            "plundered_goods": "their_goods",
            "status": "PERMITTED",
            "speech_act": "PRESCRIBES_AS_LAW"
          }
        ],
        "target_qualifier": ["armed_force", "a_people", "a_province"]
      },
      "inter_proposition_links": {
        "content_of": "P6",
        "condition_of": "P18",
        "forward_link_to": "P8"
      },
      "cross_ref": "The leave to destroy is conditional: licensed only against any force that attacks them (the attack-condition rides as condition P18).",
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P18",
      "scene_link": "S2",
      "verse_anchor": "8:11",
      "proposition_kind": "DECLARED",
      "status": "NORM",
      "event_specific_slots": {
        "attacker": "B20",
        "attacked": "B17"
      },
      "inter_proposition_links": {
        "condition_of": "P7"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P8",
      "scene_link": "S2",
      "verse_anchor": "8:12",
      "proposition_kind": "DAY_APPOINTED",
      "status": "FORESEEN",
      "event_specific_slots": {
        "appointed_span": "one_day",
        "appointed_scope": "the_provinces",
        "scope_sovereign": "B4",
        "appointed_day": "thirteenth",
        "appointed_month": "TM_ADAR",
        "month_ordinal": "twelfth"
      },
      "inter_proposition_links": {
        "content_of": "P6"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P9",
      "scene_link": "S2",
      "verse_anchor": "8:13",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "published_copy": "TH_EDICT",
        "copy_of": "the_writing",
        "given_as": "law",
        "publication_scope": "every_province",
        "disclosure": "PUBLISHED",
        "disclosed_to": "all_peoples"
      },
      "inter_proposition_links": {
        "forward_link_to": "P10"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P10",
      "scene_link": "S2",
      "verse_anchor": "8:13",
      "proposition_kind": "READIED_FOR_DEFENSE",
      "status": "FORESEEN",
      "event_specific_slots": {
        "readied_party": "B17",
        "readied_for": "that_day",
        "readied_to": "avenge_themselves",
        "avenged_on": "B20"
      },
      "inter_proposition_links": {
        "purpose_of": "P9"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P11",
      "scene_link": "S3",
      "verse_anchor": "8:14",
      "proposition_kind": "WENT_OUT",
      "event_specific_slots": {
        "departer": "B22",
        "departer_mount": "TH_ROYAL_HORSE",
        "departure_manner": ["HURRIED", "PRESSED"],
        "driven_by": "the_kings_word"
      },
      "inter_proposition_links": {
        "caused_by": "P5",
        "forward_link_to": "P12"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P12",
      "scene_link": "S3",
      "verse_anchor": "8:14",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "given_law": "law",
        "given_at": "PL1",
        "place_qualifier": "the_citadel"
      },
      "inter_proposition_links": {
        "forward_link_to": "P13"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P13",
      "scene_link": "S3",
      "verse_anchor": "8:15",
      "proposition_kind": "DEPARTED",
      "event_specific_slots": {
        "departer": "B1",
        "departed_from_before": "B4",
        "donned_robe": "TH_ROYAL_ROBE",
        "robe_quality": "ROYAL",
        "robe_colors": ["blue", "white"],
        "donned_crown": "a_crown",
        "crown_material": "gold",
        "crown_size": "great",
        "donned_mantle": "a_mantle",
        "mantle_material": ["fine_linen", "purple"]
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
      "verse_anchor": "8:15",
      "proposition_kind": "REJOICED",
      "event_specific_slots": {
        "rejoicing_components": [
          {
            "action": "CRIED",
            "rejoicer": "PL1",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "REJOICED",
            "rejoicer": "PL1",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P13"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P15",
      "scene_link": "S4",
      "verse_anchor": "8:16",
      "proposition_kind": "GRANTED",
      "event_specific_slots": {
        "reversal_receiver": "B17",
        "received_state": ["light", "gladness", "joy", "honour"]
      },
      "inter_proposition_links": {
        "caused_by": "P9",
        "forward_link_to": "P16"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P16",
      "scene_link": "S4",
      "verse_anchor": "8:17",
      "proposition_kind": "GLADNESS_SPREAD",
      "event_specific_slots": {
        "gladness_scope": ["every_province", "every_city", "every_place"],
        "reached_by": ["TH_EDICT", "law"],
        "rejoicing_party": "B17",
        "gladness_state": ["gladness", "joy"],
        "celebration_feast": "a_feast",
        "celebration_marker": "a_good_day"
      },
      "inter_proposition_links": {
        "caused_by": "P15",
        "forward_link_to": "P17"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P17",
      "scene_link": "S4",
      "verse_anchor": "8:17",
      "proposition_kind": "BECAME_JEWS",
      "event_specific_slots": {
        "joiners_quantity": "many",
        "joiners_drawn_from": "the_peoples",
        "joiners_origin": "the_land",
        "joining_cause": "dread",
        "dread_of": "B17",
        "dread_fallen_on": "the_peoples"
      },
      "inter_proposition_links": {
        "caused_by": "P15"
      },
      "cb_flags": [],
      "figure_flags": []
    }
  ]
}
```

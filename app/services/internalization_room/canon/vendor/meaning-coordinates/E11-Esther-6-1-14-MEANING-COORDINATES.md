---
type: "sta-meaning-coordinates"
pericope: "E11"
pericope-title: "The sleepless night and the reversal: Haman honours Mordecai"
source-meaning-map: [[E11-Esther-6-1-14]]
status: "valid"
pilot: "pilot-2"
---

# E11 — Esther 6:1–14 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "esther_pericope_11_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",

  "header": {
    "bcv": "Esther 6:1-14",
    "pericope_title": "The sleepless night and the reversal: Haman honours Mordecai",
    "book_context_ref": "esther_pilot_BCD_v0_1",
    "source_meaning_map_ref": "E11-Esther-6-1-14",
    "source_language": "Biblical Hebrew"
  },

  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "No override. The whole pericope is INFORMAL_CASUAL — the plain, fast storyteller's voice. There is heavy quoted dialogue (the king's questions, Haman's prescription, the king's command, the household's omen), but quoted speech inside narration does not lift the register. No edict is voiced or written word-for-word here: the chronicle is summarised, and Haman's prescription for honour is private court-advice spoken to the king's face, not a promulgated law — so FORMAL_OFFICIAL does not apply (and the prescription is tagged ADVISES_COURSE_OF_ACTION, not PRESCRIBES_AS_LAW). The COMMUNITY_MEMORY framing-lift is reserved for the book's open and close and does not apply here.",
      "scene_level": null,
      "moment_level": null
    }
  },

  "level_1": {
    "arc_elements": [
      "SLEEPLESSNESS",
      "LOYALTY_REMEMBERED",
      "ENEMY_ARRIVES",
      "CROSS_PURPOSED_QUESTION",
      "SELF_INCRIMINATING_PRESCRIPTION",
      "ROYAL_DECREE",
      "ENEMY_MADE_HERALD",
      "FLIGHT_IN_SHAME",
      "VERDICT_OF_FALL"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "PHYSICAL_LOCATION",
      "KINSHIP_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT",
      "TEMPORAL_CONTEXT"
    ],
    "tone_elements": [
      "TAUT",
      "QUIETLY_DELIGHTED",
      "IRONIC",
      "RISING",
      "GRAVE_BENEATH_THE_COMEDY"
    ],
    "pace_elements": [
      "BRISK",
      "OVERLAPPING",
      "BREAKING_TO_OPEN_REVERSAL"
    ],
    "communicative_function_elements": [
      "TURNS",
      "PAYS_OFF",
      "SPRINGS_IRONY",
      "REVERSES",
      "PRONOUNCES_VERDICT"
    ]
  },

  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "6:1-3",
      "scene_kind": "SLEEPLESS_NIGHT_SCENE",
      "scene_communicative_purpose": "Sets up the reversal: a sleepless king, the chronicle read, Mordecai's unrewarded loyalty surfaced at the decisive moment.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT"
          },
          {
            "being_id": "B1",
            "role_in_scene": "GATE_SITTER",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B11",
            "role_in_scene": "CONSPIRATOR",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B12",
            "role_in_scene": "CONSPIRATOR",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B18",
            "role_in_scene": "ADVISERS",
            "presence": "PRESENT"
          }
        ]
      },

      "places_in_scene": {
        "_note": "No registry place is invoked in this scene; the action is the implied royal bedchamber / court, carried as descriptive scene-content, not a place code.",
        "entries": null
      },

      "objects_in_scene": {
        "entries": [
          {
            "object_id": "TH_ANNALS"
          }
        ]
      },

      "times_in_scene": {
        "_note": "Scene-content time is the relative day-reference 'that night', not a registered TM_ code; carried as a bare atom in the proposition slots.",
        "entries": null
      },

      "significant_absence": "No reason is given for the king's sleeplessness — the narrator simply records that sleep fled, and never says who or what drove it off. The whole turn hangs on a \"chance\" the book pointedly leaves unexplained: no God is named as the one who keeps the king awake, who steers the reading to that page, who times it all. The book's signature silence is loudest exactly here, at its hinge."
    },

    {
      "scene_id": "S2",
      "verse_range": "6:4-9",
      "scene_kind": "AUDIENCE_SCENE",
      "scene_communicative_purpose": "Springs the irony: Haman, come to ask for Mordecai's death, mistakes himself for the man to be honoured and prescribes the most lavish honours he can imagine.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT"
          },
          {
            "being_id": "B3",
            "role_in_scene": "ADVERSARY",
            "presence": "PRESENT"
          },
          {
            "being_id": "B1",
            "role_in_scene": "HONORED_ONE",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B19",
            "role_in_scene": "LINEAGE_REFERENT",
            "presence": "REFERENCED"
          }
        ]
      },

      "places_in_scene": {
        "_note": "The outer court of the king's house (the audience venue) and the open square of the city (the prescribed procession route) are descriptive sub-locations of the palace at PL1, carried as bare atoms in the proposition slots, not separate place codes.",
        "entries": [
          {
            "place_id": "PL1"
          }
        ]
      },

      "objects_in_scene": {
        "entries": [
          {
            "object_id": "TH_GALLOWS"
          },
          {
            "object_id": "TH_ROYAL_ROBE"
          },
          {
            "object_id": "TH_ROYAL_HORSE"
          },
          {
            "object_id": "TH_ROYAL_CROWN"
          }
        ]
      },

      "times_in_scene": {
        "_note": "No distinct temporal frame; the scene runs straight on from the night-scene into the morning audience.",
        "entries": null
      },

      "significant_absence": "Haman never gets to speak his errand — the request to hang Mordecai stays unspoken, swallowed by the king's question; the narrator lets us know it only in passing. And the king never says whom he means; the name is withheld, so Haman convicts himself in the gap. No one — not the king, not Haman — invokes any higher will; the perfectly-timed cross-purpose simply happens, with no hand named over it."
    },

    {
      "scene_id": "S3",
      "verse_range": "6:10-11",
      "scene_kind": "REVERSAL_SCENE",
      "scene_communicative_purpose": "Executes the reversal: the king orders Haman to do every honour, to the letter, for Mordecai — and Haman carries it out with his own hands and voice.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT"
          },
          {
            "being_id": "B3",
            "role_in_scene": "ADVERSARY",
            "presence": "PRESENT"
          },
          {
            "being_id": "B1",
            "role_in_scene": "HONORED_ONE",
            "presence": "PRESENT",
            "referential_form": "MORDECAI_THE_JEW"
          }
        ]
      },

      "places_in_scene": {
        "_note": "The open square of the city (the procession route) is a descriptive sub-location of the capital at PL1, carried as a bare atom in the proposition slots; the king's gate, where Mordecai sits, is PL8.",
        "entries": [
          {
            "place_id": "PL8"
          }
        ]
      },

      "objects_in_scene": {
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
        "_note": "No distinct temporal frame for this scene; it follows immediately on the king's command.",
        "entries": null
      },

      "significant_absence": "No protest from Haman is recorded — between the king's command and Haman's obeying it, the narrator gives not one word of his fury or his pleading; the silence is the humiliation. And no one names the justice on display: the perfect symmetry of the man made to exalt the man he meant to hang is left to stand bare, uncredited to any hand."
    },

    {
      "scene_id": "S4",
      "verse_range": "6:12-14",
      "scene_kind": "FLIGHT_AND_HOUSEHOLD_VERDICT_SCENE",
      "scene_communicative_purpose": "Closes the turn: Mordecai returns unmoved, Haman flees in shame, and his own household pronounces the verdict — he will surely fall — as he is swept toward Esther's banquet and his end.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B1",
            "role_in_scene": "REFUSER",
            "presence": "PRESENT",
            "referential_form": "MORDECAI_THE_JEW"
          },
          {
            "being_id": "B3",
            "role_in_scene": "MAN_WHO_FLEES_IN_MOURNING",
            "presence": "PRESENT"
          },
          {
            "being_id": "B6",
            "role_in_scene": "ADVISERS",
            "presence": "PRESENT"
          },
          {
            "being_id": "B23",
            "role_in_scene": "ADVISERS",
            "presence": "PRESENT"
          },
          {
            "being_id": "B17",
            "role_in_scene": "LINEAGE_REFERENT",
            "presence": "REFERENCED",
            "referential_form": "THE_SEED_OF_THE_JEWS"
          },
          {
            "being_id": "B2",
            "role_in_scene": "QUEEN",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B24",
            "role_in_scene": "EUNUCHS_WHO_HURRY_HAMAN_AWAY",
            "presence": "PRESENT"
          }
        ]
      },

      "places_in_scene": {
        "_note": "Haman's house, where he flees and the verdict is spoken, is a descriptive setting carried as a bare atom in the proposition slots; the king's gate, to which Mordecai returns, is PL8.",
        "entries": [
          {
            "place_id": "PL8"
          }
        ]
      },

      "objects_in_scene": {
        "_note": "The covered head in mourning is the descriptive sign of Haman's shame, carried as a bare atom in the proposition slots, not a registry object. The banquet (the mishteh) is an institution, carried as the bare atom MISHTEH in the proposition slots, not an object_id.",
        "entries": null
      },

      "times_in_scene": {
        "_note": "Scene-content time is the relative overlap 'while they were still speaking', not a registered TM_ code; carried as a bare atom in the proposition slots.",
        "entries": null
      },

      "significant_absence": "The household names \"Jewish stock\" as the ground of Haman's doom — but they name no God behind it; the certainty of his fall is pinned to a people, never to the One that people belongs to. The book states the verdict and withholds its author. And nothing is said of Mordecai's feelings at his sudden honour — he simply returns to the gate, his silence as pointed as Haman's flight."
    }
  ],

  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "6:1",
      "proposition_kind": "FEARED",
      "event_specific_slots": {
        "sleepless_party": "B4",
        "when": "THAT_NIGHT"
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
      "verse_anchor": "6:1",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B4",
        "brought": "TH_ANNALS",
        "named_as": "THE_CHRONICLES",
        "speech_act": "DIRECTS_HEARER_TO_DO"
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
      "verse_anchor": "6:1",
      "proposition_kind": "PERCEIVED",
      "event_specific_slots": {
        "read_record": "TH_ANNALS",
        "read_before": "B4"
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
      "verse_anchor": "6:2",
      "proposition_kind": "PERCEIVED",
      "event_specific_slots": {
        "found_record_form": "WRITTEN",
        "exposer": "B1",
        "exposed_parties": ["B11", "B12"],
        "exposed_office": "THRESHOLD_KEEPERS",
        "exposed_being": "EUNUCHS",
        "plotted_against": "B4",
        "plotted_intent": "LAYING_A_HAND"
      },
      "inter_proposition_links": {
        "caused_by": "P3",
        "forward_link_to": "P5"
      },
      "cross_ref": "The chronicle pays off Mordecai's exposure of the plot at E05; the planted record surfaces here at the book's hinge.",
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P5",
      "scene_link": "S1",
      "verse_anchor": "6:3",
      "proposition_kind": "ASKED",
      "event_specific_slots": {
        "speaker": "B4",
        "asked_about": "B1",
        "asked_reward": "HONOUR",
        "asked_reward_also": "GREATNESS",
        "asked_for_deed": "THIS",
        "speech_act": "ASKS_INFORMATION_SEEKING_QUESTION"
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
      "verse_anchor": "6:3",
      "proposition_kind": "ANSWERED",
      "event_specific_slots": {
        "speaker": "B18",
        "answered": "NOTHING",
        "done_for": "B1",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P5",
        "forward_link_to": "P7"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P7",
      "scene_link": "S2",
      "verse_anchor": "6:4",
      "proposition_kind": "ASKED",
      "event_specific_slots": {
        "speaker": "B4",
        "asked": "WHO",
        "where": "THE_COURT",
        "speech_act": "ASKS_INFORMATION_SEEKING_QUESTION"
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
      "verse_anchor": "6:4",
      "proposition_kind": "ARRIVED_AT",
      "event_specific_slots": {
        "arriver": "B3",
        "destination": "THE_OUTER_COURT",
        "court_of": "THE_KINGS_HOUSE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P9"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P9",
      "scene_link": "S2",
      "verse_anchor": "6:4",
      "proposition_kind": "ARRIVED_AT",
      "event_specific_slots": {
        "errand_holder": "B3",
        "errand_addressee": "B4",
        "errand_request": "A_HANGING",
        "hanging_target": "B1",
        "hanging_instrument": "TH_GALLOWS",
        "gallows_preparer": "B3",
        "gallows_prepared_for": "B1"
      },
      "inter_proposition_links": {
        "caused_by": "P8",
        "forward_link_to": "P10"
      },
      "cross_ref": "The gallows traces to Haman's gallows-building at E10; the errand stays unspoken, swallowed by the king's question.",
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P10",
      "scene_link": "S2",
      "verse_anchor": "6:5",
      "proposition_kind": "ANSWERED",
      "event_specific_slots": {
        "speaker": "B18",
        "answered_standing": "B3",
        "where": "THE_COURT",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P7",
        "forward_link_to": "P11"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P11",
      "scene_link": "S2",
      "verse_anchor": "6:5",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B4",
        "commanded": "LET_HIM_COME",
        "speech_act": "DIRECTS_HEARER_TO_DO"
      },
      "inter_proposition_links": {
        "caused_by": "P10",
        "forward_link_to": "P12"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P12",
      "scene_link": "S2",
      "verse_anchor": "6:6",
      "proposition_kind": "ARRIVED_AT",
      "event_specific_slots": {
        "comer": "B3"
      },
      "inter_proposition_links": {
        "caused_by": "P11",
        "forward_link_to": "P13"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P13",
      "scene_link": "S2",
      "verse_anchor": "6:6",
      "proposition_kind": "ASKED",
      "event_specific_slots": {
        "speaker": "B4",
        "addressee": "B3",
        "asked_deed": "WHAT_TO_DO",
        "asked_for_party": "A_MAN",
        "delighted_in_by": "B4",
        "delight_kind": "TO_HONOUR",
        "speech_act": "ASKS_DELIBERATIVE_QUESTION"
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
      "scene_link": "S2",
      "verse_anchor": "6:6",
      "proposition_kind": "PERCEIVED",
      "event_specific_slots": {
        "speaker": "B3",
        "addressee": "B3",
        "thought_where": "HIS_HEART",
        "guessed_party": "HIMSELF",
        "honoured_by": "B4",
        "honoured_extent": "MORE_THAN_ANY",
        "speech_act": "ASKS_DELIBERATIVE_QUESTION"
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
      "scene_link": "S2",
      "verse_anchor": "6:7",
      "proposition_kind": "ANSWERED",
      "event_specific_slots": {
        "speaker": "B3",
        "addressee": "B4",
        "answered_about_party": "A_MAN",
        "delighted_in_by": "B4",
        "delight_kind": "TO_HONOUR",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P14",
        "forward_link_to": "P16"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P16",
      "scene_link": "S2",
      "verse_anchor": "6:8",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B3",
        "addressee": "B4",
        "prescribe_components": [
          {
            "action": "PERMITTED",
            "brought": "TH_ROYAL_ROBE",
            "robe_worn_by": "B4",
            "status": "FORESEEN",
            "speech_act": "ADVISES_COURSE_OF_ACTION"
          },
          {
            "action": "LET_THEM_BRING",
            "brought": "TH_ROYAL_HORSE",
            "horse_ridden_by": "B4",
            "status": "FORESEEN",
            "speech_act": "ADVISES_COURSE_OF_ACTION"
          },
          {
            "action": "LET_THEM_SET",
            "set_thing": "TH_ROYAL_CROWN",
            "set_on": "THE_HORSES_HEAD",
            "status": "FORESEEN",
            "speech_act": "ADVISES_COURSE_OF_ACTION"
          }
        ]
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
      "scene_link": "S2",
      "verse_anchor": "6:9",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B3",
        "handed_objects": ["TH_ROYAL_ROBE", "TH_ROYAL_HORSE"],
        "handed_into_hand_of": "B19",
        "noble_qualified_as": "THE_KINGS_NOBLES",
        "status": "FORESEEN",
        "speech_act": "ADVISES_COURSE_OF_ACTION"
      },
      "inter_proposition_links": {
        "content_of": "P16",
        "forward_link_to": "P18"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P18",
      "scene_link": "S2",
      "verse_anchor": "6:9",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B3",
        "clothed_party": "THE_MAN",
        "delighted_in_by": "B4",
        "delight_kind": "TO_HONOUR",
        "status": "FORESEEN",
        "speech_act": "ADVISES_COURSE_OF_ACTION"
      },
      "inter_proposition_links": {
        "content_of": "P16",
        "forward_link_to": "P19"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P19",
      "scene_link": "S2",
      "verse_anchor": "6:9",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B3",
        "led_on": "TH_ROYAL_HORSE",
        "led_through": "A_SQUARE",
        "square_of": "THE_CITY",
        "status": "FORESEEN",
        "speech_act": "ADVISES_COURSE_OF_ACTION"
      },
      "inter_proposition_links": {
        "content_of": "P16",
        "forward_link_to": "P20"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P20",
      "scene_link": "S2",
      "verse_anchor": "6:9",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B3",
        "cried_where": "BEFORE_HIM",
        "cried_formula": "THUS_DONE",
        "cried_for_party": "THE_MAN",
        "delighted_in_by": "B4",
        "delight_kind": "TO_HONOUR",
        "preserve_form": true,
        "status": "FORESEEN",
        "speech_act": "ADVISES_COURSE_OF_ACTION"
      },
      "inter_proposition_links": {
        "content_of": "P16"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P21",
      "scene_link": "S3",
      "verse_anchor": "6:10",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B4",
        "addressee": "B3",
        "commanded": "HURRY",
        "take_objects": ["TH_ROYAL_ROBE", "TH_ROYAL_HORSE"],
        "as_marker": "AS_YOU_SAID",
        "speech_act": "DIRECTS_HEARER_TO_DO"
      },
      "inter_proposition_links": {
        "forward_link_to": "P22"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P22",
      "scene_link": "S3",
      "verse_anchor": "6:10",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B4",
        "addressee": "B3",
        "commanded_deed": "DO_SO",
        "honoured_party": "B1",
        "honoured_referential_form": "THE_JEW",
        "honoured_seat": "PL8",
        "omit_marker": "NOTHING",
        "omit_of": "ALL_YOU_SAID",
        "speech_act": "DIRECTS_HEARER_TO_DO"
      },
      "inter_proposition_links": {
        "caused_by": "P21",
        "forward_link_to": "P23",
        "paired_with": "P16"
      },
      "cross_ref": "The king turns Haman's prescription (P16) back on him, command-for-prescription, for Mordecai.",
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P23",
      "scene_link": "S3",
      "verse_anchor": "6:11",
      "proposition_kind": "TOOK",
      "event_specific_slots": {
        "taker": "B3",
        "taken_objects": ["TH_ROYAL_ROBE", "TH_ROYAL_HORSE"]
      },
      "inter_proposition_links": {
        "caused_by": "P22",
        "forward_link_to": "P24"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P24",
      "scene_link": "S3",
      "verse_anchor": "6:11",
      "proposition_kind": "GAVE",
      "event_specific_slots": {
        "clother": "B3",
        "clothed_party": "B1"
      },
      "inter_proposition_links": {
        "caused_by": "P23",
        "forward_link_to": "P25"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P25",
      "scene_link": "S3",
      "verse_anchor": "6:11",
      "proposition_kind": "TOOK",
      "event_specific_slots": {
        "leader": "B3",
        "led_on": "TH_ROYAL_HORSE",
        "led_through": "A_SQUARE",
        "square_of": "THE_CITY"
      },
      "inter_proposition_links": {
        "caused_by": "P24",
        "forward_link_to": "P26"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P26",
      "scene_link": "S3",
      "verse_anchor": "6:11",
      "proposition_kind": "LAMENT",
      "event_specific_slots": {
        "crier": "B3",
        "cried_where": "BEFORE_HIM",
        "cried_formula": "THUS_DONE",
        "cried_for_party": "THE_MAN",
        "delighted_in_by": "B4",
        "delight_kind": "TO_HONOUR",
        "preserve_form": true,
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P25",
        "paired_with": "P20",
        "forward_link_to": "P27"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P27",
      "scene_link": "S4",
      "verse_anchor": "6:12",
      "proposition_kind": "RETURNED",
      "event_specific_slots": {
        "returner": "B1",
        "destination": "PL8"
      },
      "inter_proposition_links": {
        "forward_link_to": "P28"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P28",
      "scene_link": "S4",
      "verse_anchor": "6:12",
      "proposition_kind": "RETURNED",
      "event_specific_slots": {
        "hurrier": "B3",
        "destination": "HIS_HOUSE",
        "state": "MOURNING",
        "head_form": "COVERED"
      },
      "inter_proposition_links": {
        "forward_link_to": "P29"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P29",
      "scene_link": "S4",
      "verse_anchor": "6:13",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "teller": "B3",
        "told_parties": ["B6", "B23"],
        "wife_marker": "HIS_WIFE",
        "told_content": "EVERYTHING",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P28",
        "forward_link_to": "P30"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P30",
      "scene_link": "S4",
      "verse_anchor": "6:13",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "speakers": ["B23", "B6"],
        "wife_marker": "HIS_WIFE",
        "addressee": "B3",
        "verdict_components": [
          {
            "component_id": "C1",
            "action": "STATED",
            "condition": "OF_JEWISH_STOCK",
            "stock_of": "B17",
            "fallen_before": "B1",
            "condition_of": "C2",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "component_id": "C2",
            "action": "FORETOLD_FALL",
            "outcome": "NO_PREVAILING",
            "instead": "A_FALLING",
            "certainty": "SURELY",
            "fallen_before": "B1",
            "status": "FORESEEN",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P29",
        "forward_link_to": "P31"
      },
      "cross_ref": "The household's verdict pins Haman's certain fall to a people and withholds its author; the omen foreshadows his end at E12.",
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P31",
      "scene_link": "S4",
      "verse_anchor": "6:14",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "speakers": ["B6", "B23"],
        "speaking_with": "B3",
        "ongoing_marker": "STILL"
      },
      "inter_proposition_links": {
        "caused_by": "P30",
        "forward_link_to": "P32"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P32",
      "scene_link": "S4",
      "verse_anchor": "6:14",
      "proposition_kind": "ARRIVED_AT",
      "event_specific_slots": {
        "arrivers": "B24",
        "eunuchs_of": "B4"
      },
      "inter_proposition_links": {
        "caused_by": "P31",
        "forward_link_to": "P33"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P33",
      "scene_link": "S4",
      "verse_anchor": "6:14",
      "proposition_kind": "DEPARTED",
      "event_specific_slots": {
        "hurriers": "B24",
        "hurried_party": "B3",
        "to_event": "MISHTEH",
        "event_of": "B2"
      },
      "inter_proposition_links": {
        "caused_by": "P32"
      },
      "cross_ref": "The closing summons hands forward to Esther's second banquet at E12, where Haman falls.",
      "cb_flags": [],
      "figure_flags": []
    }
  ]
}
```

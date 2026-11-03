---
type: "sta-meaning-coordinates"
pericope: "E07"
pericope-title: "The lot and the decree of destruction: Haman buys the death of a people"
source-meaning-map: [[E07-Esther-3-7-15]]
status: "valid"
pilot: "pilot-2"
---

# E07 — Esther 3:7–15 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "esther_pericope_07_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",

  "header": {
    "bcv": "Esther 3:7-15",
    "pericope_title": "The lot and the decree of destruction: Haman buys the death of a people",
    "book_context_ref": "esther_pilot_BCD_v0_1",
    "source_meaning_map_ref": "E07-Esther-3-7-15",
    "source_language": "Biblical Hebrew"
  },

  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "Narration is INFORMAL_CASUAL throughout. Two moment-level FORMAL_OFFICIAL overrides on the book's first voiced/written official acts (Marcia's standing rule: FORMAL_OFFICIAL only on voiced/granted decree content): (1) Haman's charge-and-proposal to the king, 3:8-9; (2) the decree's own voiced words, 3:13. The narration around them — the lot, the ring, the couriers, the closing tableau — stays INFORMAL_CASUAL.",
      "scene_level": null,
      "moment_level": [
        {
          "verse": "3:8-9",
          "override_value": "FORMAL_OFFICIAL",
          "genre_override": null,
          "genre_group_override": null
        },
        {
          "verse": "3:13",
          "override_value": "FORMAL_OFFICIAL",
          "genre_override": null,
          "genre_group_override": null
        }
      ]
    }
  },

  "level_1": {
    "arc_elements": [
      "DAY_CHOSEN_BY_LOT",
      "ACCUSATION_LAID",
      "DESTRUCTION_PROPOSED_AND_BOUGHT",
      "AUTHORITY_GRANTED",
      "ROYAL_DECREE",
      "PEOPLE_CONDEMNED"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "PHYSICAL_LOCATION",
      "TEMPORAL_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT"
    ],
    "tone_elements": [
      "COLD",
      "PROCEDURAL",
      "RESTRAINED",
      "CEREMONIAL",
      "CHILLING"
    ],
    "pace_elements": [
      "DELIBERATE",
      "ACCELERATES",
      "PROCEDURAL"
    ],
    "communicative_function_elements": [
      "FIXES",
      "ACCUSES",
      "GRANTS",
      "PUBLISHES",
      "CONDEMNS"
    ]
  },

  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "3:7",
      "scene_kind": "LOT_CASTING_SCENE",
      "scene_communicative_purpose": "Shows the day of destruction being chosen — by lot, far off at the end of the year.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B3",
            "role_in_scene": "ADVERSARY",
            "presence": "PRESENT",
            "referential_form": "HAMAN_THE_PLOTTER"
          },
          {
            "being_id": "B4",
            "role_in_scene": "ERA_REFERENT",
            "presence": "REFERENCED"
          }
        ]
      },

      "places_in_scene": {
        "_note": "No place is named; the lot is cast 'before Haman' with no setting given.",
        "entries": null
      },

      "objects_in_scene": {
        "entries": [
          {
            "object_id": "TH_PUR_LOT"
          }
        ]
      },

      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_NISAN"
          },
          {
            "time_id": "TM_ADAR"
          }
        ]
      },

      "significant_absence": "No God is named over the casting of the lot — the book's signature silence falls exactly where a reader might most expect a hand behind the chance. The text says only that the lot fell; it does not say who made it fall. Nothing is said either of why the far-off month was let stand — the long delay simply happens, unexplained."
    },

    {
      "scene_id": "S2",
      "verse_range": "3:8-11",
      "scene_kind": "AUTHORITY_GRANT_SCENE",
      "scene_communicative_purpose": "Shows the destruction proposed, bought, and granted — the king handing Haman the ring and the people without even asking their name.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B3",
            "role_in_scene": "ACCUSER",
            "presence": "PRESENT",
            "referential_form": "SON_OF_HAMMEDATHA_THE_AGAGITE_THE_ENEMY_OF_THE_JEWS"
          },
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT"
          },
          {
            "being_id": "B17",
            "role_in_scene": "THREATENED_PEOPLE",
            "presence": "REFERENCED",
            "referential_form": "A_CERTAIN_PEOPLE"
          }
        ]
      },

      "places_in_scene": {
        "_note": "The king's treasuries (the royal stores into which Haman's silver is to be brought) are scene content carried as a bare atom in L3 slots (P3.silver_destination), not a registry place.",
        "entries": null
      },

      "objects_in_scene": {
        "_note": "The silver (ten thousand talents) is Haman's payment, carried as bare atoms in L3 slots (P3); the law (I2, the king's dat) is the institution Haman's charge turns on, carried as a bare atom in L3 slots (P2.governing_rule).",
        "entries": [
          {
            "object_id": "TH_SIGNET_RING"
          }
        ]
      },

      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; the audience with the king follows on the casting of the lot, with no new date given.",
        "entries": null
      },

      "significant_absence": "The king never asks who the people are. He does not learn their name, their nation, or their God — and the narrator lets that ignorance stand, unbroken: the reader knows it is the people of the queen, but the king condemns them blind. No protest is voiced, no counsel sought, no god invoked over a sentence of death. And Haman, naming the price in silver, never names the people he means to wipe out."
    },

    {
      "scene_id": "S3",
      "verse_range": "3:12-15",
      "scene_kind": "DECREE_SCENE",
      "scene_communicative_purpose": "Shows the sentence made unbreakable and sent across the empire — and the chilling close: the two men drinking while the capital reels.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B3",
            "role_in_scene": "SCRIBES",
            "presence": "PRESENT"
          },
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT"
          },
          {
            "being_id": "B17",
            "role_in_scene": "THREATENED_PEOPLE",
            "presence": "REFERENCED",
            "referential_form": "ALL_THE_JEWS"
          },
          {
            "being_id": "B21",
            "role_in_scene": "SCRIBES",
            "presence": "PRESENT"
          },
          {
            "being_id": "B22",
            "role_in_scene": "COURIERS",
            "presence": "PRESENT"
          },
          {
            "being_id": "B19",
            "role_in_scene": "PROVINCIAL_OFFICIALS",
            "presence": "REFERENCED"
          }
        ]
      },

      "places_in_scene": {
        "_note": "The 127 provinces (I5) is an institution-span carried as a bare atom in L3 slots (P9.decree_scope, P10.publication_scope), not a scene place; the staged place is Susa the citadel where the decree is issued.",
        "entries": [
          {
            "place_id": "PL1"
          }
        ]
      },

      "objects_in_scene": {
        "_note": "The law (I2, the dat given force in every province) is an institution carried as a bare atom in L3 slots (P10.given_as); the decree's own voiced words are the FORMAL_OFFICIAL content of P9, not a scene object.",
        "entries": [
          {
            "object_id": "TH_EDICT"
          },
          {
            "object_id": "TH_SIGNET_RING"
          }
        ]
      },

      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_NISAN"
          },
          {
            "time_id": "TM_ADAR"
          }
        ]
      },

      "significant_absence": "Even here, where a whole people is condemned by name in writing, no God is named — not in the decree, not in the narration, not over the bewildered city. No one in the scene speaks for the condemned; no Jew, no Mordecai, no Esther appears yet to answer it. And the narrator withholds all comment on the killing itself, reporting it in the same flat voice as the couriers' errand — the only crack of feeling is the last word, that the city was bewildered, set against the two men calmly at their cups."
    }
  ],

  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "3:7",
      "proposition_kind": "CAST_LOTS",
      "event_specific_slots": {
        "lot_cast": "TH_PUR_LOT",
        "lot_also_called": "the_goral",
        "cast_before": "B3",
        "anchor_month": "TM_NISAN",
        "month_ordinal": "first",
        "regnal_year": "twelfth",
        "regnal_of": "B4",
        "casting_manner": ["day_to_day", "month_to_month"],
        "fell_on_month": "TM_ADAR",
        "fallen_month_ordinal": "twelfth"
      },
      "inter_proposition_links": {
        "forward_link_to": "P2"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P2",
      "scene_link": "S2",
      "verse_anchor": "3:8",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "accusation_components": [
          {
            "action": "STATED",
            "accuser": "B3",
            "addressee": "B4",
            "accused": "B17",
            "speech_act": "ALLEGES_AGAINST"
          },
          {
            "action": "CHARACTERIZED",
            "accused": "B17",
            "alleged_state": ["scattered", "dispersed"],
            "scattered_among": "the_peoples",
            "scattered_where": "the_provinces",
            "provinces_of": "the_kingdom",
            "speech_act": "ALLEGES_AGAINST"
          },
          {
            "action": "ALLEGED_DIFFERENT_LAW",
            "accused": "B17",
            "different_from": "every_people",
            "governing_rule": "THE_LAW",
            "speech_act": "ALLEGES_AGAINST",
            "status": "NORM"
          },
          {
            "action": "ALLEGED_DISOBEDIENCE",
            "accused": "B17",
            "unkept_rule_of": "B4",
            "speech_act": "ALLEGES_AGAINST",
            "status": "NORM"
          },
          {
            "action": "PROPOSED",
            "accuser": "B3",
            "addressee": "B4",
            "tolerated_party": "B17",
            "speech_act": "ALLEGES_AGAINST"
          }
        ]
      },
      "inter_proposition_links": {
        "forward_link_to": "P3"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P3",
      "scene_link": "S2",
      "verse_anchor": "3:9",
      "proposition_kind": "PROPOSED",
      "event_specific_slots": {
        "proposal_components": [
          {
            "action": "PROPOSED",
            "proposer": "B3",
            "addressee": "B4",
            "destroyed_party": "B17",
            "speech_act": "PROPOSES_COURSE_OF_ACTION"
          },
          {
            "action": "OFFERED_PAYMENT",
            "payer": "B3",
            "payment_metal": "silver",
            "payment_amount": "ten_thousand",
            "payment_unit": "talents",
            "weighed_into_hands_of": "the_doers_of_the_work",
            "silver_destination": "the_kings_treasuries",
            "speech_act": "PROPOSES_COURSE_OF_ACTION"
          }
        ]
      },
      "inter_proposition_links": {
        "condition_of": "P4",
        "forward_link_to": "P5"
      },
      "cross_ref": "The destruction-proposal is contingent on the king's consent (the if-it-please-the-king protasis rides as condition P4).",
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P4",
      "scene_link": "S2",
      "verse_anchor": "3:9",
      "proposition_kind": "ROYAL_PLEASURE_CONDITION",
      "status": "COUNTERFACTUAL",
      "event_specific_slots": {
        "condition_holder": "B4",
        "condition_marker": "if_it_please_the_king"
      },
      "inter_proposition_links": {
        "condition_of": "P3"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P5",
      "scene_link": "S2",
      "verse_anchor": "3:10",
      "proposition_kind": "RING_REMOVED",
      "event_specific_slots": {
        "remover": "B4",
        "removed_ring": "TH_SIGNET_RING",
        "ring_kind": "signet",
        "removed_from": "his_hand"
      },
      "inter_proposition_links": {
        "caused_by": "P3",
        "forward_link_to": "P6"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P6",
      "scene_link": "S2",
      "verse_anchor": "3:10",
      "proposition_kind": "GAVE",
      "event_specific_slots": {
        "giver": "B4",
        "given_ring": "TH_SIGNET_RING",
        "given_to": "B3",
        "given_to_form": "THE_AGAGITE"
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
      "verse_anchor": "3:11",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "grant_components": [
          {
            "action": "GAVE",
            "granter": "B4",
            "grantee": "B3",
            "granted_thing": "the_silver",
            "speech_act": "PRESCRIBES_AS_LAW",
            "status": "PERMITTED"
          },
          {
            "action": "GRANTED_PEOPLE",
            "granter": "B4",
            "grantee": "B3",
            "granted_party": "B17",
            "free_hand_marker": "as_he_sees_good",
            "discretion_seat": "his_eyes",
            "speech_act": "PRESCRIBES_AS_LAW",
            "status": "PERMITTED"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P6",
        "forward_link_to": "P8"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P8",
      "scene_link": "S3",
      "verse_anchor": "3:12",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "summoned": "B21",
        "summoned_of_whom": "B4",
        "anchor_month": "TM_NISAN",
        "month_ordinal": "first",
        "day_of_month": "thirteenth"
      },
      "inter_proposition_links": {
        "caused_by": "P7",
        "forward_link_to": "P9"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P9",
      "scene_link": "S3",
      "verse_anchor": "3:12",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "decree_writ": "TH_EDICT",
        "writing_conformity": "AS_HAMAN_COMMANDED",
        "commander": "B3",
        "addressed_to": ["B19"],
        "addressee_span": ["province_and_province", "people_and_people"],
        "per_province_form": "OWN_SCRIPT",
        "per_people_form": "OWN_TONGUE",
        "name_invoked": "B4",
        "name_capacity": "KING",
        "sealing_instrument": "TH_SIGNET_RING",
        "ring_of_whom": "B4"
      },
      "inter_proposition_links": {
        "caused_by": "P8",
        "forward_link_to": "P10"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P10",
      "scene_link": "S3",
      "verse_anchor": "3:13",
      "proposition_kind": "DECLARED",
      "status": "PERMITTED",
      "event_specific_slots": {
        "dispatched_edict": "TH_EDICT",
        "carriers": "B22",
        "decree_scope": "the_provinces",
        "scope_sovereign": "B4",
        "decree_components": [
          {
            "action": "DESTROY",
            "decreed_target": "B17",
            "target_extent": "all",
            "speech_act": "PRESCRIBES_AS_LAW",
            "status": "FORESEEN"
          },
          {
            "action": "KILL",
            "decreed_target": "B17",
            "target_extent": "all",
            "speech_act": "PRESCRIBES_AS_LAW",
            "status": "FORESEEN"
          },
          {
            "action": "ANNIHILATE",
            "decreed_target": "B17",
            "target_extent": ["young", "old", "children", "women"],
            "speech_act": "PRESCRIBES_AS_LAW",
            "status": "FORESEEN"
          },
          {
            "action": "PLUNDER",
            "plundered_party": "B17",
            "plundered_goods": "their_goods",
            "speech_act": "PRESCRIBES_AS_LAW",
            "status": "FORESEEN"
          }
        ],
        "appointed_span": "one_day",
        "appointed_day": "thirteenth",
        "appointed_month": "TM_ADAR",
        "appointed_month_ordinal": "twelfth"
      },
      "inter_proposition_links": {
        "caused_by": "P9",
        "forward_link_to": "P11"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P11",
      "scene_link": "S3",
      "verse_anchor": "3:14",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "published_copy": "TH_EDICT",
        "copy_of": "the_writing",
        "given_as": "law",
        "publication_scope": "province_and_province",
        "disclosure": "PUBLISHED",
        "disclosed_to": "all_peoples"
      },
      "inter_proposition_links": {
        "caused_by": "P10",
        "forward_link_to": "P13"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P12",
      "scene_link": "S3",
      "verse_anchor": "3:14",
      "proposition_kind": "READINESS_FOR_THE_DAY",
      "status": "FORESEEN",
      "event_specific_slots": {
        "readied_party": "all_peoples",
        "readied_for": "that_day"
      },
      "inter_proposition_links": {
        "purpose_of": "P11"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P13",
      "scene_link": "S3",
      "verse_anchor": "3:15",
      "proposition_kind": "DEPARTED",
      "event_specific_slots": {
        "departer": "B22",
        "departure_manner": "driven",
        "driven_by": "the_kings_word",
        "word_of_whom": "B4"
      },
      "inter_proposition_links": {
        "caused_by": "P10",
        "forward_link_to": "P14"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P14",
      "scene_link": "S3",
      "verse_anchor": "3:15",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "issued_law": "law",
        "issued_at": "PL1",
        "place_qualifier": "the_citadel"
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
      "verse_anchor": "3:15",
      "proposition_kind": "ATE",
      "event_specific_slots": {
        "sitter": ["B4", "B3"],
        "sitting_purpose": "to_drink"
      },
      "inter_proposition_links": {
        "paired_with": "P16"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P16",
      "scene_link": "S3",
      "verse_anchor": "3:15",
      "proposition_kind": "CITY_BEWILDERED",
      "event_specific_slots": {
        "bewildered_place": "PL1"
      },
      "inter_proposition_links": {
        "paired_with": "P15"
      },
      "cb_flags": [],
      "figure_flags": []
    }
  ]
}
```

---
type: "sta-meaning-coordinates"
pericope: "E15"
pericope-title: "The day turned over: the Jews stand, strike, and take no plunder"
source-meaning-map: [[E15-Esther-9-1-10]]
status: "valid"
pilot: "pilot-2"
---

# E15 — Esther 9:1–10 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "esther_pericope_15_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",

  "header": {
    "bcv": "Esther 9:1-10",
    "pericope_title": "The day turned over: the Jews stand, strike, and take no plunder",
    "book_context_ref": "esther_pilot_BCD_v0_1",
    "source_meaning_map_ref": "E15-Esther-9-1-10",
    "source_language": "Biblical Hebrew"
  },

  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "Whole pericope stays INFORMAL_CASUAL. The king's word and decree are NAMED as the appointed thing now coming due, not VOICED — no quoted edict here (that was E14) — so no FORMAL_OFFICIAL override applies; the decree's bindingness is carried instead by status:NORM on P1 (Marcia's named-not-voiced register rule). One moment-level NARRATIVE_FRAMING override at v.1 for the narrator's stunned aside 'and it was turned over' (COMMUNITY_MEMORY framing of the long-dreaded, now-reversed day).",
      "scene_level": null,
      "moment_level": [
        {
          "verse": "9:1",
          "framing_override": "COMMUNITY_MEMORY",
          "genre_override": null,
          "genre_group_override": null
        }
      ]
    }
  },

  "level_1": {
    "arc_elements": [
      "ENEMY_STRUCK",
      "GREAT_REVERSAL",
      "EMPIRE_TILTED",
      "ENEMIES_STRUCK",
      "PLUNDER_REFUSED"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "PHYSICAL_LOCATION",
      "TEMPORAL_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT"
    ],
    "tone_elements": [
      "RESTRAINED",
      "ECONOMICAL",
      "SOBER",
      "VINDICATED",
      "CEREMONIAL"
    ],
    "pace_elements": [
      "ACCUMULATES",
      "BRISK",
      "SLOWED"
    ],
    "communicative_function_elements": [
      "FIXES",
      "REVERSES",
      "TILTS",
      "TALLIES",
      "WITHHOLDS"
    ]
  },

  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "9:1-4",
      "scene_kind": "REVERSAL_SCENE",
      "scene_communicative_purpose": "States the great reversal of the appointed day and shows the empire itself tilting toward the Jews out of dread of them and of the rising Mordecai.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B17",
            "role_in_scene": "THREATENED_PEOPLE",
            "presence": "PRESENT"
          },
          {
            "being_id": "B20",
            "role_in_scene": "SLAIN_FOES",
            "presence": "PRESENT"
          },
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B1",
            "role_in_scene": "THREATENED_PEOPLE",
            "presence": "REFERENCED",
            "referential_form": "THE_DREAD_OF_MORDECAI"
          },
          {
            "being_id": "B19",
            "role_in_scene": "PROVINCIAL_OFFICIALS",
            "presence": "PRESENT"
          }
        ]
      },

      "places_in_scene": {
        "_note": "No discrete registry place is staged in this scene. The 127 provinces (I5, the realm-span the two decrees run through) is an institution-span carried in L3 slots (P4.realm_span). The Jews' own cities (their local towns) and the king's house (Mordecai's seat) are non-coded scene settings carried as bare atoms in L3 slots (P4.assembly_place, P9.greatness_seat) — no registry place code exists for them.",
        "entries": null
      },

      "objects_in_scene": {
        "_note": "The report of Mordecai (his spreading fame, šomʿo) is non-coded scene content carried in L3 slots (P9.report_of, P10), not an object code. The king's word and decree are a reference to the law (I2), carried as the bare atom governing_rule:THE_LAW in P1 — no object code minted.",
        "entries": null
      },

      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_ADAR"
          }
        ]
      },

      "significant_absence": "No god is named as the author of the reversal, and no prayer, no thanksgiving, no deliverer is credited — the 'turning over' simply is, stated in the passive, with no hand assigned to it. This is the book's signature: the rescue is everywhere felt and nowhere attributed."
    },

    {
      "scene_id": "S2",
      "verse_range": "9:5-10",
      "scene_kind": "STRIKING_AND_NAMED_SONS_SCENE",
      "scene_communicative_purpose": "Reports the striking of the enemies, tallies the five hundred dead in the capital, names Haman's ten slain sons in full, and seals the scene with the refusal of the spoil.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B17",
            "role_in_scene": "DELIVERED_PEOPLE",
            "presence": "PRESENT"
          },
          {
            "being_id": "B20",
            "role_in_scene": "SLAIN_FOES",
            "presence": "PRESENT"
          },
          {
            "being_id": "B16",
            "role_in_scene": "SLAIN_SONS",
            "presence": "PRESENT_BECOMES_DECEASED"
          },
          {
            "being_id": "B3",
            "role_in_scene": "LINEAGE_REFERENT",
            "presence": "REFERENCED",
            "referential_form": "THE_FOE_OF_THE_JEWS"
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
        "_note": "The sword (ḥerev, by which the enemies are struck) is non-coded scene content carried in L3 slots (P11.struck_with). The plunder (bizzah) is LOAD-BEARING non-coded content tied to the must-preserve significant_absence — carried as the bare atom withheld_spoil:THE_PLUNDER in P16, not an object code.",
        "entries": null
      },

      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; the striking runs on directly within the appointed thirteenth of Adar set in Scene 1.",
        "entries": null
      },

      "significant_absence": "Again no god is named over the victory, and no battle-cry, no song, no triumph-speech is recorded. And the loudest absence is an action withheld: the plunder the decree had granted them is expressly not taken — the 'did not lay their hand' that the next pericope will repeat, marking the Jews' self-restraint as the moral center of the deliverance."
    }
  ],

  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "9:1",
      "proposition_kind": "APPOINTED_DAY_CAME_DUE",
      "status": "NORM",
      "event_specific_slots": {
        "appointed_day": "thirteenth",
        "appointed_month": "TM_ADAR",
        "month_ordinal": "twelfth",
        "governing_rule": "THE_LAW",
        "rule_sovereign": "B4",
        "due_for": "EXECUTION"
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
      "verse_anchor": "9:1",
      "proposition_kind": "ENEMIES_HOPED_TO_OVERPOWER",
      "status": "COUNTERFACTUAL",
      "event_specific_slots": {
        "hoper": "B20",
        "hoped_against": "B17",
        "hoped_outcome": "OVERPOWERING"
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
      "verse_anchor": "9:1",
      "proposition_kind": "DAY_TURNED_OVER",
      "event_specific_slots": {
        "turned_to": "THE_OPPOSITE",
        "gained_upper_hand": "B17",
        "prevailed_over": "B20"
      },
      "inter_proposition_links": {
        "caused_by": "P2",
        "forward_link_to": "P4"
      },
      "cross_ref": "The hinge of the pericope: the enemies' hope (P2, COUNTERFACTUAL) is overturned here.",
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P4",
      "scene_link": "S1",
      "verse_anchor": "9:2",
      "proposition_kind": "ASSEMBLED_FOR_DEFENSE",
      "event_specific_slots": {
        "assembler": "B17",
        "assembly_place": "THEIR_OWN_CITIES",
        "realm_span": "THE_PROVINCES",
        "span_sovereign": "B4",
        "assembled_against": "B20"
      },
      "inter_proposition_links": {
        "caused_by": "P3",
        "purpose_of": "P11",
        "forward_link_to": "P5"
      },
      "cross_ref": "The assembling rides under the second decree's standing leave (status:PERMITTED) and is purposed toward the striking in Scene 2 (purpose_of P11) — self-defense, not aggression.",
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P5",
      "scene_link": "S1",
      "verse_anchor": "9:2",
      "proposition_kind": "NONE_COULD_STAND",
      "event_specific_slots": {
        "none_who_stood": "ANY_MAN",
        "could_not_stand_against": "B17"
      },
      "inter_proposition_links": {
        "caused_by": "P6"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P6",
      "scene_link": "S1",
      "verse_anchor": "9:2",
      "proposition_kind": "FEARED",
      "event_specific_slots": {
        "dread_of": "B17",
        "dread_fallen_on": "THE_PEOPLES",
        "peoples_extent": "ALL_OF_THEM"
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
      "verse_anchor": "9:3",
      "proposition_kind": "OFFICIALS_UPHELD_THE_JEWS",
      "event_specific_slots": {
        "upholder": "B19",
        "upheld": "B17",
        "official_roster": ["PROVINCIAL_CHIEFS", "SATRAPS", "GOVERNORS", "KINGS_OFFICERS"],
        "officers_of": "B4"
      },
      "inter_proposition_links": {
        "caused_by": "P8",
        "forward_link_to": "P9"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P8",
      "scene_link": "S1",
      "verse_anchor": "9:3",
      "proposition_kind": "FEARED",
      "event_specific_slots": {
        "dread_of": "B1",
        "dread_fallen_on": "B19"
      },
      "inter_proposition_links": {
        "forward_link_to": "P7"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P9",
      "scene_link": "S1",
      "verse_anchor": "9:4",
      "proposition_kind": "MORDECAI_GREAT_IN_THE_HOUSE",
      "event_specific_slots": {
        "great_one": "B1",
        "greatness_seat": "THE_KINGS_HOUSE",
        "report_of": "B1",
        "report_reach": "THE_PROVINCES",
        "reach_extent": "ALL_OF_THEM"
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
      "scene_link": "S1",
      "verse_anchor": "9:4",
      "proposition_kind": "MORDECAI_GROWING_GREATER",
      "status": "HABITUAL",
      "event_specific_slots": {
        "growing_one": "B1",
        "growth_manner": "GREATER_AND_GREATER"
      },
      "inter_proposition_links": {
        "caused_by": "P9"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P11",
      "scene_link": "S2",
      "verse_anchor": "9:5",
      "proposition_kind": "STRUCK",
      "event_specific_slots": {
        "striker": "B17",
        "struck": "B20",
        "struck_extent": "ALL_OF_THEM",
        "struck_with": ["SWORD", "SLAUGHTER", "DESTRUCTION"]
      },
      "inter_proposition_links": {
        "caused_by": "P4",
        "forward_link_to": "P12"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P12",
      "scene_link": "S2",
      "verse_anchor": "9:5",
      "proposition_kind": "STRUCK",
      "event_specific_slots": {
        "doer": "B17",
        "done_to": "B20",
        "done_in_manner": "THEIR_PLEASURE"
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
      "verse_anchor": "9:6",
      "proposition_kind": "STRUCK",
      "event_specific_slots": {
        "slayer": "B17",
        "slain": "B20",
        "slain_count": "FIVE_HUNDRED",
        "slain_at": "PL1",
        "place_qualifier": "THE_CITADEL"
      },
      "inter_proposition_links": {
        "caused_by": "P11",
        "forward_link_to": "P14"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P14",
      "scene_link": "S2",
      "verse_anchor": "9:7-9",
      "proposition_kind": "STRUCK",
      "event_specific_slots": {
        "slayer": "B17",
        "slain": "B16",
        "sons_of": "B3",
        "named_roster": [
          "Parshandatha",
          "Dalphon",
          "Aspatha",
          "Poratha",
          "Adalia",
          "Aridatha",
          "Parmashta",
          "Arisai",
          "Aridai",
          "Vaizatha"
        ],
        "roster_form": "NAMED_IN_FULL"
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
      "verse_anchor": "9:10",
      "proposition_kind": "IDENTIFIED",
      "event_specific_slots": {
        "identified": "B16",
        "identified_count": "TEN",
        "father": "B3",
        "father_patronym": "SON_OF_HAMMEDATHA",
        "father_epithet": "FOE",
        "foe_of": "B17"
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
      "verse_anchor": "9:10",
      "proposition_kind": "DECLINED",
      "event_specific_slots": {
        "restrainer": "B17",
        "withheld_spoil": "THE_PLUNDER",
        "restraint_form": "HAND_WITHHELD"
      },
      "inter_proposition_links": {
        "caused_by": "P15"
      },
      "cross_ref": "The plunder was expressly PERMITTED by the second decree (E14 P7); the refusal here reads as 'allowed-but-declined', not a bare negation — pairs with the Scene 2 must-preserve significant_absence.",
      "cb_flags": [],
      "figure_flags": []
    }
  ]
}
```

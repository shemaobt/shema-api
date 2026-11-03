---
type: "sta-meaning-coordinates"
pericope: "E01"
pericope-title: "The empire on display: the king's two banquets and the queen's feast"
source-meaning-map: [[E01-Esther-1-1-9]]
status: "valid"
pilot: "pilot-2"
---

# E01 — Esther 1:1–9 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "esther_pericope_01_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",

  "header": {
    "bcv": "Esther 1:1-9",
    "pericope_title": "The empire on display: the king's two banquets and the queen's feast",
    "book_context_ref": "esther_pilot_BCD_v0_1",
    "source_meaning_map_ref": "E01-Esther-1-1-9",
    "source_language": "Biblical Hebrew"
  },

  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "One moment-level framing override at v.1 (NARRATIVE_FRAMING axis): the set opening 'in the days of Ahasuerus' lifts into the formal key of a remembered tale. No scene-level overrides. v.8's wine-protocol is kept INFORMAL_CASUAL — the narrator describes the rule from outside, no decree is voiced.",
      "scene_level": null,
      "moment_level": [
        {
          "verse": "1:1",
          "framing_override": "COMMUNITY_MEMORY",
          "genre_override": null,
          "genre_group_override": null
        }
      ]
    }
  },

  "level_1": {
    "arc_elements": [
      "IMPERIAL_FRAME",
      "ROYAL_DISPLAY",
      "PUBLIC_FEAST",
      "ESCALATING_SPLENDOUR",
      "PARALLEL_QUEEN_FEAST"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "PHYSICAL_LOCATION",
      "INSTITUTIONAL_CONTEXT",
      "TEMPORAL_CONTEXT",
      "HISTORICAL_ERA_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT"
    ],
    "tone_elements": [
      "ADMIRING",
      "IRONIC",
      "ACCUMULATING",
      "CEREMONIAL",
      "SLOWED"
    ],
    "pace_elements": [
      "DELIBERATE",
      "ACCUMULATES",
      "TURNING_ASIDE_AT_CLOSE"
    ],
    "communicative_function_elements": [
      "OPENS",
      "ESTABLISHES",
      "STAGES",
      "PLANTS",
      "WITHHOLDS"
    ]
  },

  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "1:1-2",
      "scene_kind": "OPENING_CHRONICLE_SCENE",
      "scene_communicative_purpose": "Establishes the king, the imperial span, and the throne — the world the book is set in.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT",
            "referential_form": "AHASUERUS_THE_KING"
          }
        ]
      },

      "places_in_scene": {
        "_note": "The realm-span institution I5 (the 127 provinces) is carried as an L3 slot (P1.realm_span), not an in-scene place, since institution codes are not scene places.",
        "entries": [
          {
            "place_id": "PL1"
          },
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
            "object_id": "TH_THRONE"
          }
        ]
      },

      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_DAYS_OF_AHASUERUS"
          }
        ]
      },

      "significant_absence": "No God is named, and no Israelite or Jew is in view. The book opens entirely inside a foreign empire, with no word of the people whose story this will become — and no word of the One the book will never name."
    },

    {
      "scene_id": "S2",
      "verse_range": "1:3-4",
      "scene_kind": "MEAL_SCENE",
      "scene_communicative_purpose": "Shows the king displaying his wealth and power to the empire's nobility across half a year.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT",
            "referential_form": "THE_KING"
          },
          {
            "being_id": "B18",
            "role_in_scene": "NOBLES",
            "presence": "PRESENT",
            "referential_form": "HIS_PRINCES_AND_SERVANTS"
          },
          {
            "being_id": "B19",
            "role_in_scene": "NOBLES",
            "presence": "PRESENT",
            "referential_form": "ARMY_NOBLES_AND_PROVINCIAL_PRINCES"
          }
        ]
      },

      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL6"
          },
          {
            "place_id": "PL7"
          }
        ]
      },

      "objects_in_scene": {
        "_note": "The banquet institution I1 (mishteh) is carried as an L3 slot (P3.banquet_institution), not an in-scene object; no persistent scene-object stands apart from the feast itself.",
        "entries": null
      },

      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_THIRD_YEAR_OF_THE_REIGN"
          }
        ]
      },

      "significant_absence": "The feast has no stated reason beyond display — no festival, no victory, no occasion is named. Six months of banqueting are recorded with no event inside them but the showing itself."
    },

    {
      "scene_id": "S3",
      "verse_range": "1:5-8",
      "scene_kind": "MEAL_SCENE",
      "scene_communicative_purpose": "Shows the king's lavish public feast for the whole capital, where even the wine runs by royal law.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT",
            "referential_form": "THE_KING"
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
        "_note": "The banquet institution I1 (mishteh) and the law I2 (dat) are carried as L3 slots (P5.banquet_institution, P8.governing_rule), not in-scene objects; the gold/silver furnishings and wine are descriptive content carried in L3 (P6, P7), not registry objects.",
        "entries": null
      },

      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; the seven days run on directly from the close of the 180-day feast ('when these days were fulfilled').",
        "entries": null
      },

      "significant_absence": "For all the gold and wine, nothing is eaten, said, or done that the story will turn on — the scene is pure display. And no god is thanked, invoked, or named over any of it."
    },

    {
      "scene_id": "S4",
      "verse_range": "1:9",
      "scene_kind": "MEAL_SCENE",
      "scene_communicative_purpose": "Introduces the queen and her separate women's feast — the hinge into the coming conflict.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B5",
            "role_in_scene": "QUEEN",
            "presence": "PRESENT",
            "referential_form": "VASHTI_THE_QUEEN"
          },
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "REFERENCED",
            "referential_form": "KING_AHASUERUS"
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
        "_note": "The banquet institution I1 (mishteh) is carried as an L3 slot (P9.banquet_institution), not an in-scene object.",
        "entries": null
      },

      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; the women's feast runs concurrently with the king's seven-day feast.",
        "entries": null
      },

      "significant_absence": "Nothing is said of why the queen's feast is held apart, or of any contact between the two. The verse opens with 'also' and closes the pericope on a separation it does not explain — the gap the next scene (the summons of Vashti) will force open."
    }
  ],

  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "1:1",
      "proposition_kind": "TIME_ANCHOR_ESTABLISHED",
      "event_specific_slots": {
        "reigning_king": "B4",
        "eastern_limit": "PL2",
        "western_limit": "PL3",
        "realm_span": "THE_PROVINCES",
        "province_count": "127"
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
      "verse_anchor": "1:2",
      "proposition_kind": "SAT",
      "event_specific_slots": {
        "enthroned_king": "B4",
        "kingly_capacity": "KING",
        "seat_taken": "TH_THRONE",
        "seat_belonging": "ROYAL",
        "throne_place": "PL1",
        "place_qualifier": "THE_CITADEL"
      },
      "inter_proposition_links": {
        "caused_by": "P1"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P3",
      "scene_link": "S2",
      "verse_anchor": "1:3",
      "proposition_kind": "ATE",
      "event_specific_slots": {
        "banquet_host": "B4",
        "banquet_named": "MISHTEH",
        "reign_year": "TM_THIRD_YEAR_OF_THE_REIGN",
        "invited_court": "B18",
        "invited_officialdom": "B19",
        "convened_position": "BEFORE_HIM"
      },
      "inter_proposition_links": {
        "forward_link_to": "P4"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P4",
      "scene_link": "S2",
      "verse_anchor": "1:4",
      "proposition_kind": "SHOWED",
      "event_specific_slots": {
        "displaying_king": "B4",
        "displayed_riches": "RICHES",
        "riches_belonging": "ROYAL_GLORY",
        "displayed_splendour": "SPLENDOUR",
        "splendour_belonging": "HIS_GREATNESS",
        "display_duration": "180_DAYS"
      },
      "inter_proposition_links": {
        "purpose_of": "P3"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P5",
      "scene_link": "S3",
      "verse_anchor": "1:5",
      "proposition_kind": "ATE",
      "event_specific_slots": {
        "banquet_host": "B4",
        "banquet_named": "MISHTEH",
        "timing_marker": "DAYS_FULFILLED",
        "feasted_populace": "ALL_THE_PEOPLE",
        "populace_place": "PL1",
        "populace_high": "THE_GREAT",
        "populace_low": "THE_SMALL",
        "feast_duration": "SEVEN_DAYS",
        "feast_venue": "GARDEN_COURT",
        "venue_belonging": "THE_KINGS_PAVILION"
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
      "scene_link": "S3",
      "verse_anchor": "1:6",
      "proposition_kind": "SHOWED",
      "event_specific_slots": {
        "described_furnishings": "THE_FURNISHINGS",
        "hangings": ["WHITE_COTTON", "FINE_LINEN", "VIOLET"],
        "hangings_held_by": "CORDS",
        "cord_material": ["FINE_LINEN", "PURPLE"],
        "ring_material": "SILVER",
        "pillar_material": "ALABASTER",
        "couches": ["GOLD", "SILVER"],
        "pavement": ["PORPHYRY", "MARBLE", "MOTHER_OF_PEARL", "COSTLY_STONE"]
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
      "scene_link": "S3",
      "verse_anchor": "1:7",
      "proposition_kind": "ATE",
      "event_specific_slots": {
        "drink_served": "WINE",
        "wine_quality": "ROYAL",
        "serving_vessels": "VESSELS",
        "vessel_material": "GOLD",
        "vessel_variety": "DIFFERING",
        "wine_quantity": "ABUNDANT",
        "wine_measure": "THE_KINGS_BOUNTY"
      },
      "inter_proposition_links": {
        "caused_by": "P5",
        "forward_link_to": "P8"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P8",
      "scene_link": "S3",
      "verse_anchor": "1:8",
      "proposition_kind": "INSTRUCTION",
      "status": "NORM",
      "event_specific_slots": {
        "ordaining_king": "B4",
        "bound_household": "EVERY_OFFICER",
        "household_belonging": "HIS_HOUSE",
        "governed_matter": "THE_DRINKING",
        "governing_rule": "THE_LAW",
        "drinking_components": [
          {
            "action": "GAVE",
            "granting_king": "B4",
            "granted_freedom": "TO_DRINK",
            "permitted_party": "EACH_MAN",
            "constraint": "NONE_COMPELLING",
            "freedom_extent": "EACH_MANS_PLEASURE",
            "status": "PERMITTED",
            "speech_act": "GRANTS_PERMISSION_TO_DO"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P7"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P9",
      "scene_link": "S4",
      "verse_anchor": "1:9",
      "proposition_kind": "ATE",
      "event_specific_slots": {
        "banquet_host": "B5",
        "host_capacity": "QUEEN",
        "banquet_named": "MISHTEH",
        "feasted_party": "THE_WOMEN",
        "feast_venue": "THE_ROYAL_HOUSE",
        "venue_belonging": "KING_AHASUERUS"
      },
      "inter_proposition_links": {
        "paired_with": "P5"
      },
      "cb_flags": [],
      "figure_flags": []
    }
  ]
}
```

---
type: "sta-meaning-coordinates"
pericope: "J01"
pericope-title: "The word comes to Jonah, and Jonah flees"
source-meaning-map: [[J01-Jonah-1-1-3]]
status: "valid"
pilot: "pilot-2"
drafter: "claude-opus-4-8 · fm-drafter prompt (see _spec/pins.json) · machine-drafted, ruled by Marcia (SC-0064 batch ruling §A–§E + arc_element, 2026-06-19); MODEL_DRAFTED_REVIEWER_RULED"
---

# J01 — Jonah 1:1–3 — MEANING_COORDINATES

> Judgment gaps filled by the SC-0063 drafter (`tripod draft --live`); the merge layer enforced the patch-only contract. NOT canon until ruled.

```json
{
  "sta_id": "jonah_pericope_01_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Jonah 1:1-3",
    "pericope_title": "The word comes to Jonah, and Jonah flees",
    "book_context_ref": "jonah_pilot_BCD_v0_3",
    "source_meaning_map_ref": "J01-Jonah-1-1-3",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "MM Section 1 marks YHWH's command at v.2 lifting to ELDER_AUTHORITY; the narrator voice around it stays INFORMAL_CASUAL. Encoded at moment level (v.2) rather than coloring the whole of S1 (which also carries the casual v.1 word-event formula). No NARRATIVE_FRAMING shift is marked here.",
      "scene_level": null,
      "moment_level": [
        {
          "verse": "1:2",
          "override_value": "ELDER_AUTHORITY"
        }
      ]
    }
  },
  "level_1": {
    "arc_elements": [
      "DIVINE_COMMISSION",
      "REFUSAL_OF_COMMISSION",
      "FLIGHT_FROM_PRESENCE"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "PHYSICAL_LOCATION",
      "KINSHIP_CONTEXT",
      "DIVINE_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT"
    ],
    "tone_elements": [
      "ECONOMICAL",
      "RESTRAINED",
      "URGENT",
      "UNSETTLED_AT_CLOSE"
    ],
    "pace_elements": [
      "BRISK",
      "NARROWS"
    ],
    "communicative_function_elements": [
      "OPENS",
      "ESTABLISHES",
      "PLANTS",
      "WITHHOLDS"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "1:1-2",
      "scene_kind": "COMMISSIONING_SCENE",
      "scene_communicative_purpose": "Gives the command that the rest of the pericope answers: the caller, the called, the city, and the reason.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B1",
            "role_in_scene": "PROPHET",
            "presence": "PRESENT",
            "referential_form": "JONAH_SON_OF_AMITTAI"
          },
          {
            "being_id": "B2",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "PRESENT"
          },
          {
            "being_id": "B3",
            "role_in_scene": "PATRONYMIC_REFERENT",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B5",
            "role_in_scene": "TOWNSPEOPLE",
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
        "entries": [
          {
            "object_id": "CB_0051"
          },
          {
            "object_id": "CB_0052"
          }
        ]
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "The narrator names \"their evil\" but never says what it is — the wrongdoing is asserted, not described. Nothing is told of who Jonah is or why he is the one sent."
    },
    {
      "scene_id": "S2",
      "verse_range": "1:3",
      "scene_kind": "FLIGHT_SCENE",
      "scene_communicative_purpose": "Records the flight: the prophet's refusal, carried out as a journey the opposite way.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B1",
            "role_in_scene": "FUGITIVE",
            "presence": "PRESENT"
          },
          {
            "being_id": "B2",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B4",
            "role_in_scene": "CREW",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B3",
            "role_in_scene": "PATRONYMIC_REFERENT",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
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
            "object_id": "O1"
          },
          {
            "object_id": "O2"
          },
          {
            "object_id": "CB_0052"
          }
        ]
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "The narrator gives no reason for the flight. Jonah says nothing — no refusal, no argument, no prayer. Why he runs is left entirely unsaid."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "1:1",
      "proposition_kind": "WORD_OF_YHWH_CAME",
      "event_specific_slots": {
        "word_from": "B2",
        "word_came_to": "B1",
        "patronymic": "B3",
        "addressed_referential_form": "JONAH_SON_OF_AMITTAI"
      },
      "inter_proposition_links": {
        "forward_link_to": "P2"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0196"
      ]
    },
    {
      "prop_id": "P2",
      "scene_link": "S1",
      "verse_anchor": "1:2",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "commander": "B2",
        "commanded": "B1",
        "command_components": [
          {
            "action": "DIRECTED",
            "step_order": "FIRST",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "action": "DIRECTED",
            "step_order": "SECOND",
            "destination": "PL1",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "action": "DIRECTED",
            "step_order": "THIRD",
            "target": "PL1",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          }
        ],
        "city_descriptor": "THE_GREAT_CITY",
        "indicted_party": "B5",
        "evil": "CB_0051",
        "divine_presence": "CB_0052"
      },
      "inter_proposition_links": {
        "caused_by": "P1",
        "forward_link_to": "P3"
      },
      "cb_flags": [
        "CB_0051",
        "CB_0052"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P3",
      "scene_link": "S2",
      "verse_anchor": "1:3a",
      "proposition_kind": "FLED",
      "event_specific_slots": {
        "fleer": "B1",
        "flight_destination": "PL2",
        "fled_from_presence": "CB_0052",
        "fled_from_being": "B2",
        "flight_directionality": "OPPOSITE_OF_COMMISSION"
      },
      "inter_proposition_links": {
        "caused_by": "P2",
        "forward_link_to": "P4"
      },
      "cb_flags": [
        "CB_0052"
      ],
      "figure_flags": [
        "FIG_0197"
      ]
    },
    {
      "prop_id": "P4",
      "scene_link": "S2",
      "verse_anchor": "1:3b",
      "proposition_kind": "WENT_DOWN",
      "event_specific_slots": {
        "goer_down": "B1",
        "descent_destination": "PL3",
        "found_vessel": "O1",
        "vessel_destination": "PL2",
        "descent_marker": "GOING_DOWN"
      },
      "inter_proposition_links": {
        "caused_by": "P3",
        "forward_link_to": "P5"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0198"
      ]
    },
    {
      "prop_id": "P5",
      "scene_link": "S2",
      "verse_anchor": "1:3c",
      "proposition_kind": "EMBARKED",
      "event_specific_slots": {
        "payer": "B1",
        "fare_paid": "O2",
        "boarded_vessel": "O1",
        "descent_marker": "GOING_DOWN",
        "sail_companions": "B4",
        "intended_destination": "PL2",
        "fled_from_presence": "CB_0052",
        "fled_from_being": "B2"
      },
      "inter_proposition_links": {
        "caused_by": "P4"
      },
      "cb_flags": [
        "CB_0052"
      ],
      "figure_flags": [
        "FIG_0197",
        "FIG_0198"
      ]
    }
  ]
}
```

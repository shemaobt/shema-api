---
type: "sta-meaning-coordinates"
pericope: "J05"
pericope-title: "The qiqayon and the last question"
source-meaning-map: [[J05-Jonah-4-1-11]]
status: "valid"
pilot: "pilot-2"
drafter: "claude-opus-4-8 · fm-drafter prompt (see _spec/pins.json) · machine-drafted, ruled by Marcia (SC-0064 batch ruling §A–§E + arc_element, 2026-06-19); MODEL_DRAFTED_REVIEWER_RULED"
---

# J05 — Jonah 4:1–11 — MEANING_COORDINATES

> Judgment gaps filled by the SC-0063 drafter (`tripod draft --live`); the merge layer enforced the patch-only contract. NOT canon until ruled.

```json
{
  "sta_id": "jonah_pericope_05_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Jonah 4:1-11",
    "pericope_title": "The qiqayon and the last question",
    "book_context_ref": "jonah_pilot_BCD_v0_3",
    "source_meaning_map_ref": "J05-Jonah-4-1-11",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "Jonah's prayer at 4:2-3 lifts into RELIGIOUS_WORSHIP (prayer addressed to YHWH by name, though furious — the register carries the address, not the mood); the surrounding question-and-answer exchanges (4:4, 4:9, 4:10-11) stay in the pericope's INFORMAL_CASUAL. No scene-level overrides.",
      "scene_level": null,
      "moment_level": [
        {
          "verse": "4:2",
          "override_value": "RELIGIOUS_WORSHIP"
        },
        {
          "verse": "4:3",
          "override_value": "RELIGIOUS_WORSHIP"
        }
      ]
    }
  },
  "level_1": {
    "arc_elements": [
      "ANGER_AT_DIVINE_MERCY",
      "MOTIVE_DISCLOSED",
      "DEATH_WISH",
      "DIVINE_PROBING_QUESTION",
      "WITHDRAWAL_TO_WATCH",
      "APPOINTED_OBJECT_LESSON",
      "LOSS_OF_COMFORT",
      "ARGUMENT_FROM_LESSER_TO_GREATER",
      "UNANSWERED_QUESTION_CLOSE"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "PHYSICAL_LOCATION",
      "DIVINE_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT",
      "PRIOR_PERICOPE_CARRY_FORWARD",
      "PRIOR_ACTION_CONTEXT"
    ],
    "tone_elements": [
      "HEATED",
      "ECONOMICAL",
      "WARM",
      "STILLED",
      "UNRESOLVED_AT_CLOSE"
    ],
    "pace_elements": [
      "HOLDS",
      "BRISK",
      "WIDENS",
      "SETTLES"
    ],
    "communicative_function_elements": [
      "REACTIVATES",
      "STAGES",
      "CLOSES"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "4:1-3",
      "scene_kind": "ANGRY_PRAYER_SCENE",
      "scene_communicative_purpose": "Supplies the reason the whole book withheld: Jonah ran because he knew the creed — and the scene turns Israel's oldest praise into a prophet's accusation. It sets the question the rest of the chapter answers with a plant.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B1",
            "role_in_scene": "COMPLAINANT",
            "presence": "PRESENT"
          },
          {
            "being_id": "B2",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "PRESENT",
            "referential_form": "YHWH"
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
            "object_id": "CB_0057"
          },
          {
            "object_id": "CB_0011"
          },
          {
            "object_id": "CB_0058"
          }
        ]
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "The missing motive of J01 is given here — and the narrator lets Jonah's own mouth give it, with no comment, no rebuke, and no defense of him. What exactly Jonah feared — Nineveh spared as such, or his word undone, or mercy reaching Israel's enemy — is left folded inside the creed; the text never unpacks it."
    },
    {
      "scene_id": "S2",
      "verse_range": "4:4-5",
      "scene_kind": "WATCH_POST_SCENE",
      "scene_communicative_purpose": "Sets the question of the chapter and lets it hang: Jonah answers with his feet, not his mouth. The watcher's post east of the city stages the lesson — a man, his anger, his own little shade, and the city below.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B2",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "PRESENT"
          },
          {
            "being_id": "B1",
            "role_in_scene": "WATCHER",
            "presence": "PRESENT"
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
            "object_id": "O13"
          }
        ]
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "Jonah gives no answer to the question — none at all. And the narrator never explains why he still watches the city after God has already relented — whether he hopes the doom will yet fall is left entirely unsaid."
    },
    {
      "scene_id": "S3",
      "verse_range": "4:6-8",
      "scene_kind": "APPOINTMENT_SCENE",
      "scene_communicative_purpose": "Builds the lesson out of appointings: the comfort given and loved, then taken blow by blow — plant, worm, wind, sun — until the prophet's death-wish returns over a plant. The book's one \"great joy\" stands here, and it is for shade.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B2",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "PRESENT",
            "referential_form": "YHWH_ELOHIM"
          },
          {
            "being_id": "B1",
            "role_in_scene": "COMPLAINANT",
            "presence": "PRESENT"
          },
          {
            "being_id": "B13",
            "role_in_scene": "APPOINTED_CREATURE",
            "presence": "PRESENT"
          }
        ]
      },
      "places_in_scene": {
        "entries": []
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "O11"
          },
          {
            "object_id": "O12"
          }
        ]
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "Jonah's joy is for the qiqayon — the spared city stirs nothing in him; the narrator sets the great joy beside the great evil of 4:1 without a word of comment. Why the plant is killed is never explained inside the scene — the meaning waits for YHWH's argument."
    },
    {
      "scene_id": "S4",
      "verse_range": "4:9-11",
      "scene_kind": "CLOSING_ARGUMENT_SCENE",
      "scene_communicative_purpose": "Closes the book by refusing to close it: the two pities are set side by side — a plant against a city — and the question is left standing in the air. The hearer, not Jonah, is the one who must answer it.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B2",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "PRESENT",
            "referential_form": "YHWH"
          },
          {
            "being_id": "B1",
            "role_in_scene": "COMPLAINANT",
            "presence": "PRESENT"
          },
          {
            "being_id": "B5",
            "role_in_scene": "PEOPLE",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B12",
            "role_in_scene": "ANIMAL_REFERENT",
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
            "object_id": "O11"
          }
        ]
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "The book ends on an unanswered question — Jonah says nothing, the narrator adds nothing, and no verdict is passed on the prophet. What became of Jonah, and of Nineveh after, is never told. The last word of the book belongs to the animals, and the text leaves it there."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "4:1",
      "proposition_kind": "ANGER_KINDLED",
      "event_specific_slots": {
        "displeased_party": "B1",
        "displeasing_event": "MERCY_SPARING_NINEVEH",
        "displeasure_magnitude": "GREAT",
        "anger_state": "BURNED"
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
      "verse_anchor": "4:2",
      "proposition_kind": "PRAYED",
      "event_specific_slots": {
        "pray_er": "B1",
        "addressed_deity": "B2",
        "speech_act": "ASKS_RHETORICAL_QUESTION_AS_PROTEST"
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
      "verse_anchor": "4:2",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "speaker": "B1",
        "flight_destination": "PL2",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P4"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P4",
      "scene_link": "S1",
      "verse_anchor": "4:2",
      "proposition_kind": "CREED_RECITED",
      "event_specific_slots": {
        "reciter": "B1",
        "creed_about": "B2",
        "creed_rhetorical_function": "ACCUSATION",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P5"
      },
      "cb_flags": [
        "CB_0011",
        "CB_0057",
        "CB_0058"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P5",
      "scene_link": "S1",
      "verse_anchor": "4:3",
      "proposition_kind": "APPEAL",
      "event_specific_slots": {
        "petitioner": "B1",
        "addressed_deity": "B2",
        "speech_act": "DIRECTS_HEARER_TO_DO"
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
      "verse_anchor": "4:4",
      "proposition_kind": "QUESTIONED",
      "event_specific_slots": {
        "questioner": "B2",
        "questioned_party": "B1",
        "question_about": "JONAHS_ANGER",
        "speech_act": "ASKS_RHETORICAL_QUESTION_AS_DISSUASION"
      },
      "inter_proposition_links": {
        "caused_by": "P5",
        "paired_with": "P17",
        "forward_link_to": "P7"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0206"
      ]
    },
    {
      "prop_id": "P7",
      "scene_link": "S2",
      "verse_anchor": "4:5",
      "proposition_kind": "DEPARTED",
      "event_specific_slots": {
        "goer": "B1",
        "exited_from": "PL1",
        "final_position": "EAST_OF_CITY",
        "movement_components": [
          {
            "action": "WENT_OUT",
            "goer": "B1",
            "from": "PL1",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "POSITIONED",
            "sitter": "B1",
            "position": "EAST_OF_CITY",
            "speech_act": "STATES_AS_TRUE"
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
      "scene_link": "S2",
      "verse_anchor": "4:5",
      "proposition_kind": "MADE_SHELTER",
      "event_specific_slots": {
        "builder": "B1",
        "shelter_built": "O13",
        "shelter_purpose": "SHADE",
        "post_build_position": {
          "action": "SAT"
        },
        "watch_intent": "SEE_CITY_FATE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P9"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P9",
      "scene_link": "S3",
      "verse_anchor": "4:6",
      "proposition_kind": "APPOINTED",
      "event_specific_slots": {
        "appointer": "B2",
        "appointer_referential_form": "YHWH_ELOHIM",
        "appointed_creature": "O11",
        "appointment_intent": "SHADE_OVER_HEAD"
      },
      "inter_proposition_links": {
        "forward_link_to": "P10"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0205"
      ]
    },
    {
      "prop_id": "P10",
      "scene_link": "S3",
      "verse_anchor": "4:6",
      "proposition_kind": "ROSE",
      "event_specific_slots": {
        "riser": "O11",
        "rose_over": "B1",
        "became": "SHADE_OVER_HEAD",
        "deliverance_intent": "FROM_HIS_EVIL"
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
      "verse_anchor": "4:6",
      "proposition_kind": "REJOICED",
      "event_specific_slots": {
        "rejoicer": "B1",
        "rejoiced_over": "O11",
        "joy_magnitude": "GREAT"
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
      "scene_link": "S3",
      "verse_anchor": "4:7",
      "proposition_kind": "APPOINTED",
      "event_specific_slots": {
        "appointer": "B2",
        "appointer_referential_form": "ELOHIM",
        "appointed_creature": "B13",
        "appointment_timing": "DAWN_NEXT_DAY"
      },
      "inter_proposition_links": {
        "forward_link_to": "P13"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0205"
      ]
    },
    {
      "prop_id": "P13",
      "scene_link": "S3",
      "verse_anchor": "4:7",
      "proposition_kind": "STRUCK",
      "event_specific_slots": {
        "striker": "B13",
        "struck_target": "O11",
        "result": "WITHERED"
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
      "verse_anchor": "4:8",
      "proposition_kind": "APPOINTED",
      "event_specific_slots": {
        "appointer": "B2",
        "appointer_referential_form": "ELOHIM",
        "appointed_force": "O12",
        "force_quality": "CUTTING_EAST_WIND",
        "appointment_timing": "WHEN_SUN_ROSE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P15"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0205"
      ]
    },
    {
      "prop_id": "P15",
      "scene_link": "S3",
      "verse_anchor": "4:8",
      "proposition_kind": "STRUCK",
      "event_specific_slots": {
        "striker": "SUN",
        "struck_target": "JONAHS_HEAD",
        "afflicted_party": "B1",
        "result": "FAINTED"
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
      "scene_link": "S3",
      "verse_anchor": "4:8",
      "proposition_kind": "APPEAL",
      "event_specific_slots": {
        "petitioner": "B1",
        "speech_act": "STATES_HOPED_FOR_CONDITION"
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
      "verse_anchor": "4:9",
      "proposition_kind": "QUESTIONED",
      "event_specific_slots": {
        "questioner": "B2",
        "questioner_referential_form": "ELOHIM",
        "questioned_party": "B1",
        "question_about": "ANGER_OVER_PLANT",
        "speech_act": "ASKS_RHETORICAL_QUESTION_AS_DISSUASION"
      },
      "inter_proposition_links": {
        "caused_by": "P16",
        "paired_with": "P6",
        "forward_link_to": "P18"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0206"
      ]
    },
    {
      "prop_id": "P18",
      "scene_link": "S4",
      "verse_anchor": "4:9",
      "proposition_kind": "ANSWERED",
      "event_specific_slots": {
        "answerer": "B1",
        "answered_to": "B2",
        "intensity": "EVEN_TO_DEATH",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "paired_with": "P17",
        "forward_link_to": "P19"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P19",
      "scene_link": "S4",
      "verse_anchor": "4:10",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "speaker": "B2",
        "speaker_referential_form": "YHWH",
        "addressed_party": "B1",
        "pitying_party": "B1",
        "pitied": "O11",
        "comparison_rank": "LESSER_TERM",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P18",
        "forward_link_to": "P20"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P20",
      "scene_link": "S4",
      "verse_anchor": "4:11",
      "proposition_kind": "QUESTIONED",
      "event_specific_slots": {
        "questioner": "B2",
        "questioner_referential_form": "YHWH",
        "pitied": "PL1",
        "city_descriptor": "GREAT_CITY",
        "inhabitants": "B5",
        "comparison_rank": "GREATER_TERM",
        "speech_act": "ASKS_RHETORICAL_QUESTION_AS_PROTEST"
      },
      "inter_proposition_links": {
        "forward_link_to": "P21"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P21",
      "scene_link": "S4",
      "verse_anchor": "4:11",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "speaker": "B2",
        "appended_to_question": "P20",
        "added_group": "B12",
        "added_descriptor": "MANY_ANIMALS",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "back_reference_to_proposition": "P20"
      },
      "cb_flags": [],
      "figure_flags": []
    }
  ]
}
```

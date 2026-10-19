---
type: "sta-meaning-coordinates"
pericope: "J04"
pericope-title: "Nineveh believes, and God relents"
source-meaning-map: [[J04-Jonah-2-10-3-10]]
status: "valid"
pilot: "pilot-2"
drafter: "claude-opus-4-8 · fm-drafter prompt (see _spec/pins.json) · machine-drafted, ruled by Marcia (SC-0064 batch ruling §A–§E + arc_element, 2026-06-19); MODEL_DRAFTED_REVIEWER_RULED"
---

# J04 — Jonah 2:10–3:10 — MEANING_COORDINATES

> Judgment gaps filled by the SC-0063 drafter (`tripod draft --live`); the merge layer enforced the patch-only contract. NOT canon until ruled.

```json
{
  "sta_id": "jonah_pericope_04_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Jonah 2:10-3:10",
    "pericope_title": "Nineveh believes, and God relents",
    "book_context_ref": "jonah_pilot_BCD_v0_3",
    "source_meaning_map_ref": "J04-Jonah-2-10-3-10",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "Three moment-level register lifts inside quoted speech, per MM Section 1; the narrator's own voice stays INFORMAL_CASUAL throughout. No scene-level overrides.",
      "scene_level": null,
      "moment_level": [
        {
          "verse": "3:2",
          "override_value": "ELDER_AUTHORITY"
        },
        {
          "verse": "3:4",
          "override_value": "FORMAL_OFFICIAL"
        },
        {
          "verse": "3:7-9",
          "override_value": "FORMAL_OFFICIAL"
        }
      ]
    }
  },
  "level_1": {
    "arc_elements": [
      "DELIVERANCE_TO_DRY_LAND",
      "RECOMMISSION",
      "OBEDIENT_DEPARTURE",
      "ORACLE_PROCLAMATION",
      "MASS_REPENTANCE",
      "ROYAL_DECREE",
      "DIVINE_RELENTING"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "PRIOR_PERICOPE_CARRY_FORWARD",
      "PRIOR_ACTION_CONTEXT",
      "PHYSICAL_LOCATION",
      "INSTITUTIONAL_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT",
      "DIVINE_CONTEXT"
    ],
    "tone_elements": [
      "ECONOMICAL",
      "RESTRAINED",
      "WONDER_UNDERSTATED",
      "STILLED",
      "ANTICIPATORY"
    ],
    "pace_elements": [
      "BRISK",
      "QUIETLY_ACCELERATING",
      "WIDENS",
      "SETTLES"
    ],
    "communicative_function_elements": [
      "REACTIVATES",
      "ADVANCES",
      "CLOSES",
      "PLANTS",
      "WITHHOLDS"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "2:11",
      "scene_kind": "DELIVERANCE_SCENE",
      "scene_communicative_purpose": "Closes the fish episode in a single motion and puts the prophet back where an errand can start: the rescue is complete, the road to Nineveh is open.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B2",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "PRESENT"
          },
          {
            "being_id": "B7",
            "role_in_scene": "APPOINTED_CREATURE",
            "presence": "PRESENT"
          },
          {
            "being_id": "B1",
            "role_in_scene": "PROPHET",
            "presence": "PRESENT"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL5"
          }
        ]
      },
      "objects_in_scene": {
        "entries": []
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "The fish is gone in one verse — no wonder, no description, no afterword. Nothing is said of the beach, of Jonah's state, or of any word between YHWH and the man — the next thing the story gives him is the command."
    },
    {
      "scene_id": "S2",
      "verse_range": "3:1-2",
      "scene_kind": "COMMISSIONING_SCENE",
      "scene_communicative_purpose": "Restarts the book's errand word for word: the same get-up, the same go, the same call. The story offers the prophet the exact choice he fled — and waits.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B2",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "PRESENT"
          },
          {
            "being_id": "B1",
            "role_in_scene": "PROPHET",
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
        "entries": []
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "There is no rebuke and no mention of the flight — the word resumes as if nothing had happened. The content of the message itself is withheld here: \"the call that I am telling you,\" not yet the words."
    },
    {
      "scene_id": "S3",
      "verse_range": "3:3-4",
      "scene_kind": "PROCLAMATION_SCENE",
      "scene_communicative_purpose": "Completes the broken arc of J01 — got up, went, cried out — and drops the whole message in five words: a deadline and a doom, with the door of meaning left open (\"overthrown\" can be ruin, or turning over).",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B1",
            "role_in_scene": "PROPHET",
            "presence": "PRESENT"
          },
          {
            "being_id": "B2",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "REFERENCED",
            "referential_form": "BY_THE_WORD_OF_YHWH"
          },
          {
            "being_id": "B9",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "REFERENCED",
            "referential_form": "ELOHIM"
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
        "entries": []
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "The oracle has no reason, no call to repent, no offer of mercy, and no \"unless\" — doom and a date, nothing else. The narrator never says Jonah preached more than this. What Jonah hoped or feared as he cried it is withheld entirely."
    },
    {
      "scene_id": "S4",
      "verse_range": "3:5",
      "scene_kind": "REPENTANCE_SCENE",
      "scene_communicative_purpose": "Gives the oracle its answer before the throne ever hears it: belief, fasting, sackcloth — the people move first, and the completeness (\"greatest to least\") is the point.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B5",
            "role_in_scene": "TOWNSPEOPLE",
            "presence": "PRESENT",
            "referential_form": "GREATEST_TO_LEAST"
          },
          {
            "being_id": "B9",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "REFERENCED",
            "referential_form": "ELOHIM"
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
            "object_id": "O9"
          }
        ]
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "They believe God — Jonah is not named in their believing, and no sign, wonder, or reason is given for it. Five words from a stranger, and a city turns; the narrator offers no explanation at all."
    },
    {
      "scene_id": "S5",
      "verse_range": "3:6-9",
      "scene_kind": "DECREE_SCENE",
      "scene_communicative_purpose": "Carries the city's turning to its top and its edges: the king goes lowest, the decree reaches widest — out past the people to the very herds. And it names the hope the whole passage rides on, in a pagan king's mouth: who knows? God may relent.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B10",
            "role_in_scene": "KING",
            "presence": "PRESENT",
            "referential_form": "UNNAMED_KING"
          },
          {
            "being_id": "B11",
            "role_in_scene": "NOBLES",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B5",
            "role_in_scene": "TOWNSPEOPLE",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B12",
            "role_in_scene": "LIVESTOCK",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B9",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "REFERENCED",
            "referential_form": "ELOHIM"
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
            "object_id": "O9"
          },
          {
            "object_id": "O10"
          },
          {
            "object_id": "CB_0057"
          }
        ]
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "The king is never named, and no word of his is spoken to Jonah — prophet and king never meet. The decree commands turning from \"his evil way,\" yet no one in the story ever says what Nineveh's evil was. The hope is bare — \"who knows?\" — with no promise to stand on; the king decrees repentance without any assurance it will work."
    },
    {
      "scene_id": "S6",
      "verse_range": "3:10",
      "scene_kind": "DIVINE_RELENTING_SCENE",
      "scene_communicative_purpose": "Lands the book's theology in one verse, on one repeated word: they turn from their evil, and God turns from his. The oracle's \"overthrown\" comes true the second way — the city is turned over, not torn down.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B9",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "PRESENT",
            "referential_form": "ELOHIM"
          },
          {
            "being_id": "B5",
            "role_in_scene": "TOWNSPEOPLE",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "entries": []
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0051"
          },
          {
            "object_id": "CB_0057"
          }
        ]
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "God says nothing — the relenting is reported, not spoken; God's last words in this pericope were the charge of 3:2. Whether the forty days passed is never told. And Jonah is wholly absent from the ending — what the prophet thought of the mercy he announced is the held breath the next pericope opens on."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "2:10",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "divine_speaker": "B2",
        "addressed_creature": "B7",
        "speech_act": "DIRECTS_HEARER_TO_DO"
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
      "verse_anchor": "2:10",
      "proposition_kind": "VOMITED",
      "event_specific_slots": {
        "expeller": "B7",
        "expelled": "B1",
        "destination": "PL5"
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
      "scene_link": "S2",
      "verse_anchor": "3:1",
      "proposition_kind": "WORD_OF_YHWH_CAME",
      "event_specific_slots": {
        "from_deity": "B2",
        "word_came_to": "B1",
        "occurrence_marker": "SECOND_TIME"
      },
      "inter_proposition_links": {
        "forward_link_to": "P4"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0196"
      ]
    },
    {
      "prop_id": "P4",
      "scene_link": "S2",
      "verse_anchor": "3:2",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "divine_commander": "B2",
        "commanded_prophet": "B1",
        "destination": "PL1",
        "destination_qualifier": "GREAT_CITY",
        "charge_components": [
          {
            "action": "DIRECTED",
            "step_order": "FIRST",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "action": "DIRECTED",
            "step_order": "SECOND",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "action": "DIRECTED",
            "step_order": "THIRD",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          }
        ]
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
      "scene_link": "S3",
      "verse_anchor": "3:3",
      "proposition_kind": "ROSE",
      "event_specific_slots": {
        "obedient_prophet": "B1",
        "destination": "PL1",
        "compliance_marker": "ACCORDING_TO_WORD_OF_YHWH",
        "motion_components": [
          {
            "action": "AROSE",
            "step_order": "FIRST",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "WALKED",
            "destination": "PL1",
            "step_order": "SECOND",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P4",
        "forward_link_to": "P7"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P6",
      "scene_link": "S3",
      "verse_anchor": "3:3",
      "proposition_kind": "IDENTIFIED",
      "event_specific_slots": {
        "identified_place": "PL1",
        "magnitude_qualifier": "GREAT_CITY",
        "greatness_measured_by": "B9",
        "traversal_scale": "THREE_DAYS_WALK"
      },
      "inter_proposition_links": {},
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P7",
      "scene_link": "S3",
      "verse_anchor": "3:4",
      "proposition_kind": "ARRIVED_AT",
      "event_specific_slots": {
        "enterer": "B1",
        "place_entered": "PL1",
        "entry_marker": "BEGAN_TO_ENTER",
        "entry_extent": "ONE_DAYS_WALK"
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
      "verse_anchor": "3:4",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "proclaimer": "B1",
        "addressed_city": "PL1",
        "speech_act": "STATES_AS_TRUE"
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
      "scene_link": "S4",
      "verse_anchor": "3:5",
      "proposition_kind": "BELIEVED",
      "event_specific_slots": {
        "believers": "B5",
        "believed_one": "B9"
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
      "scene_link": "S4",
      "verse_anchor": "3:5",
      "proposition_kind": "FASTED",
      "event_specific_slots": {
        "penitents": "B5",
        "fast_response": "CALLED_A_FAST",
        "mourning_garb": "O9",
        "participation_extent": "GREATEST_TO_LEAST"
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
      "scene_link": "S5",
      "verse_anchor": "3:6",
      "proposition_kind": "HEARD_REPORT",
      "event_specific_slots": {
        "reported_to": "B10",
        "report_origin": "JONAHS_ORACLE",
        "arrival_marker": "WORD_REACHED"
      },
      "inter_proposition_links": {
        "caused_by": "P8",
        "forward_link_to": "P12"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P12",
      "scene_link": "S5",
      "verse_anchor": "3:6",
      "proposition_kind": "ROSE",
      "event_specific_slots": {
        "king": "B10",
        "descent_components": [
          {
            "action": "AROSE",
            "from_seat": "THRONE",
            "step_order": "FIRST",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "REMOVED_ROBE",
            "step_order": "SECOND",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "DONNED_SACKCLOTH",
            "garment": "O9",
            "step_order": "THIRD",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "SAT_ON_ASHES",
            "seat": "O10",
            "step_order": "FOURTH",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
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
      "scene_link": "S5",
      "verse_anchor": "3:7",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "decreer": "B10",
        "co_issuers": "B11",
        "proclamation_place": "PL1",
        "speech_act": "STATES_AS_TRUE"
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
      "scene_link": "S5",
      "verse_anchor": "3:7",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "decree_issuer": "B10",
        "fast_subjects": [
          "B5",
          "B12"
        ],
        "animal_scope": "HERD_AND_FLOCK",
        "abstention_commands": [
          {
            "action": "DIRECTED",
            "speech_act": "DIRECTS_HEARER_NOT_TO_DO"
          },
          {
            "action": "DIRECTED",
            "speech_act": "DIRECTS_HEARER_NOT_TO_DO"
          },
          {
            "action": "DIRECTED",
            "speech_act": "DIRECTS_HEARER_NOT_TO_DO"
          }
        ]
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
      "scene_link": "S5",
      "verse_anchor": "3:8",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "decree_issuer": "B10",
        "sackcloth_subjects": [
          "B5",
          "B12"
        ],
        "decree_commands": [
          {
            "action": "DIRECTED",
            "garment": "O9",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "action": "DIRECTED",
            "addressed_deity": "B9",
            "intensity": "MIGHTILY",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P13",
        "forward_link_to": "P16"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P16",
      "scene_link": "S5",
      "verse_anchor": "3:8",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "decree_issuer": "B10",
        "commanded_party": "B5",
        "turning_commands": [
          {
            "action": "DIRECTED",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "action": "DIRECTED",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P13",
        "forward_link_to": "P17"
      },
      "cb_flags": [
        "CB_0051"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P17",
      "scene_link": "S5",
      "verse_anchor": "3:9",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "hopeful_speaker": "B10",
        "deity": "B9",
        "speech_act": "STATES_HOPED_FOR_CONDITION"
      },
      "inter_proposition_links": {
        "caused_by": "P13",
        "forward_link_to": "P18"
      },
      "cb_flags": [
        "CB_0057"
      ],
      "figure_flags": [
        "FIG_0204"
      ]
    },
    {
      "prop_id": "P18",
      "scene_link": "S6",
      "verse_anchor": "3:10",
      "proposition_kind": "PERCEIVED",
      "event_specific_slots": {
        "perceiver": "B9",
        "whose_deeds": "B5",
        "perceived_content": "TURNED_FROM_EVIL"
      },
      "inter_proposition_links": {
        "caused_by": "P16",
        "forward_link_to": "P19"
      },
      "cb_flags": [
        "CB_0051"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P19",
      "scene_link": "S6",
      "verse_anchor": "3:10",
      "proposition_kind": "RELENTED",
      "event_specific_slots": {
        "relenter": "B9",
        "relented_of": "DISASTER",
        "non_execution_marker": "NOT_EXECUTED"
      },
      "inter_proposition_links": {
        "caused_by": "P18",
        "paired_with": "P17"
      },
      "cb_flags": [
        "CB_0057"
      ],
      "figure_flags": []
    }
  ]
}
```

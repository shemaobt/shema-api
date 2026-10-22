---
type: "sta-meaning-coordinates"
pericope: "P07"
pericope-title: "The gleaning brought home and the redeemer named"
source-meaning-map: [[P07-Ruth-2-17-23]]
status: "valid"
pilot: "pilot-2"
drafter: "claude-opus-4-8 · fm-drafter prompt (see _spec/pins.json) · machine-drafted, ruled by Marcia (SC-0064 batch ruling §A–§E + arc_element, 2026-06-19); MODEL_DRAFTED_REVIEWER_RULED"
---

# P07 — Ruth 2:17-23 — MEANING_COORDINATES

> Judgment gaps filled by the SC-0063 drafter (`tripod draft --live`); the merge layer enforced the patch-only contract. NOT canon until ruled.

```json
{
  "sta_id": "ruth_pericope_07_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Ruth 2:17-23",
    "pericope_title": "The gleaning brought home and the redeemer named",
    "book_context_ref": "ruth_pilot_BCD_v0_3",
    "source_meaning_map_ref": "P07-Ruth-2-17-23",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "Scene 3 (vv.19-22) shifts to INTIMATE per MM Section 1; within it Naomi's blessing at v.20 lifts to CEREMONIAL. Narrator framing at v.17, v.18, v.23 stays INFORMAL_CASUAL.",
      "scene_level": [
        {
          "scene_id": "S3",
          "override_value": "INTIMATE"
        }
      ],
      "moment_level": [
        {
          "verse": "2:20",
          "override_value": "CEREMONIAL"
        }
      ]
    }
  },
  "level_1": {
    "arc_elements": [
      "PROVISION_BROUGHT_HOME",
      "REDEEMER_RECOGNITION",
      "BLESSING_INVOCATION",
      "PROTECTIVE_INSTRUCTION",
      "CLINGING",
      "NARRATOR_FRAMING_CLOSE"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "PHYSICAL_LOCATION",
      "KINSHIP_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "TEMPORAL_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT",
      "DIVINE_CONTEXT",
      "PRIOR_PERICOPE_CARRY_FORWARD",
      "PRIOR_ACTION_CONTEXT"
    ],
    "tone_elements": [
      "CHRONICLE",
      "WARM",
      "RISING",
      "STILLED",
      "ANTICIPATORY"
    ],
    "pace_elements": [
      "STEADY",
      "RISES",
      "SETTLES",
      "WIDENS"
    ],
    "communicative_function_elements": [
      "CLOSES",
      "OPENS",
      "REACTIVATES",
      "STAGES"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "2:17",
      "scene_kind": "GLEANING_SCENE",
      "scene_communicative_purpose": "Records the size of the day's gleaning — a full ephah — as plain proof of how much favor Ruth was shown.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B9",
            "role_in_scene": "GLEANER",
            "presence": "PRESENT"
          },
          {
            "being_id": "B13",
            "role_in_scene": "FIELD_OWNER",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B3",
            "role_in_scene": "MOTHER_IN_LAW",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL5_BOAZ_PORTION"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0034"
          },
          {
            "object_id": "CB_0041"
          },
          {
            "object_id": "O12"
          },
          {
            "object_id": "O2"
          }
        ]
      },
      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_EVENING"
          }
        ]
      },
      "significant_absence": "No marked absence: the verse is pure action; the narrator withholds nothing here that the telling makes felt."
    },
    {
      "scene_id": "S2",
      "verse_range": "2:18",
      "scene_kind": "PROVISION_HOMECOMING_SCENE",
      "scene_communicative_purpose": "Brings the field's plenty home: the full gleaning seen, and Naomi fed from Ruth's own leftovers.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B9",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "PRESENT"
          },
          {
            "being_id": "B3",
            "role_in_scene": "MOTHER_IN_LAW",
            "presence": "PRESENT",
            "referential_form": "MOTHER_IN_LAW"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL4"
          },
          {
            "place_id": "PL_NAOMIS_DWELLING"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "O12"
          },
          {
            "object_id": "O10"
          }
        ]
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "The narrator records no word and no reaction from Naomi at the sight — her response is held back until the questions of the next verse."
    },
    {
      "scene_id": "S3",
      "verse_range": "2:19-22",
      "scene_kind": "REDEEMER_RECOGNITION_SCENE",
      "scene_communicative_purpose": "The turn of the passage: at the name \"Boaz,\" Naomi recognizes a redeemer, and the day's food becomes the first sign of rescue — sealed in a blessing that holds the living and the dead together under unbroken hesed.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B3",
            "role_in_scene": "MOTHER_IN_LAW",
            "presence": "PRESENT",
            "referential_form": "NAOMI"
          },
          {
            "being_id": "B9",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "PRESENT",
            "referential_form": "RUTH_THE_MOABITESS"
          },
          {
            "being_id": "B13",
            "role_in_scene": "REDEEMER_KIN",
            "presence": "REFERENCED",
            "referential_form": "THE_MAN"
          },
          {
            "being_id": "B10",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B18",
            "role_in_scene": "REDEEMER_KIN",
            "presence": "REFERENCED",
            "referential_form": "ONE_OF_OUR_REDEEMERS"
          },
          {
            "being_id": "B2",
            "role_in_scene": "DECEASED_KIN",
            "presence": "REFERENCED",
            "referential_form": "HAMETIM_THE_DEAD"
          },
          {
            "being_id": "B17",
            "role_in_scene": "MALE_WORKERS",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B16",
            "role_in_scene": "FEMALE_WORKERS",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B2",
            "role_in_scene": "HUSBAND",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B4",
            "role_in_scene": "SON",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B5",
            "role_in_scene": "SON",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL_NAOMIS_DWELLING"
          },
          {
            "place_id": "PL5_BOAZ_PORTION"
          },
          {
            "place_id": "PL_OTHER_FIELD"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0008"
          },
          {
            "object_id": "CB_0011"
          },
          {
            "object_id": "CB_0039"
          },
          {
            "object_id": "CB_0001"
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
      "significant_absence": "Naomi does not explain to Ruth what a redeemer is or what the nearness could mean for them; she names the role and stops, and the narrator does not say what Ruth understands by it. The dead are named only as \"the dead,\" not as Elimelech, Mahlon, and Chilion. The blessing never says whose hesed has not been forsaken — YHWH's or the man's; the words leave it open."
    },
    {
      "scene_id": "S4",
      "verse_range": "2:23",
      "scene_kind": "NARRATOR_FRAMING_CLOSE_SCENE",
      "scene_communicative_purpose": "Closes the pericope and the season in one quiet line: Ruth holding fast where it is safe, the household provided for, and the two women together — the still floor the next chapter's plan rises from.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B9",
            "role_in_scene": "GLEANER",
            "presence": "PRESENT"
          },
          {
            "being_id": "B16",
            "role_in_scene": "FEMALE_WORKERS",
            "presence": "PRESENT"
          },
          {
            "being_id": "B13",
            "role_in_scene": "FIELD_OWNER",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B3",
            "role_in_scene": "MOTHER_IN_LAW",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL5_BOAZ_PORTION"
          },
          {
            "place_id": "PL_NAOMIS_DWELLING"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0018"
          },
          {
            "object_id": "CB_0026"
          }
        ]
      },
      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_EXTENDED_HARVEST_SPAN"
          }
        ]
      },
      "significant_absence": "Through all the weeks of both harvests, the narrator records no further meeting and no further word between Ruth and Boaz. The season passes in silence."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "2:17a",
      "proposition_kind": "GLEANED",
      "event_specific_slots": {
        "gleaner": "B9",
        "gleaning_location": "PL5_BOAZ_PORTION",
        "gleaned_until": "TM_EVENING"
      },
      "inter_proposition_links": {
        "forward_link_to": "P2"
      },
      "cb_flags": [
        "CB_0034"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P2",
      "scene_link": "S1",
      "verse_anchor": "2:17b",
      "proposition_kind": "THRESHED",
      "event_specific_slots": {
        "thresher": "B9",
        "threshed_grain": "GLEANED_BARLEY",
        "threshing_method": "BY_HAND_CHAVAT"
      },
      "inter_proposition_links": {
        "caused_by": "P1",
        "forward_link_to": "P3"
      },
      "cb_flags": [
        "CB_0041"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P3",
      "scene_link": "S1",
      "verse_anchor": "2:17c",
      "proposition_kind": "MEASURED",
      "event_specific_slots": {
        "measured_yield": "O12",
        "yield_grain": "O2",
        "yield_amount": "ABOUT_AN_EPHAH",
        "yield_exactness": "APPROXIMATE"
      },
      "inter_proposition_links": {
        "caused_by": "P2",
        "forward_link_to": "P4"
      },
      "cb_flags": [
        "CB_0040"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P4",
      "scene_link": "S2",
      "verse_anchor": "2:18a",
      "proposition_kind": "ARRIVED_AT",
      "event_specific_slots": {
        "carrier": "B9",
        "home_bringing_components": [
          {
            "action": "TOOK",
            "lifted_load": "O12",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "ARRIVED_AT",
            "destination": "PL4",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "forward_link_to": "P5"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P5",
      "scene_link": "S2",
      "verse_anchor": "2:18b",
      "proposition_kind": "PERCEIVED",
      "event_specific_slots": {
        "perceiver": "B3",
        "perceived_gleaning": "O12"
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
      "verse_anchor": "2:18c",
      "proposition_kind": "GAVE",
      "event_specific_slots": {
        "giver": "B9",
        "given_to_mother_in_law": "B3",
        "gift_leftover": "O10",
        "gift_action_components": [
          {
            "action": "BROUGHT_OUT",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "GAVE",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "forward_link_to": "P7"
      },
      "cross_ref": "FIG_0104 cross-pericope pair closes here at 2:18 (opened at P06 P15, 2:14 — the third action, had leftover, lands as the leftover food Ruth gives Naomi); FIG_0113 single occurrence",
      "cb_flags": [],
      "figure_flags": [
        "FIG_0104",
        "FIG_0113"
      ]
    },
    {
      "prop_id": "P7",
      "scene_link": "S3",
      "verse_anchor": "2:19a",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "asker": "B3",
        "asked_party": "B9",
        "question_form": "DOUBLED_WHERE_AND_WHERE_WORKED",
        "speech_act": "ASKS_INFORMATION_SEEKING_QUESTION"
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
      "verse_anchor": "2:19b",
      "proposition_kind": "BLESSING",
      "event_specific_slots": {
        "blesser": "B3",
        "blessing_recipients": "B13",
        "blessed_party_form": "THE_MAN_WHO_TOOK_NOTICE",
        "speech_act": "WISHES_FOR_THIRD_PARTY"
      },
      "inter_proposition_links": {
        "forward_link_to": "P9"
      },
      "cb_flags": [
        "CB_0008"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P9",
      "scene_link": "S3",
      "verse_anchor": "2:19c",
      "proposition_kind": "IDENTIFIED",
      "event_specific_slots": {
        "reporter": "B9",
        "addressee": "B3",
        "identified_man": "B13",
        "given_name": "Boaz",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P7",
        "paired_with": "P7",
        "forward_link_to": "P10"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P10",
      "scene_link": "S3",
      "verse_anchor": "2:20a",
      "proposition_kind": "BLESSING",
      "event_specific_slots": {
        "blesser": "B3",
        "addressee": "B9",
        "blessing_recipients": "B13",
        "invoked_deity": "B10",
        "blessing_content_kind": "BLESSED_BY_YHWH",
        "speech_act": "WISHES_FOR_THIRD_PARTY"
      },
      "inter_proposition_links": {
        "caused_by": "P9",
        "paired_with": "P8",
        "forward_link_to": "P11"
      },
      "cb_flags": [
        "CB_0008"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P11",
      "scene_link": "S3",
      "verse_anchor": "2:20b",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "speaker": "B3",
        "hesed_holds": [
          "THE_LIVING",
          "THE_DEAD"
        ],
        "living_and_dead_form": "ET_HACHAYIM_VEET_HAMETIM",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P10",
        "forward_link_to": "P12"
      },
      "cross_ref": "FIG_0111 opens here; cross-pericope pair closes at P09 (3:10). FIG_0110 opens here; pairs forward to P11 (4:5) and P12 (4:10). The blessing keeps open whose hesed has not been forsaken — YHWH's or the man's",
      "cb_flags": [
        "CB_0011",
        "CB_0039"
      ],
      "figure_flags": [
        "FIG_0111",
        "FIG_0110"
      ]
    },
    {
      "prop_id": "P12",
      "scene_link": "S3",
      "verse_anchor": "2:20c",
      "proposition_kind": "IDENTIFIED",
      "event_specific_slots": {
        "speaker": "B3",
        "identified_man": "B13",
        "named_redeemer_role": "B18",
        "role_form": "ONE_OF_OUR_REDEEMERS",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P9",
        "forward_link_to": "P13"
      },
      "cross_ref": "FIG_0112 opens here; cross-pericope pair pairs forward to P09 (3:12) and P11 (4:1-6) — the nearness that carries the redeemer duty",
      "cb_flags": [
        "CB_0001"
      ],
      "figure_flags": [
        "FIG_0112"
      ]
    },
    {
      "prop_id": "P13",
      "scene_link": "S3",
      "verse_anchor": "2:21",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "reporter": "B9",
        "reporter_referential_form": "RUTH_THE_MOABITESS",
        "addressee": "B3",
        "reported_speaker": "B13",
        "reported_worker": "B17",
        "report_variation_form": "YOUNG_MEN_NOT_YOUNG_WOMEN",
        "speech_act": "REPORTS_PRIOR_SPEECH_INSTRUCTION"
      },
      "inter_proposition_links": {
        "forward_link_to": "P14"
      },
      "cross_ref": "FIG_0001 narrator epithet active here at 2:21; the book-wide arc opened at P01 (1:4), runs 1:22; 2:6; 2:21; 4:5; 4:10, and closes at P12 (4:10)",
      "cb_flags": [
        "CB_0004"
      ],
      "figure_flags": [
        "FIG_0001"
      ]
    },
    {
      "prop_id": "P14",
      "scene_link": "S3",
      "verse_anchor": "2:22",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "counselor": "B3",
        "counseled_party": "B9",
        "address_form": "MY_DAUGHTER",
        "worker_companions": "B16",
        "avoided_field": "PL_OTHER_FIELD",
        "speech_act": "DIRECTS_HEARER_TO_DO"
      },
      "inter_proposition_links": {
        "caused_by": "P13",
        "paired_with": "P13",
        "forward_link_to": "P15"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P15",
      "scene_link": "S4",
      "verse_anchor": "2:23a",
      "proposition_kind": "CLUNG_TO",
      "event_specific_slots": {
        "clinger": "B9",
        "clung_to": "B16",
        "clinging_purpose": "GLEAN",
        "clung_until": "TM_EXTENDED_HARVEST_SPAN",
        "harvest_span_seasons": [
          "BARLEY_HARVEST",
          "WHEAT_HARVEST"
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P14",
        "forward_link_to": "P16"
      },
      "cross_ref": "FIG_0012 cross-pericope pair closes here at 2:23 (opened at P02 P14, 1:14) — the same staying-close word as her first holding-fast to Naomi",
      "cb_flags": [
        "CB_0034",
        "CB_0018",
        "CB_0026"
      ],
      "figure_flags": [
        "FIG_0012"
      ]
    },
    {
      "prop_id": "P16",
      "scene_link": "S4",
      "verse_anchor": "2:23b",
      "proposition_kind": "DWELT_AT",
      "event_specific_slots": {
        "dweller": "B9",
        "dwelt_with_mother_in_law": "B3",
        "dwelling": "PL_NAOMIS_DWELLING"
      },
      "inter_proposition_links": {},
      "cb_flags": [],
      "figure_flags": []
    }
  ]
}
```

---
type: "sta-meaning-coordinates"
pericope: "P09"
pericope-title: "The threshing-floor night: the wing asked for, the word redeemer spoken, the oath"
source-meaning-map: [[P09-Ruth-3-6-13]]
status: "valid"
pilot: "pilot-2"
drafter: "claude-opus-4-8 · fm-drafter prompt (see _spec/pins.json) · machine-drafted, ruled by Marcia (SC-0064 batch ruling §A–§E + arc_element, 2026-06-19); MODEL_DRAFTED_REVIEWER_RULED"
---

# P09 — Ruth 3:6-13 — MEANING_COORDINATES

> Judgment gaps filled by the SC-0063 drafter (`tripod draft --live`); the merge layer enforced the patch-only contract. NOT canon until ruled.

```json
{
  "sta_id": "ruth_pericope_09_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Ruth 3:6-13",
    "pericope_title": "The threshing-floor night: the wing asked for, the word redeemer spoken, the oath",
    "book_context_ref": "ruth_pilot_BCD_v0_3",
    "source_meaning_map_ref": "P09-Ruth-3-6-13",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "Scenes 2-3 shift to CONSULTATIVE (a respectful exchange between the two, alone, at night). The blessing (3:10, FIG_0137) and the oath (3:13, FIG_0135) keep their exact formula wording and carry no register override of their own. Scene 1 is the narrator's plain INFORMAL_CASUAL telling.",
      "scene_level": [
        {
          "scene_id": "S2",
          "override_value": "CONSULTATIVE"
        },
        {
          "scene_id": "S3",
          "override_value": "CONSULTATIVE"
        }
      ],
      "moment_level": null
    }
  },
  "level_1": {
    "arc_elements": [
      "PLAN_EXECUTION",
      "RECOGNITION_EXCHANGE",
      "WING_PETITION",
      "BLESSING_INVOCATION",
      "NEARER_REDEEMER_DISCLOSURE",
      "OATH_SEALING"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "PHYSICAL_LOCATION",
      "KINSHIP_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "PRIOR_PERICOPE_CARRY_FORWARD",
      "DIVINE_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT"
    ],
    "tone_elements": [
      "QUIET",
      "ECONOMICAL",
      "ANTICIPATORY",
      "STILLED"
    ],
    "pace_elements": [
      "BRISK",
      "RISES",
      "SLOWED",
      "HOLDS",
      "SETTLES"
    ],
    "communicative_function_elements": [
      "ADVANCES",
      "CLOSES",
      "REACTIVATES",
      "OPENS",
      "STAGES"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "3:6-7",
      "scene_kind": "NIGHT_APPROACH_SCENE",
      "scene_communicative_purpose": "Executes the plan to the letter and sets the night's stage: the man lying down at the end of the grain heap, the woman at his feet, and nothing yet said.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B9",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "PRESENT"
          },
          {
            "being_id": "B13",
            "role_in_scene": "REDEEMER_KIN",
            "presence": "PRESENT"
          },
          {
            "being_id": "B3",
            "role_in_scene": "PLANNER",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL6"
          },
          {
            "place_id": "PL_END_OF_GRAIN_HEAP"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0042"
          }
        ]
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "The narrator does not say what Ruth intends beyond the plan. No word is spoken in the whole scene."
    },
    {
      "scene_id": "S2",
      "verse_range": "3:8-9",
      "scene_kind": "APPEAL_SCENE",
      "scene_communicative_purpose": "The turn of the night: the plan's script runs out and Ruth speaks past it — name, petition, and the redeemer-claim, in one breath in the dark.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B13",
            "role_in_scene": "REDEEMER_KIN",
            "presence": "PRESENT",
            "referential_form": "HA_ISH_THE_MAN"
          },
          {
            "being_id": "B9",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "PRESENT",
            "referential_form": "RUTH_YOUR_SERVANT_AMAH"
          },
          {
            "being_id": "B18",
            "role_in_scene": "REDEEMER_KIN",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B2",
            "role_in_scene": "ANCESTOR",
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
            "place_id": "PL6"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0037"
          },
          {
            "object_id": "CB_0001"
          }
        ]
      },
      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_MIDDLE_OF_THE_NIGHT"
          }
        ]
      },
      "significant_absence": "Ruth does not wait for the man to tell her what to do, though Naomi's plan said he would (3:4); in the night it is Ruth who makes the request, and the narrator does not comment on the change. What the uncovering and the lying down mean is never said. No word of love or desire is spoken by either of them."
    },
    {
      "scene_id": "S3",
      "verse_range": "3:10-13",
      "scene_kind": "BLESSING_SCENE",
      "scene_communicative_purpose": "Answers the night's petition with everything at once — blessing, honor, pledge, and law: Ruth is praised and promised, the nearer redeemer is disclosed, and the whole matter is bound under oath and handed to the morning.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B13",
            "role_in_scene": "REDEEMER_KIN",
            "presence": "PRESENT"
          },
          {
            "being_id": "B9",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "PRESENT",
            "referential_form": "MY_DAUGHTER"
          },
          {
            "being_id": "B10",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B19",
            "role_in_scene": "REDEEMER_KIN",
            "presence": "REFERENCED",
            "referential_form": "NEARER_REDEEMER_UNNAMED"
          },
          {
            "being_id": "B21",
            "role_in_scene": "TOWNSPEOPLE",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B32",
            "role_in_scene": "NOT_GONE_AFTER",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B2",
            "role_in_scene": "ANCESTOR",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL6"
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
            "object_id": "CB_0032"
          },
          {
            "object_id": "CB_0001"
          }
        ]
      },
      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_NIGHT_UNTIL_MORNING"
          }
        ]
      },
      "significant_absence": "Boaz answers yes to the request (\"all that you say I will do\") but binds the promise to the order of redeemers: if the nearer one redeems, good; if he is not willing, Boaz himself will redeem, under oath by YHWH. The text does not say which of the two will act, nor what Boaz feels or wants. The nearer redeemer is not named. The narrator reports no touch beyond the uncovering and no word of love or desire; the night passes in words. The text gives no verdict on the night — neither that something happened nor that nothing did."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "3:6",
      "proposition_kind": "WENT_DOWN",
      "event_specific_slots": {
        "descender": "B9",
        "destination": "PL6",
        "compliance_form": "ALL_AS_COMMANDED",
        "commanding_party": "B3"
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
      "verse_anchor": "3:7a",
      "proposition_kind": "ATE",
      "event_specific_slots": {
        "diner": "B13",
        "ate": true,
        "drank": true,
        "resulting_disposition": "HEART_WAS_GOOD"
      },
      "inter_proposition_links": {
        "forward_link_to": "P3"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0141"
      ]
    },
    {
      "prop_id": "P3",
      "scene_link": "S1",
      "verse_anchor": "3:7b",
      "proposition_kind": "LAY_DOWN",
      "event_specific_slots": {
        "one_lying_down": "B13",
        "location": "PL_END_OF_GRAIN_HEAP"
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
      "verse_anchor": "3:7c",
      "proposition_kind": "APPROACHED",
      "event_specific_slots": {
        "approach_components": [
          {
            "action": "WALKED",
            "approacher": "B9",
            "manner": "SOFTLY",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "UNCOVERED_FEET",
            "uncoverer": "B9",
            "uncovered_place": "CB_0042",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "LAY_DOWN",
            "one_lying_down": "B9",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "forward_link_to": "P5"
      },
      "cb_flags": [
        "CB_0042"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P5",
      "scene_link": "S2",
      "verse_anchor": "3:8a",
      "proposition_kind": "TREMBLED",
      "event_specific_slots": {
        "one_who_trembled": "B13",
        "time_of_startle": "TM_MIDDLE_OF_THE_NIGHT",
        "follow_motion": "TWISTED_AROUND",
        "referential_form_at_verse": "HA_ISH_THE_MAN"
      },
      "inter_proposition_links": {
        "caused_by": "P4",
        "forward_link_to": "P6"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0130"
      ]
    },
    {
      "prop_id": "P6",
      "scene_link": "S2",
      "verse_anchor": "3:8b",
      "proposition_kind": "PERCEIVED",
      "event_specific_slots": {
        "perceiver": "B13",
        "perceived_being": "B9",
        "perceived_as": "A_WOMAN",
        "location": "CB_0042"
      },
      "inter_proposition_links": {
        "caused_by": "P5",
        "forward_link_to": "P7"
      },
      "cb_flags": [
        "CB_0042"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P7",
      "scene_link": "S2",
      "verse_anchor": "3:9a",
      "proposition_kind": "ASKED",
      "event_specific_slots": {
        "asker": "B13",
        "addressee": "B9",
        "referential_form_at_verse": "HA_ISH_THE_MAN",
        "speech_act": "ASKS_INFORMATION_SEEKING_QUESTION"
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
      "verse_anchor": "3:9b",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "speaker": "B9",
        "addressee": "B13",
        "self_referential_form": "RUTH_YOUR_SERVANT_AMAH",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P7",
        "paired_with": "P7",
        "forward_link_to": "P9"
      },
      "cross_ref": "FIG_0132 closes here with amah; opened at P06 (2:13) with shifchah; the change of word is kept, its meaning is not stated",
      "cb_flags": [],
      "figure_flags": [
        "FIG_0132"
      ]
    },
    {
      "prop_id": "P9",
      "scene_link": "S2",
      "verse_anchor": "3:9c",
      "proposition_kind": "APPEAL",
      "event_specific_slots": {
        "petitioner": "B9",
        "petitioned": "B13",
        "invoked_image": "CB_0037",
        "self_referential_form": "AMAH_SERVANT",
        "speech_act": "DIRECTS_HEARER_TO_DO"
      },
      "inter_proposition_links": {
        "forward_link_to": "P10"
      },
      "cross_ref": "FIG_0131 closes the FIG_0011 wing pair here; opened at P06 (2:12); Ruth uses the same word (kanaph) Boaz used at 2:12 for the wings of YHWH",
      "cb_flags": [
        "CB_0037"
      ],
      "figure_flags": [
        "FIG_0131"
      ]
    },
    {
      "prop_id": "P10",
      "scene_link": "S2",
      "verse_anchor": "3:9d",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "declarer": "B9",
        "addressee": "B13",
        "redeemer_role": "B18",
        "redeemer_concept": "CB_0001",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "paired_with": "P9",
        "forward_link_to": "P11"
      },
      "cb_flags": [
        "CB_0001"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P11",
      "scene_link": "S3",
      "verse_anchor": "3:10a",
      "proposition_kind": "BLESSING",
      "event_specific_slots": {
        "blessing_speaker": "B13",
        "blessing_recipients": "B9",
        "invoked_deity": "B10",
        "address_form": "MY_DAUGHTER",
        "blessing_content_kind": "BLESSED_OF_YHWH",
        "speech_act": "WISHES_FOR_HEARER"
      },
      "inter_proposition_links": {
        "caused_by": "P9",
        "forward_link_to": "P12"
      },
      "cb_flags": [
        "CB_0008"
      ],
      "figure_flags": [
        "FIG_0137"
      ]
    },
    {
      "prop_id": "P12",
      "scene_link": "S3",
      "verse_anchor": "3:10b",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "declarer": "B13",
        "praised_party": "B9",
        "hesed_concept": "CB_0011",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P13"
      },
      "cross_ref": "FIG_0111 closes here; opened at P07 (2:20). CB_0011 third station (1:8, 2:20, 3:10); whose hesed was not forsaken at 2:20 — YHWH's or the man's — stays open",
      "cb_flags": [
        "CB_0011"
      ],
      "figure_flags": [
        "FIG_0133",
        "FIG_0111"
      ]
    },
    {
      "prop_id": "P13",
      "scene_link": "S3",
      "verse_anchor": "3:10c",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "declarer": "B13",
        "about_party": "B9",
        "young_men": "B32",
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
      "scene_link": "S3",
      "verse_anchor": "3:11a",
      "proposition_kind": "REASSURED",
      "event_specific_slots": {
        "speaker": "B13",
        "addressee": "B9",
        "address_form": "MY_DAUGHTER",
        "reassurance_components": [
          {
            "speech_act": "DIRECTS_HEARER_NOT_TO_DO"
          },
          {
            "speech_act": "VOWS"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P9",
        "forward_link_to": "P15"
      },
      "cross_ref": "FIG_0123 closes here in Boaz's mouth (FIG_0136); opened at P08 (3:5) in Ruth's mouth",
      "cb_flags": [],
      "figure_flags": [
        "FIG_0123",
        "FIG_0136"
      ]
    },
    {
      "prop_id": "P15",
      "scene_link": "S3",
      "verse_anchor": "3:11b",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "declarer": "B13",
        "knowing_public": "B21",
        "worth_concept": "CB_0032",
        "about_party": "B9",
        "referential_form_at_verse": "ESHET_CHAYIL_WOMAN_OF_WORTH",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P14",
        "forward_link_to": "P16"
      },
      "cross_ref": "FIG_0134 closes here with eshet chayil; opened at P05 (2:1) with Boaz as ish gibbor chayil (FIG_0090, CB_0032)",
      "cb_flags": [
        "CB_0032"
      ],
      "figure_flags": [
        "FIG_0134"
      ]
    },
    {
      "prop_id": "P16",
      "scene_link": "S3",
      "verse_anchor": "3:12a",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "declarer": "B13",
        "redeemer_concept": "CB_0001",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P17"
      },
      "cb_flags": [
        "CB_0001"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P17",
      "scene_link": "S3",
      "verse_anchor": "3:12b",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "declarer": "B13",
        "disclosed_party": "B19",
        "redeemer_concept": "CB_0001",
        "referential_form": "NEARER_REDEEMER_UNNAMED",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P16",
        "forward_link_to": "P18"
      },
      "cross_ref": "FIG_0112 returns here: a redeemer nearer than I, who comes first because he is nearer; opened at P07 (2:20)",
      "cb_flags": [
        "CB_0001"
      ],
      "figure_flags": [
        "FIG_0138",
        "FIG_0112"
      ]
    },
    {
      "prop_id": "P18",
      "scene_link": "S3",
      "verse_anchor": "3:13a",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "instructor": "B13",
        "instructed": "B9",
        "action": "DIRECTED",
        "speech_act": "DIRECTS_HEARER_TO_DO"
      },
      "inter_proposition_links": {
        "caused_by": "P17",
        "forward_link_to": "P19"
      },
      "cross_ref": "FIG_0140 closes the FIG_0122 pair here; opened at P08 (3:4): Naomi's plan said he would tell Ruth what to do; in the night Ruth makes the request (3:9), and Boaz sends the next step to the morning",
      "cb_flags": [],
      "figure_flags": [
        "FIG_0140"
      ]
    },
    {
      "prop_id": "P19",
      "scene_link": "S3",
      "verse_anchor": "3:13b",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "speaker": "B13",
        "protocol_components": [
          {
            "condition": "IF_HE_REDEEMS",
            "redeemer": "B19",
            "response": "GOOD",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "condition": "IF_NOT_WILLING",
            "self_redeemer": "B13",
            "speech_act": "VOWS"
          }
        ],
        "redeemer_concept": "CB_0001"
      },
      "inter_proposition_links": {
        "caused_by": "P17",
        "forward_link_to": "P20"
      },
      "cross_ref": "FIG_0140 continues from P18: the next step sent to the morning",
      "cb_flags": [
        "CB_0001"
      ],
      "figure_flags": [
        "FIG_0140"
      ]
    },
    {
      "prop_id": "P20",
      "scene_link": "S3",
      "verse_anchor": "3:13c",
      "proposition_kind": "VOW",
      "event_specific_slots": {
        "swearer": "B13",
        "invoked_divine_witness": "B10",
        "speech_act": "INVOKES_DIVINE_AS_OATH_GUARANTOR"
      },
      "inter_proposition_links": {
        "caused_by": "P19",
        "forward_link_to": "P21"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0135"
      ]
    },
    {
      "prop_id": "P21",
      "scene_link": "S3",
      "verse_anchor": "3:13d",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "instructor": "B13",
        "instructed": "B9",
        "action": "DIRECTED",
        "speech_act": "DIRECTS_HEARER_TO_DO"
      },
      "inter_proposition_links": {
        "caused_by": "P20"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0139"
      ]
    }
  ]
}
```

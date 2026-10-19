---
type: "sta-meaning-coordinates"
pericope: "E10"
pericope-title: "The scepter, the two banquets, and the gallows raised for Mordecai"
source-meaning-map: [[E10-Esther-5-1-14]]
status: "valid"
pilot: "pilot-2"
---

# E10 — Esther 5:1–14 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "esther_pericope_10_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",

  "header": {
    "bcv": "Esther 5:1-14",
    "pericope_title": "The scepter, the two banquets, and the gallows raised for Mordecai",
    "book_context_ref": "esther_pilot_BCD_v0_1",
    "source_meaning_map_ref": "E10-Esther-5-1-14",
    "source_language": "Biblical Hebrew"
  },

  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "No override. The whole pericope is INFORMAL_CASUAL — plain storyteller's voice. No edict is voiced or written in 5:1-14; the king's 'even to half the kingdom' is courtly hyperbole in conversation, not a published decree, so FORMAL_OFFICIAL does not apply.",
      "scene_level": null,
      "moment_level": null
    }
  },

  "level_1": {
    "arc_elements": [
      "RESOLVE_TO_ACT",
      "FAVOR_GRANTED",
      "INVITATION_DOUBLED",
      "REQUEST_WITHHELD",
      "PRIDE_AT_SUMMIT",
      "OFFENSE_AT_THE_GATE",
      "COUNSEL_OF_DESTRUCTION",
      "TRAP_SET"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "PHYSICAL_LOCATION",
      "INSTITUTIONAL_CONTEXT",
      "KINSHIP_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT",
      "TEMPORAL_CONTEXT"
    ],
    "tone_elements": [
      "TAUT",
      "ANTICIPATORY",
      "CEREMONIAL",
      "RISING",
      "IRONIC",
      "GRIM"
    ],
    "pace_elements": [
      "HOLDS",
      "PAUSED",
      "ACCELERATES"
    ],
    "communicative_function_elements": [
      "ADVANCES",
      "SETS_TRAP",
      "ELEVATES",
      "REVERSES",
      "PLANTS"
    ]
  },

  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "5:1-3",
      "scene_kind": "AUDIENCE_SCENE",
      "scene_communicative_purpose": "Shows the queen surviving the unsummoned approach by the king's mercy, and the king opening the door wide with his offer — the moment that lets everything follow.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B2",
            "role_in_scene": "QUEEN",
            "presence": "PRESENT",
            "referential_form": "ESTHER_THE_QUEEN"
          },
          {
            "being_id": "B4",
            "role_in_scene": "KING",
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
            "object_id": "TH_SCEPTER"
          },
          {
            "object_id": "TH_THRONE"
          }
        ]
      },

      "times_in_scene": {
        "_note": "Scene-content time is a relative day-reference ('the third day'), not a registered TM_ code; carried as a bare atom in proposition slots.",
        "entries": null
      },

      "significant_absence": "God is named nowhere in the most dangerous moment of the book — the woman steps into a death-space and lives, and the narrator credits no prayer, no providence, no Name; only \"she found favor in his eyes.\" The three-day fast that frames this day is mentioned in the previous pericope without any object of the fasting being named. The deliverance is real and unattributed — the book's signature silence at its sharpest."
    },

    {
      "scene_id": "S2",
      "verse_range": "5:4-8",
      "scene_kind": "MEAL_SCENE",
      "scene_communicative_purpose": "Shows the queen springing her trap by invitation, twice declining to state her request and binding both the king and Haman to a second banquet — drawing Haman in unknowing.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B2",
            "role_in_scene": "QUEEN",
            "presence": "PRESENT",
            "referential_form": "ESTHER_THE_QUEEN"
          },
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT"
          },
          {
            "being_id": "B3",
            "role_in_scene": "UNWITTING_GUEST",
            "presence": "PRESENT"
          }
        ]
      },

      "places_in_scene": {
        "_note": "The banquet (the mishteh, institution-meaning carried as the bare atom MISHTEH in the proposition slots) is a feast-setting within the palace at PL1, not a separate place code.",
        "entries": [
          {
            "place_id": "PL1"
          }
        ]
      },

      "objects_in_scene": {
        "_note": "No registry object persists in this scene. The banquet is an institution (not an object_id; carried as the bare atom MISHTEH in the proposition slots), and the 'banquet of wine' is its wine-course — descriptive scene-content, not an object code.",
        "entries": null
      },

      "times_in_scene": {
        "_note": "Scene-content time is the relative 'today / tomorrow' day-references of the doubled invitation, not registered TM_ codes; carried as bare atoms in proposition slots.",
        "entries": null
      },

      "significant_absence": "Esther never says what she actually wants — twice asked, twice she withholds it. The narrator gives no reason for the delay, no glimpse of her plan, and no Name behind her patience. The reader is left to feel a deliberate strategy with no stated source — the silence of a withheld purpose."
    },

    {
      "scene_id": "S3",
      "verse_range": "5:9",
      "scene_kind": "GATE_CONFRONTATION_SCENE",
      "scene_communicative_purpose": "Shows Haman at his peak undone in an instant by one man's refusal to honor him — the spark that drives the plot to the gallows.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B3",
            "role_in_scene": "ADVERSARY",
            "presence": "PRESENT"
          },
          {
            "being_id": "B1",
            "role_in_scene": "REFUSER",
            "presence": "PRESENT"
          }
        ]
      },

      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL8"
          }
        ]
      },

      "objects_in_scene": {
        "_note": "No persistent objects in this scene; it turns on a man's bearing, not on any object — the absence of an act (Mordecai's not rising) is its whole substance.",
        "entries": null
      },

      "times_in_scene": {
        "_note": "Scene-content time is the relative 'that day' day-reference, not a registered TM_ code; carried as a bare atom in proposition slots.",
        "entries": null
      },

      "significant_absence": "Mordecai says nothing and does nothing — his power here is pure refusal, an absence of the homage everyone else gives. The narrator offers no word from Mordecai, no explanation, and no Name to ground his defiance; the reader knows only that he will not bow. The whole reversal hinges on a man who stays silent and still."
    },

    {
      "scene_id": "S4",
      "verse_range": "5:10-14",
      "scene_kind": "CRISIS_DELIBERATION_SCENE",
      "scene_communicative_purpose": "Shows Haman's pride at full height and the counsel that will destroy him — and raises, in his own hand, the gallows the book will turn back on him.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B3",
            "role_in_scene": "ADVERSARY",
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
            "being_id": "B1",
            "role_in_scene": "POISONING_PRESENCE_AND_INTENDED_VICTIM",
            "presence": "REFERENCED",
            "referential_form": "MORDECAI_THE_JEW"
          },
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "REFERENCED"
          }
        ]
      },

      "places_in_scene": {
        "_note": "Haman's house is the private setting of the boast and counsel — a scene venue within the palace city PL1, not a separate place code. The king's gate (PL8) is referenced, not entered: Mordecai sitting there is recalled in Haman's complaint.",
        "entries": [
          {
            "place_id": "PL1"
          },
          {
            "place_id": "PL8"
          }
        ]
      },

      "objects_in_scene": {
        "_note": "Haman's glory (riches, sons, promotions) is the substance of his boast — descriptive scene-content carried as bare atoms in the proposition slots, not a registry object. The second banquet is an institution (carried as the bare atom MISHTEH in the proposition slots), not an object code.",
        "entries": [
          {
            "object_id": "TH_GALLOWS"
          }
        ]
      },

      "times_in_scene": {
        "_note": "Scene-content time is the relative 'in the morning' day-reference, not a registered TM_ code; carried as a bare atom in proposition slots.",
        "entries": null
      },

      "significant_absence": "No one in the room foresees the irony the reader sees plainly — that the gallows is Haman's own. The counsel is given with full confidence and no hint of warning; God is not named, no omen is read, no caution is spoken. The silence here is dramatic: the audience knows what the speakers cannot, and the narrator lets the gallows go up without a word of the doom it carries."
    }
  ],

  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "5:1",
      "proposition_kind": "TOOK",
      "event_specific_slots": {
        "clother": "B2",
        "donned": "ROYALTY",
        "when": "THIRD_DAY"
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
      "verse_anchor": "5:1",
      "proposition_kind": "APPROACHED",
      "event_specific_slots": {
        "stander": "B2",
        "standing_place": "INNER_COURT",
        "court_of": "KINGS_HOUSE",
        "facing": "THRONE_ROOM"
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
      "verse_anchor": "5:1",
      "proposition_kind": "SAT",
      "event_specific_slots": {
        "sitter": "B4",
        "seat": "TH_THRONE",
        "seat_of": "THE_KINGDOM",
        "where": "ROYAL_HOUSE",
        "facing": "THE_OPENING"
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
      "verse_anchor": "5:2",
      "proposition_kind": "PERCEIVED",
      "event_specific_slots": {
        "seer": "B4",
        "seen_party": "B2",
        "seen_as": "QUEEN",
        "seen_doing": "STANDING",
        "where": "THE_COURT"
      },
      "inter_proposition_links": {
        "caused_by": "P2",
        "forward_link_to": "P5"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P5",
      "scene_link": "S1",
      "verse_anchor": "5:2",
      "proposition_kind": "PERCEIVED",
      "event_specific_slots": {
        "favor_bearer": "B2",
        "favor_in_eyes_of": "B4",
        "named_doer": "NONE"
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
      "scene_link": "S1",
      "verse_anchor": "5:2",
      "proposition_kind": "GRANTED",
      "event_specific_slots": {
        "extender": "B4",
        "extended": "TH_SCEPTER",
        "scepter_kind": "GOLDEN",
        "extended_to": "B2",
        "held_in": "HIS_HAND"
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
      "scene_link": "S1",
      "verse_anchor": "5:2",
      "proposition_kind": "APPROACHED",
      "event_specific_slots": {
        "approacher": "B2"
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
      "scene_link": "S1",
      "verse_anchor": "5:2",
      "proposition_kind": "TOUCHED",
      "event_specific_slots": {
        "toucher": "B2",
        "touched": "A_TIP",
        "tip_of": "TH_SCEPTER"
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
      "scene_link": "S1",
      "verse_anchor": "5:3",
      "proposition_kind": "PROPOSED",
      "event_specific_slots": {
        "solicit_components": [
          {
            "action": "ASKED",
            "speaker": "B4",
            "addressee": "B2",
            "asked": "WHAT_IS_IT",
            "speech_act": "ASKS_INFORMATION_SEEKING_QUESTION"
          },
          {
            "action": "PROPOSED",
            "speaker": "B4",
            "addressee": "B2",
            "offered_extent": "HALF_THE_KINGDOM",
            "to_be_given_to": "B2",
            "status": "FORESEEN",
            "speech_act": "PROPOSES_COURSE_OF_ACTION"
          }
        ]
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
      "scene_link": "S2",
      "verse_anchor": "5:4",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B2",
        "addressee": "B4",
        "condition": "IF_GOOD",
        "condition_party": "B4",
        "speech_act": "PROPOSES_COURSE_OF_ACTION"
      },
      "inter_proposition_links": {
        "forward_link_to": "P11",
        "condition_of": "P11"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P11",
      "scene_link": "S2",
      "verse_anchor": "5:4",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "inviter": "B2",
        "invited": ["B4", "B3"],
        "when": "TODAY",
        "banquet_named": "MISHTEH",
        "speech_act": "PROPOSES_COURSE_OF_ACTION"
      },
      "inter_proposition_links": {
        "caused_by": "P10",
        "content_of": "P10",
        "forward_link_to": "P12"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P12",
      "scene_link": "S2",
      "verse_anchor": "5:5",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B4",
        "hastened_party": "B3",
        "to_do": "ESTHERS_WORD",
        "speech_act": "DIRECTS_HEARER_TO_DO"
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
      "verse_anchor": "5:5",
      "proposition_kind": "ARRIVED_AT",
      "event_specific_slots": {
        "comers": ["B4", "B3"],
        "to_event": "MISHTEH",
        "event_of": "B2"
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
      "verse_anchor": "5:6",
      "proposition_kind": "PROPOSED",
      "event_specific_slots": {
        "solicit_components": [
          {
            "action": "ASKED",
            "speaker": "B4",
            "addressee": "B2",
            "asked": "PETITION",
            "at_event": "MISHTEH",
            "event_course": "OF_WINE",
            "speech_act": "ASKS_INFORMATION_SEEKING_QUESTION"
          },
          {
            "action": "PROPOSED",
            "speaker": "B4",
            "addressee": "B2",
            "offered_extent": "HALF_THE_KINGDOM",
            "to_be_done_for": "B2",
            "status": "FORESEEN",
            "speech_act": "PROPOSES_COURSE_OF_ACTION"
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
      "scene_link": "S2",
      "verse_anchor": "5:7",
      "proposition_kind": "ANSWERED",
      "event_specific_slots": {
        "answerer": "B2",
        "addressee": "B4",
        "named": ["PETITION", "REQUEST"],
        "speech_act": "PETITIONS_FOR_GRANT"
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
      "verse_anchor": "5:8",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B2",
        "addressee": "B4",
        "condition_components": [
          {
            "condition": "FAVOR_FOUND",
            "favor_bearer": "B2",
            "favor_in_eyes_of": "B4"
          },
          {
            "condition": "IF_GOOD",
            "condition_party": "B4",
            "to_grant": "PETITION",
            "to_do": "REQUEST"
          }
        ],
        "speech_act": "PETITIONS_FOR_GRANT"
      },
      "inter_proposition_links": {
        "content_of": "P15",
        "condition_of": "P17",
        "forward_link_to": "P17"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P17",
      "scene_link": "S2",
      "verse_anchor": "5:8",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "inviter": "B2",
        "invited": ["B4", "B3"],
        "to_event": "MISHTEH",
        "when": "TOMORROW",
        "deferred_ask": "WITHHELD",
        "speech_act": "PROPOSES_COURSE_OF_ACTION"
      },
      "inter_proposition_links": {
        "caused_by": "P16",
        "content_of": "P15"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P18",
      "scene_link": "S3",
      "verse_anchor": "5:9",
      "proposition_kind": "WENT_OUT",
      "event_specific_slots": {
        "goer": "B3",
        "when": "THAT_DAY",
        "in_state": ["GLAD", "GOOD_OF_HEART"]
      },
      "inter_proposition_links": {
        "forward_link_to": "P19"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P19",
      "scene_link": "S3",
      "verse_anchor": "5:9",
      "proposition_kind": "PERCEIVED",
      "event_specific_slots": {
        "seer": "B3",
        "seen_party": "B1",
        "where": "PL8",
        "gate_of": "B4"
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
      "scene_link": "S3",
      "verse_anchor": "5:9",
      "proposition_kind": "DECLINED",
      "event_specific_slots": {
        "withholder": "B1",
        "withheld": ["RISING", "TREMBLING"],
        "before_whom": "B3"
      },
      "inter_proposition_links": {
        "caused_by": "P19",
        "forward_link_to": "P21"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P21",
      "scene_link": "S3",
      "verse_anchor": "5:9",
      "proposition_kind": "ANGER_KINDLED",
      "event_specific_slots": {
        "filled_party": "B3",
        "filled_with": "FURY",
        "against_whom": "B1"
      },
      "inter_proposition_links": {
        "caused_by": "P20",
        "forward_link_to": "P22"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P22",
      "scene_link": "S4",
      "verse_anchor": "5:10",
      "proposition_kind": "AFFIRMED_RESOLVE",
      "event_specific_slots": {
        "restrainer": "B3"
      },
      "inter_proposition_links": {
        "caused_by": "P21",
        "forward_link_to": "P23"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P23",
      "scene_link": "S4",
      "verse_anchor": "5:10",
      "proposition_kind": "ARRIVED_AT",
      "event_specific_slots": {
        "comer": "B3",
        "to_place": "HIS_HOUSE"
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
      "scene_link": "S4",
      "verse_anchor": "5:10",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "sender": "B3",
        "summoned": ["B23", "B6"],
        "summoned_role": "WIFE_AND_FRIENDS"
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
      "scene_link": "S4",
      "verse_anchor": "5:11",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "recounter": "B3",
        "addressees": ["B23", "B6"],
        "recounted": ["RICHES_GLORY", "MANY_SONS", "PROMOTION_BY_KING", "RAISED_ABOVE_OFFICIALS"],
        "promoter": "B4",
        "speech_act": "STATES_AS_TRUE"
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
      "scene_link": "S4",
      "verse_anchor": "5:12",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "boaster": "B3",
        "boasted": "UNIQUE_INVITATION",
        "inviter": "B2",
        "brought_no_one_but": "B3",
        "alongside": "B4",
        "to_event": "MISHTEH",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P25",
        "forward_link_to": "P27"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P27",
      "scene_link": "S4",
      "verse_anchor": "5:12",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "boaster": "B3",
        "boasted": "RENEWED_INVITATION",
        "invited_party": "B3",
        "when": "TOMORROW",
        "inviter": "B2",
        "alongside": "B4",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P26",
        "content_of": "P26",
        "forward_link_to": "P28"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P28",
      "scene_link": "S4",
      "verse_anchor": "5:13",
      "proposition_kind": "LAMENTED_AGAINST",
      "event_specific_slots": {
        "lamenter": "B3",
        "declared": "WORTHLESSNESS_TO_ME",
        "worthless_thing": "ALL_HIS_GLORY",
        "when": "EVERY_TIME",
        "trigger": "SEEING",
        "seen_party": "B1",
        "seen_referential_form": "MORDECAI_THE_JEW",
        "seen_doing": "SITTING",
        "where": "PL8",
        "speech_act": "ALLEGES_AGAINST"
      },
      "inter_proposition_links": {
        "caused_by": "P27",
        "content_of": "P26",
        "forward_link_to": "P29"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P29",
      "scene_link": "S4",
      "verse_anchor": "5:14",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "counselors": ["B6", "B23"],
        "counselor_role": "WIFE_AND_FRIENDS",
        "addressee": "B3",
        "speech_act": "ADVISES_COURSE_OF_ACTION"
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
      "verse_anchor": "5:14",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "made_thing": "TH_GALLOWS",
        "height": "FIFTY",
        "height_unit": "CUBITS",
        "status": "FORESEEN"
      },
      "inter_proposition_links": {
        "caused_by": "P29",
        "content_of": "P29",
        "purpose_of": "P31",
        "forward_link_to": "P31"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P31",
      "scene_link": "S4",
      "verse_anchor": "5:14",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "teller": "B3",
        "told_party": "B4",
        "when": "IN_THE_MORNING",
        "to_do": "HANGING",
        "hanged_party": "B1",
        "on_what": "TH_GALLOWS",
        "status": "FORESEEN"
      },
      "inter_proposition_links": {
        "caused_by": "P30",
        "content_of": "P29",
        "forward_link_to": "P32"
      },
      "cross_ref": "the gallows raised here is the one Haman is hanged on; closes at E12",
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P32",
      "scene_link": "S4",
      "verse_anchor": "5:14",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "goer": "B3",
        "alongside": "B4",
        "to_event": "MISHTEH",
        "in_state": "GLAD",
        "status": "FORESEEN"
      },
      "inter_proposition_links": {
        "caused_by": "P31",
        "content_of": "P29",
        "forward_link_to": "P33"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P33",
      "scene_link": "S4",
      "verse_anchor": "5:14",
      "proposition_kind": "GRANTED",
      "event_specific_slots": {
        "pleasing_thing": "THE_COUNSEL",
        "pleased_in_eyes_of": "B3"
      },
      "inter_proposition_links": {
        "caused_by": "P29",
        "forward_link_to": "P34"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P34",
      "scene_link": "S4",
      "verse_anchor": "5:14",
      "proposition_kind": "MADE",
      "event_specific_slots": {
        "maker": "B3",
        "made_thing": "TH_GALLOWS"
      },
      "inter_proposition_links": {
        "caused_by": "P33",
        "purpose_of": "P31"
      },
      "cross_ref": "the gallows Haman makes here is the one he is hanged on; closes at E12",
      "cb_flags": [],
      "figure_flags": []
    }
  ]
}
```

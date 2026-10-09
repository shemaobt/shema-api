---
type: "sta-meaning-coordinates"
pericope: "P05"
pericope-title: "Boaz introduced as kinsman; Ruth's gleaning initiative; her chance arrival in Boaz's portion; the foreman's report"
source-meaning-map: [[P05-Ruth-2-1-7]]
status: "valid"
pilot: "pilot-2"
---

# P05 — Ruth 2:1–7 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "ruth_pericope_05_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Ruth 2:1-7",
    "pericope_title": "Boaz introduced as kinsman; Ruth's gleaning initiative; her chance arrival in Boaz's portion; the foreman's report",
    "book_context_ref": "ruth_pilot_BCD_v0_3",
    "source_meaning_map_ref": "P05-Ruth-2-1-7",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "One scene-level INTIMATE override on S2 (Ruth-Naomi interior dialogue inside their dwelling — relational-close register fits the moment better than INFORMAL_CASUAL even though the speech is a request-and-release exchange; mirroring P02 S2/S3, P03 S1-S2, P04 S2 pattern). S1, S3, S4 stay at INFORMAL_CASUAL narrator default. No moment-level overrides.",
      "scene_level": [
        {
          "scene_id": "S2",
          "override_value": "INTIMATE",
          "genre_override": null,
          "genre_group_override": null
        }
      ],
      "moment_level": null
    }
  },
  "level_1": {
    "arc_elements": [
      "NARRATOR_PARENTHETICAL_INTRODUCTION",
      "INITIATIVE_OF_OUTSIDER_DAUGHTER_IN_LAW",
      "CHANCE_PROVIDENCE_ARRIVAL",
      "FIELD_COMMUNITY_GREETING",
      "PUBLIC_IDENTIFICATION_OF_OUTSIDER"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "PHYSICAL_LOCATION",
      "KINSHIP_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "TEMPORAL_CONTEXT",
      "DIVINE_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT",
      "PRIOR_ACTION_CONTEXT"
    ],
    "tone_elements": [
      "QUIET",
      "ECONOMICAL",
      "ANTICIPATORY",
      "RESTRAINED",
      "CHRONICLE"
    ],
    "pace_elements": [
      "NARROWS",
      "HOLDS",
      "WIDENS",
      "SETTLES"
    ],
    "communicative_function_elements": [
      "OPENS",
      "INTRODUCES",
      "ANCHORS",
      "POSITIONS",
      "REACTIVATES",
      "STAGES",
      "WITHHOLDS"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "2:1",
      "scene_kind": "NARRATOR_INTRODUCTION_SCENE",
      "scene_communicative_purpose": "Introduces Boaz to the audience before he steps into the story. Places him among the family through Naomi's tie to her dead husband and through the clan.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B13",
            "role_in_scene": "KINSMAN",
            "presence": "REFERENCED",
            "referential_form": "NAMED"
          },
          {
            "being_id": "B3",
            "role_in_scene": "MOTHER_IN_LAW",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B2",
            "role_in_scene": "ANCESTOR",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B29",
            "role_in_scene": "REDEEMER_KIN",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "_note": "No distinct place anchored in the narrator-parenthetical; the introduction is given outside the storyline.",
        "entries": null
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0032"
          }
        ]
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; the narrator-parenthetical is given outside the storyline's time-flow.",
        "entries": null
      },
      "significant_absence": "Narrator never says where Boaz is, or what he is doing. Nothing of what is in him — no aim, no leaning toward the women, no awareness that they have come back."
    },
    {
      "scene_id": "S2",
      "verse_range": "2:2",
      "scene_kind": "INITIATIVE_SCENE",
      "scene_communicative_purpose": "Shows that the gleaning is Ruth's own idea, not Naomi's. Naomi lets her go without changing a word of it. The exchange is short and close, and it matters.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B9",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "PRESENT",
            "referential_form": "NAMED"
          },
          {
            "being_id": "B3",
            "role_in_scene": "MOTHER_IN_LAW",
            "presence": "PRESENT",
            "referential_form": "NAMED"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL_NAOMIS_DWELLING"
          },
          {
            "place_id": "PL5"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0033"
          },
          {
            "object_id": "CB_0034"
          }
        ]
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; time is continuous with the previous pericope's arrival.",
        "entries": null
      },
      "significant_absence": "Naomi does not name Boaz to Ruth, even though the narrator has just named Boaz to the audience one verse before at v.1. She names no particular field, does not bless Ruth, does not warn her of any danger, does not point her to a kinsman. The audience knows the very thing Naomi does not yet say."
    },
    {
      "scene_id": "S3",
      "verse_range": "2:3-4",
      "scene_kind": "ARRIVAL_SCENE",
      "scene_communicative_purpose": "Brings Ruth into Boaz's field by a turn the narrator tells so you can't tell if it is chance or God's hand. Shows Boaz arriving from Bethlehem. Sets the field-community's covenant-blessing tone through the greeting they trade. Names the clan again at the very moment of her chance arrival.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B9",
            "role_in_scene": "GLEANER",
            "presence": "PRESENT",
            "referential_form": "NAMED"
          },
          {
            "being_id": "B13",
            "role_in_scene": "FIELD_OWNER",
            "presence": "PRESENT",
            "referential_form": "NAMED"
          },
          {
            "being_id": "B14",
            "role_in_scene": "HARVESTERS",
            "presence": "PRESENT_COLLECTIVE"
          },
          {
            "being_id": "B10",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B29",
            "role_in_scene": "REDEEMER_KIN",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL5"
          },
          {
            "place_id": "PL5_BOAZ_PORTION"
          },
          {
            "place_id": "PL1"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0035"
          },
          {
            "object_id": "CB_0008"
          }
        ]
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; the barley-harvest setting from P04 v.22 is the active frame and is not lexically named here.",
        "entries": null
      },
      "significant_absence": "Narrator never says God led Ruth to Boaz's field; the 'chance' wording leaves the one who led her there unnamed on purpose. He never says Boaz notices Ruth when he arrives. Ruth says nothing in this scene. Naomi is off the scene, and no one in it so much as mentions her."
    },
    {
      "scene_id": "S4",
      "verse_range": "2:5-7",
      "scene_kind": "REPORT_SCENE",
      "scene_communicative_purpose": "Shows the first time the outsider gleaner is named out loud among the field-workers. The field's owner asks whose young woman this is; the foreman tells him where she is from, how she is tied to her mother-in-law, what she asked when she came to glean, and how she has worked from morning until now.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B13",
            "role_in_scene": "FIELD_OWNER",
            "presence": "PRESENT",
            "referential_form": "NAMED"
          },
          {
            "being_id": "B15",
            "role_in_scene": "FOREMAN",
            "presence": "PRESENT",
            "referential_form": "NAAR_NITSAV_AL_HAQOTSRIM"
          },
          {
            "being_id": "B9",
            "role_in_scene": "GLEANER",
            "presence": "REFERENCED",
            "referential_form": "NAARA_MOABIYAH"
          },
          {
            "being_id": "B3",
            "role_in_scene": "MOTHER_IN_LAW",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B14",
            "role_in_scene": "HARVESTERS",
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
            "place_id": "PL2"
          },
          {
            "place_id": "PL_HA_BAYIT_FIELD_SHELTER"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "TH_WITHIN_DAY_FROM_MORNING_UNTIL_NOW"
          }
        ]
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; the within-day duration 'from morning until now' is a content element inside the foreman's quoted report, encoded in objects_in_scene, not as a scene-setting time frame. Follows P01 TM_TEN_YEARS approximate-duration precedent.",
        "entries": null
      },
      "significant_absence": "Foreman never gives Ruth's own name; he places her by where she is from, by her tie to Naomi, by how she has worked. Narrator tells us nothing of what is in Boaz as he asks — no surprise, no recognition, no leaning toward her. In the way it is framed, the question carries no particular feeling."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "2:1",
      "proposition_kind": "NARRATOR_INTRODUCES",
      "event_specific_slots": {
        "introduction_components": [
          {
            "action": "POSITIONED",
            "kinsman": "B13",
            "kinship_anchor_being": "B3",
            "kinship_anchor_relation": "WIDOW",
            "deceased_ancestor": "B2",
            "list_position": "FIRST",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "INTRODUCED",
            "introduced_party": "B13",
            "introduction_attribute": "PERSON_OF_STANDING",
            "chayil_lexeme": "CB_0032",
            "list_position": "SECOND",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "PLACED",
            "placed_party": "B13",
            "clan": "B29",
            "clan_eponym": "B2",
            "list_position": "THIRD",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "NAMED",
            "named_party": "B13",
            "given_name": "Boaz",
            "list_position": "FOURTH",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "forward_link_to": "P2"
      },
      "cb_flags": ["CB_0032"],
      "figure_flags": ["FIG_0090", "FIG_0134"]
    },
    {
      "prop_id": "P2",
      "scene_link": "S2",
      "verse_anchor": "2:2a",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "requester": "B9",
        "addressee": "B3",
        "destination": "PL5",
        "speech_act": "REQUESTS_PERMISSION_TO_DO"
      },
      "inter_proposition_links": {
        "forward_link_to": "P3"
      },
      "cb_flags": ["CB_0033", "CB_0034", "CB_0004"],
      "figure_flags": ["FIG_0001", "FIG_0018"]
    },
    {
      "prop_id": "P3",
      "scene_link": "S2",
      "verse_anchor": "2:2b",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "permission_granter": "B3",
        "permitted_party": "B9",
        "addressed_form": "DAUGHTER",
        "speech_act": "GRANTS_PERMISSION_TO_DO"
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
      "scene_link": "S3",
      "verse_anchor": "2:3a",
      "proposition_kind": "GLEANED",
      "event_specific_slots": {
        "gleaner": "B9",
        "destination": "PL5",
        "gleaning_position_relation": "BEHIND_HARVESTERS",
        "harvesters": "B14",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P3",
        "forward_link_to": "P5"
      },
      "cb_flags": ["CB_0034"],
      "figure_flags": []
    },
    {
      "prop_id": "P5",
      "scene_link": "S3",
      "verse_anchor": "2:3b",
      "proposition_kind": "ARRIVED_AT",
      "event_specific_slots": {
        "gleaner": "B9",
        "arrived_at_portion": "PL5_BOAZ_PORTION",
        "portion_belongs_to": "B13",
        "clan_restated": "B29",
        "clan_eponym": "B2",
        "named_doer": "NONE",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P4",
        "forward_link_to": "P6"
      },
      "cross_ref": "FIG_0088 closes here; opened at P04 P5-P6 (Naomi's empty-lament at v.21 / harvest-setting at v.22)",
      "cb_flags": ["CB_0035"],
      "figure_flags": ["FIG_0015", "FIG_0088"]
    },
    {
      "prop_id": "P6",
      "scene_link": "S3",
      "verse_anchor": "2:4a",
      "proposition_kind": "ARRIVED_AT",
      "event_specific_slots": {
        "arriver": "B13",
        "origin": "PL1",
        "destination": "PL5_BOAZ_PORTION",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P7"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P7",
      "scene_link": "S3",
      "verse_anchor": "2:4b",
      "proposition_kind": "BLESSING",
      "event_specific_slots": {
        "greeting_components": [
          {
            "action": "GREETED",
            "greeter": "B13",
            "greeted_party": "B14",
            "invoked_deity": "B10",
            "list_position": "FIRST",
            "speech_act": "WISHES_FOR_HEARER"
          },
          {
            "action": "BLESSED",
            "blesser": "B14",
            "blessed_party": "B13",
            "invoked_deity": "B10",
            "list_position": "SECOND",
            "speech_act": "WISHES_FOR_HEARER"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P6",
        "forward_link_to": "P8"
      },
      "cb_flags": ["CB_0008"],
      "figure_flags": ["FIG_0092", "FIG_0093"]
    },
    {
      "prop_id": "P8",
      "scene_link": "S4",
      "verse_anchor": "2:5",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "question_asker": "B13",
        "question_addressee": "B15",
        "question_target": "B9",
        "speech_act": "ASKS_KINSHIP_BELONGING_QUESTION"
      },
      "inter_proposition_links": {
        "forward_link_to": "P9"
      },
      "cb_flags": ["CB_0036"],
      "figure_flags": ["FIG_0091", "FIG_0094"]
    },
    {
      "prop_id": "P9",
      "scene_link": "S4",
      "verse_anchor": "2:6-7",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "reporter": "B15",
        "report_addressee": "B13",
        "reported_about": "B9",
        "report_components": [
          {
            "action": "IDENTIFIED",
            "identified_party": "B9",
            "list_position": "FIRST",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "IDENTIFIED",
            "identified_party": "B9",
            "kinship_anchor_being": "B3",
            "return_origin": "PL2",
            "list_position": "SECOND",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "REPORTED",
            "quoted_prior_speaker": "B9",
            "quoted_prior_speech_act": "REQUESTS_PERMISSION_TO_DO",
            "list_position": "THIRD",
            "speech_act": "REPORTS_PRIOR_SPEECH_REQUEST"
          },
          {
            "action": "REPORTED",
            "list_position": "FOURTH",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "REPORTED",
            "shelter_place": "PL_HA_BAYIT_FIELD_SHELTER",
            "textual_clarity_flag": true,
            "list_position": "FIFTH",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P8"
      },
      "cross_ref": "FIG_0001 third-party-voice reactivation at v.6 (carry-forward arc: opened P01 v.4 narrator → withheld P02-P03 → narrator-voice P04 v.22 → narrator-epithet P05 v.2 → third-party-voice P05 v.6)",
      "cb_flags": ["CB_0004", "CB_0034", "CB_0036"],
      "figure_flags": ["FIG_0001", "FIG_0091"]
    }
  ]
}
```

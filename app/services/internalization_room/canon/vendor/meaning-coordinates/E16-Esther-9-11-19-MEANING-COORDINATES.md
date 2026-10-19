---
type: "sta-meaning-coordinates"
pericope: "E16"
pericope-title: "The Susa toll, Esther's second request, and the two days of feasting"
source-meaning-map: [[E16-Esther-9-11-19]]
status: "valid"
pilot: "pilot-2"
---

# E16 — Esther 9:11–19 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "esther_pericope_16_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Esther 9:11-19",
    "pericope_title": "The Susa toll, Esther's second request, and the two days of feasting",
    "book_context_ref": "esther_pilot_BCD_v0_1",
    "source_meaning_map_ref": "E16-Esther-9-11-19",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "Whole passage stays INFORMAL_CASUAL — the storyteller's plain voice reporting a toll, a request, and a feast, with palace conversation quoted but no edict text read out. The v.14 'a decree (dat) was given out in Susa' is the narrator REPORTING that an order issued, not the decree's own words being voiced, so NO FORMAL_OFFICIAL moment-override lands here (Mapper's note 1, surfaced for Marcia). v.17-19 brushes the book's closing COMMUNITY_MEMORY frame ('For this reason the Jews of the open country keep the fourteenth…'); the full framing belongs to the next pericope, so it is a first touch only — recorded as one moment-level NARRATIVE_FRAMING override at 9:19, the rest staying INFORMAL_CASUAL.",
      "scene_level": null,
      "moment_level": [
        {
          "verse": "9:19",
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
      "SECOND_REQUEST_GRANTED",
      "SECOND_DAY_OF_ACTION",
      "PLUNDER_REFUSED",
      "PUBLIC_FEAST",
      "FESTIVAL_FOUNDED"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "POLITICAL_CONTEXT",
      "TEMPORAL_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT"
    ],
    "tone_elements": [
      "SOBER",
      "ECONOMICAL",
      "GRIMLY_SATISFIED",
      "RESTRAINED",
      "TURNING_LITURGICAL"
    ],
    "pace_elements": [
      "SLOWED",
      "WIDENS",
      "ACCELERATES",
      "SETTLES"
    ],
    "communicative_function_elements": [
      "TALLIES",
      "GRANTS",
      "WITHHOLDS",
      "ADVANCES",
      "EXPLAINS",
      "TURNS_TO_FEAST"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "9:11-14",
      "scene_kind": "TOLL_REPORTED_AND_REQUEST_GRANTED_SCENE",
      "scene_communicative_purpose": "Reports the capital's death-toll and stages the king's granting of Esther's last two requests — a second day and the public hanging of the enemy's sons.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT",
            "referential_form": "THE_KING"
          },
          {
            "being_id": "B2",
            "role_in_scene": "QUEEN",
            "presence": "PRESENT",
            "referential_form": "ESTHER_THE_QUEEN"
          },
          {
            "being_id": "B17",
            "role_in_scene": "DELIVERED_PEOPLE",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B16",
            "role_in_scene": "SLAIN_SONS",
            "presence": "REFERENCED",
            "referential_form": "TEN_SONS_OF_HAMAN"
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
        "_note": "The royal order issued in Susa ('a decree, dat, was given out') maps to the registered INSTITUTION I2 (the law/dat). The MEANING_COORDINATES scene containers have no institution slot and object_id excludes I-codes, so the decree rides as bare-atom content in Prop 4 (governing_rule:THE_DECREE); its per-pericope tracking lives in the registry appears_in (E16 listed). The five hundred slain are a count/toll, not a character — carried as a descriptive number in Prop 2, no B-code. The gallows is the only persistent registry object here.",
        "entries": [
          {
            "object_id": "TH_GALLOWS"
          }
        ]
      },
      "times_in_scene": {
        "_note": "'That day' (the day the Susa toll is reported, the thirteenth of Adar) and 'tomorrow' (the morrow Esther asks for, the fourteenth) are in-the-moment day-references carried as content in the propositions, anchored to the registered month Adar; they are not distinct registry time codes for this scene.",
        "entries": null
      },
      "significant_absence": "No God is named — not in the king's wondering question, not in the queen's measured request, not over the granting. The deliverance is asked for and given entirely in the human key of court speech. And Esther gives no reason for either request — no anger voiced, no vengeance named; the motive behind the second day and the hanging is left unspoken, carried only by the bare asking."
    },
    {
      "scene_id": "S2",
      "verse_range": "9:15-16",
      "scene_kind": "SECOND_DAY_AND_PROVINCIAL_RECKONING_SCENE",
      "scene_communicative_purpose": "Records the second day's killing in the capital and the empire-wide toll, twice marking that the Jews took no plunder — and sets up the difference in timing between Susa and the provinces.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B17",
            "role_in_scene": "DELIVERED_PEOPLE",
            "presence": "PRESENT",
            "referential_form": "THE_JEWS_OF_SUSA"
          },
          {
            "being_id": "B17",
            "role_in_scene": "DELIVERED_PEOPLE",
            "presence": "REFERENCED",
            "referential_form": "THE_REST_OF_THE_JEWS_IN_THE_PROVINCES"
          },
          {
            "being_id": "B20",
            "role_in_scene": "SLAIN_FOES",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "_note": "Susa the citadel (PL1) is the place of the second-day killing. 'The king's provinces' — the empire-wide setting where the seventy-five thousand fell — maps to the registered INSTITUTION I5 (the 127 provinces); since object_id/place_id exclude I-codes, it rides as bare-atom content in Prop 6 (realm_span:THE_PROVINCES). The three hundred slain and the seventy-five thousand are counts/tolls, not characters — descriptive numbers in Props 5 and 6, no B-code.",
        "entries": [
          {
            "place_id": "PL1"
          }
        ]
      },
      "objects_in_scene": {
        "_note": "The plunder not taken (the spoil the Jews were permitted to seize but did not) is the load-bearing restraint, stated twice; it is carried as bare-atom content in Props 5 and 6 (spoil:UNTOUCHED), with the verbatim repetition protected by preserve_form on the no-plunder slot in both. No persistent registry object in this scene.",
        "entries": null
      },
      "times_in_scene": {
        "_note": "'The fourteenth of Adar' (Susa's second day) and 'the thirteenth of Adar' (the provinces' one day) are day-numbers anchored to the registered month Adar, carried as content in the propositions; not distinct registry time codes for this scene.",
        "entries": null
      },
      "significant_absence": "No God is named over the deliverance, even at its great summary number. And no spoil is taken — twice the line refuses it. In a world (and a genre) where the victors plunder the fallen, the doubled withholding of the hand from the spoil is the absence the narrator most wants heard: this is not enrichment, it is survival."
    },
    {
      "scene_id": "S3",
      "verse_range": "9:17-19",
      "scene_kind": "FESTIVAL_FOUNDING_SCENE",
      "scene_communicative_purpose": "Explains, by who rested on which day, why there come to be two days of feasting — the fourteenth kept by the open-town Jews, the fifteenth by the Jews of Susa — and shows the festival taking its shape: rest, gladness, feasting, and gifts of food.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B17",
            "role_in_scene": "DELIVERED_PEOPLE",
            "presence": "PRESENT"
          },
          {
            "being_id": "B17",
            "role_in_scene": "DELIVERED_PEOPLE",
            "presence": "PRESENT",
            "referential_form": "THE_JEWS_OF_SUSA"
          },
          {
            "being_id": "B17",
            "role_in_scene": "DELIVERED_PEOPLE",
            "presence": "PRESENT",
            "referential_form": "THE_JEWS_OF_THE_OPEN_TOWNS"
          }
        ]
      },
      "places_in_scene": {
        "_note": "Susa the citadel (PL1), whose Jews rest on the fifteenth. 'The open towns / unwalled villages' (the country settlements whose Jews keep the fourteenth) is not a registered place — it rides as bare-atom content in Prop 9 (settlement_kind:UNWALLED_TOWNS); the walled-vs-unwalled difference is the etiology, carried in prose.",
        "entries": [
          {
            "place_id": "PL1"
          }
        ]
      },
      "objects_in_scene": {
        "_note": "'A day of feasting and gladness' is the festal day taking shape; the feast (the mishteh, registered INSTITUTION I1) rides as bare-atom content in the propositions (banquet_named:MISHTEH) since object_id excludes I-codes. 'The sending of portions' (mishloach manot) is not a registered object — it rides as bare-atom content in Prop 9 (custom:SENDING_PORTIONS). No persistent registry object in this scene.",
        "entries": null
      },
      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_ADAR"
          }
        ]
      },
      "significant_absence": "No God is named, even as the people turn from rescue to rejoicing — there is no thanksgiving spoken, no prayer, no altar; the gladness is simply kept. And the festival here has no name yet: the word Purim does not appear in this passage. The day is described — feasting, gladness, portions sent — but not yet titled or commanded; that naming is held back for the next pericope."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "9:11",
      "proposition_kind": "HEARD_REPORT",
      "event_specific_slots": {
        "count_of": "THE_SLAIN",
        "where": "PL1",
        "brought_before": "B4",
        "when": "THAT_DAY"
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
      "verse_anchor": "9:12",
      "proposition_kind": "KING_REPORTS_TOLL_AND_ASKS_REQUEST",
      "event_specific_slots": {
        "speaker": "B4",
        "addressee": "B2",
        "report_components": [
          {
            "reported_killers": "B17",
            "slain_count": "FIVE_HUNDRED",
            "where": "PL1",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "reported_slain": "B16",
            "slain_count": "TEN",
            "speech_act": "STATES_AS_TRUE"
          }
        ],
        "question_components": [
          {
            "wondered_about": "THE_PROVINCES",
            "speech_act": "ASKS_DELIBERATIVE_QUESTION"
          },
          {
            "elicited": "YOUR_REQUEST",
            "speech_act": "ASKS_DELIBERATIVE_QUESTION"
          }
        ],
        "grant_components": [
          {
            "grant_pledged": "THE_REQUEST",
            "granted_to": "B2",
            "status": "FORESEEN",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
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
      "verse_anchor": "9:13",
      "proposition_kind": "QUEEN_PETITIONS_FOR_SECOND_DAY_AND_HANGING",
      "event_specific_slots": {
        "speaker": "B2",
        "addressee": "B4",
        "petition_components": [
          {
            "granted_to": "B17",
            "granted_day": "TOMORROW",
            "granted_action": "TO_ACT",
            "by_measure": "TODAYS_DECREE",
            "status": "PERMITTED",
            "speech_act": "PETITIONS_FOR_GRANT"
          },
          {
            "hung_party": "B16",
            "hung_count": "TEN",
            "hung_on": "TH_GALLOWS",
            "status": "PERMITTED",
            "speech_act": "PETITIONS_FOR_GRANT"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P2",
        "condition_of": "P4",
        "forward_link_to": "P4"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P4",
      "scene_link": "S1",
      "verse_anchor": "9:14",
      "proposition_kind": "KING_DECREES_AND_SONS_HUNG",
      "event_specific_slots": {
        "speaker": "B4",
        "consent_to": "THE_DOING",
        "governing_rule": "THE_DECREE",
        "decree_place": "PL1",
        "speech_act": "PRESCRIBES_AS_LAW",
        "outcome_components": [
          {
            "hung_party": "B16",
            "hung_count": "TEN",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P3"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P5",
      "scene_link": "S2",
      "verse_anchor": "9:15",
      "proposition_kind": "SECOND_DAY_KILLING_IN_SUSA",
      "event_specific_slots": {
        "gatherers": "B17",
        "referential_form_at_verse": "THE_JEWS_OF_SUSA",
        "when": "FOURTEENTH",
        "of_month": "TM_ADAR",
        "where": "PL1",
        "slain": "B20",
        "slain_count": "THREE_HUNDRED",
        "no_plunder_components": [
          {
            "spoil": "UNTOUCHED",
            "manner": "NO_HAND_LAID",
            "preserve_form": true,
            "speech_act": "STATES_AS_TRUE"
          }
        ]
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
      "verse_anchor": "9:16",
      "proposition_kind": "PROVINCIAL_DEFENCE_AND_REST",
      "event_specific_slots": {
        "gatherers": "B17",
        "referential_form_at_verse": "THE_REST_OF_THE_JEWS_IN_THE_PROVINCES",
        "realm_span": "THE_PROVINCES",
        "stood_for": "THEIR_LIVES",
        "rest_from": "B20",
        "slain": "B20",
        "slain_count": "SEVENTY_FIVE_THOUSAND",
        "no_plunder_components": [
          {
            "spoil": "UNTOUCHED",
            "manner": "NO_HAND_LAID",
            "preserve_form": true,
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "paired_with": "P5"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P7",
      "scene_link": "S3",
      "verse_anchor": "9:17",
      "proposition_kind": "PROVINCES_REST_AND_FEAST",
      "event_specific_slots": {
        "action_day": "THIRTEENTH",
        "of_month": "TM_ADAR",
        "rest_day": "FOURTEENTH",
        "made_into": "A_DAY",
        "day_kind": ["FEASTING", "GLADNESS"],
        "banquet_named": "MISHTEH"
      },
      "inter_proposition_links": {
        "forward_link_to": "P8"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P8",
      "scene_link": "S3",
      "verse_anchor": "9:18",
      "proposition_kind": "SUSA_RESTS_AND_FEASTS",
      "event_specific_slots": {
        "gatherers": "B17",
        "referential_form_at_verse": "THE_JEWS_OF_SUSA",
        "action_days": ["THIRTEENTH", "FOURTEENTH"],
        "rest_day": "FIFTEENTH",
        "made_into": "A_DAY",
        "day_kind": ["FEASTING", "GLADNESS"],
        "banquet_named": "MISHTEH"
      },
      "inter_proposition_links": {
        "paired_with": "P7",
        "forward_link_to": "P9"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P9",
      "scene_link": "S3",
      "verse_anchor": "9:19",
      "proposition_kind": "OPEN_TOWN_JEWS_KEEP_THE_FOURTEENTH",
      "status": "HABITUAL",
      "event_specific_slots": {
        "keepers": "B17",
        "referential_form_at_verse": "THE_JEWS_OF_THE_OPEN_TOWNS",
        "settlement_kind": "UNWALLED_TOWNS",
        "kept_day": "FOURTEENTH",
        "of_month": "TM_ADAR",
        "day_kind": ["GLADNESS", "FEASTING", "A_GOOD_DAY"],
        "custom": "SENDING_PORTIONS",
        "portions_from": "EACH",
        "portions_to": "A_NEIGHBOUR"
      },
      "inter_proposition_links": {
        "caused_by": "P8",
        "purpose_of": "P8"
      },
      "cb_flags": [],
      "figure_flags": []
    }
  ]
}
```

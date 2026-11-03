---
type: "sta-meaning-coordinates"
pericope: "E02"
pericope-title: "The queen's refusal and the empire's answer: Vashti deposed by decree"
source-meaning-map: [[E02-Esther-1-10-22]]
status: "valid"
pilot: "pilot-2"
---

# E02 — Esther 1:10–22 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "esther_pericope_02_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",

  "header": {
    "bcv": "Esther 1:10-22",
    "pericope_title": "The queen's refusal and the empire's answer: Vashti deposed by decree",
    "book_context_ref": "esther_pilot_BCD_v0_1",
    "source_meaning_map_ref": "E02-Esther-1-10-22",
    "source_language": "Biblical Hebrew"
  },

  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "The narrator's voice stays INFORMAL_CASUAL throughout. One moment-level FORMAL_OFFICIAL override across v.19-20 — Memucan stops arguing and voices the edict itself in its own official cadence ('let a royal word go out, and let it be written in the laws of Persia and Media… that Vashti come no more'). The surrounding speech (v.16-18, the argument) and the narrator's report of the king sending letters (v.22) stay INFORMAL_CASUAL — those are description/publication of a law, not a voiced/granted decree. Mapper's open call: confirm the override scope is the voiced decree v.19-20 only, not the whole of Memucan's speech v.16-20.",
      "scene_level": null,
      "moment_level": [
        {
          "verse": "1:19",
          "override_value": "FORMAL_OFFICIAL",
          "genre_override": null,
          "genre_group_override": null
        },
        {
          "verse": "1:20",
          "override_value": "FORMAL_OFFICIAL",
          "genre_override": null,
          "genre_group_override": null
        }
      ]
    }
  },

  "level_1": {
    "arc_elements": [
      "SUMMONS",
      "REFUSAL",
      "ROYAL_RAGE",
      "QUESTION_OF_LAW",
      "ROYAL_DECREE",
      "DECREE_DISPATCHED",
      "SEARCH_SET_IN_MOTION"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "POLITICAL_CONTEXT",
      "KINSHIP_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT"
    ],
    "tone_elements": [
      "TAUT",
      "FAINTLY_ABSURD",
      "DISPROPORTIONATE",
      "RISING",
      "COLD"
    ],
    "pace_elements": [
      "TURNING_HARD",
      "INFLATING_AT_COUNCIL",
      "CLOSING_FAST_AND_WIDE"
    ],
    "communicative_function_elements": [
      "OPENS",
      "PLANTS",
      "ESTABLISHES",
      "EMPTIES_THE_THRONE",
      "WITHHOLDS"
    ]
  },

  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "1:10-11",
      "scene_kind": "ROYAL_SUMMONS_SCENE",
      "scene_communicative_purpose": "Shows the drunken king commanding the queen be brought out and displayed like a treasure — the order that sets the crisis in motion.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT",
            "referential_form": "THE_KING_MERRY_WITH_WINE"
          },
          {
            "being_id": "B14",
            "role_in_scene": "NOBLES",
            "presence": "PRESENT",
            "referential_form": "THE_SEVEN_EUNUCHS_WHO_SERVE_BEFORE_HIM"
          },
          {
            "being_id": "B5",
            "role_in_scene": "QUEEN",
            "presence": "REFERENCED",
            "referential_form": "VASHTI_THE_QUEEN"
          }
        ]
      },

      "places_in_scene": {
        "_note": "No new place is set; the scene continues inside the king's seven-day feast in Susa the citadel (PL1, established in E01). The peoples-and-princes gathered before the king are an unregistered group carried as L3 bare-atom content (P2.shown_to), not a registry being; ruling on a B-code is surfaced for Marcia.",
        "entries": null
      },

      "objects_in_scene": {
        "entries": [
          {
            "object_id": "TH_ROYAL_CROWN"
          }
        ]
      },

      "times_in_scene": {
        "_note": "The seventh day (the last day of the feast) is carried as L3 content (P1.day_ordinal), a day of the feast already established in E01, not a registered TM_ time.",
        "entries": null
      },

      "significant_absence": "God is not named, and is not invoked over the feast or the command. No reason is given for the summons beyond display, and no thought is given to whether the queen would consent. Her own voice is entirely absent here: she is spoken about and sent for, never asked."
    },

    {
      "scene_id": "S2",
      "verse_range": "1:12-15",
      "scene_kind": "REFUSAL_AND_QUESTION_OF_LAW_SCENE",
      "scene_communicative_purpose": "Shows the refusal, the king's instant fury, and his choice to convert a private slight into a question of law before his counsellors — opening the door for the decree.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B5",
            "role_in_scene": "QUEEN",
            "presence": "PRESENT",
            "referential_form": "QUEEN_VASHTI"
          },
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT",
            "referential_form": "THE_KING_IN_RAGE"
          },
          {
            "being_id": "B14",
            "role_in_scene": "NOBLES",
            "presence": "REFERENCED",
            "referential_form": "THE_EUNUCHS"
          },
          {
            "being_id": "B15",
            "role_in_scene": "NOBLES",
            "presence": "PRESENT",
            "referential_form": "WISE_MEN_WHO_KNOW_THE_TIMES"
          }
        ]
      },

      "places_in_scene": {
        "_note": "No new place is set; the rage and consultation follow at once within the court of the feast. The wise men who know law and judgment resolve to B15 (the seven princes nearest the king, named in P5); 'all who know law and judgment' is carried as L3 bare-atom content (P4.put_before).",
        "entries": null
      },

      "objects_in_scene": {
        "_note": "The law (I2 / dat, a registered INSTITUTION) is the legal frame the king appeals to; the MEANING_COORDINATES scene containers have no institution slot and object_id excludes I-codes, so the law rides as a bare-atom L3 slot (P6.governing_rule: THE_LAW); its per-pericope tracking lives in the registry appears_in (E02). The king's word that Vashti disobeyed is bare-atom L3 content (P3.refused_word), not a registry object.",
        "entries": null
      },

      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; the rage and the consultation follow immediately on the refusal.",
        "entries": null
      },

      "significant_absence": "Vashti gives no reason for her refusal — the narrator records the 'no' and not a word of why. God is again unnamed; the king appeals not to any divine law but to Persian law and precedent. And the queen, having spoken her one act of refusal, is now spoken about only in the third person — judged in her absence, never summoned to answer."
    },

    {
      "scene_id": "S3",
      "verse_range": "1:16-20",
      "scene_kind": "DECREE_SCENE",
      "scene_communicative_purpose": "Shows the king's nearest counsellor magnifying a private refusal into an empire-wide threat and answering it with a voiced, irrevocable decree — the engine of the whole book set running.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B10",
            "role_in_scene": "ADVISERS",
            "presence": "PRESENT",
            "referential_form": "MEMUCAN"
          },
          {
            "being_id": "B15",
            "role_in_scene": "NOBLES",
            "presence": "PRESENT",
            "referential_form": "THE_KINGS_PRINCES"
          },
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT",
            "referential_form": "THE_KING"
          },
          {
            "being_id": "B5",
            "role_in_scene": "QUEEN",
            "presence": "REFERENCED",
            "referential_form": "QUEEN_VASHTI"
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
        "_note": "The law (I2 / dat, the irrevocable law-form the edict is to take) and the realm-span (I5, the 127 provinces, the reach Memucan invokes) are registered INSTITUTIONS carried as L3 bare-atom slots (P10.written_into: THE_LAW; P7.spanning: THE_PROVINCES), not scene objects, since object_id/place_id exclude I-codes. The voiced royal word/decree, the queen's royal estate, and 'this very day' are bare-atom L3 content (P10), not registry objects. The empire's wives and the noble ladies of Persia and Media are unregistered groups carried as L3 bare-atom content (P8, P9); a B-code ruling is surfaced for Marcia.",
        "entries": null
      },

      "times_in_scene": {
        "_note": "'This very day' (the urgency Memucan presses) is bare-atom L3 content (P9.when: THIS_DAY), not a registry time.",
        "entries": null
      },

      "significant_absence": "No one speaks for Vashti; no defence, no inquiry, no hearing — judgment is passed on her in her absence and she is never named again after the decree. God is not invoked to sanction the law. And there is no proportion: an empire's machinery of irrevocable law is turned on a single act of a single woman, with no voice raised against the scale of the response."
    },

    {
      "scene_id": "S4",
      "verse_range": "1:21-22",
      "scene_kind": "DECREE_SCENE",
      "scene_communicative_purpose": "Shows the king ratifying the decree and dispatching it across the whole empire — a private refusal sealed as published, irrevocable law.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT",
            "referential_form": "THE_KING"
          },
          {
            "being_id": "B15",
            "role_in_scene": "NOBLES",
            "presence": "PRESENT",
            "referential_form": "THE_PRINCES"
          },
          {
            "being_id": "B10",
            "role_in_scene": "ADVISERS",
            "presence": "REFERENCED",
            "referential_form": "MEMUCAN"
          }
        ]
      },

      "places_in_scene": {
        "_note": "The realm-span (I5, all the king's provinces, the destination of the letters) is a registered INSTITUTION carried as an L3 bare-atom slot (P13.sent_to: THE_PROVINCES), not a scene place, since place_id excludes I-codes. Persia and Media (PL6/PL7), the realm whose unchangeable law the decree now is, are implied from Scene 3; no new place-setting in this scene.",
        "entries": null
      },

      "objects_in_scene": {
        "entries": [
          {
            "object_id": "TH_EDICT"
          }
        ]
      },

      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; the approval and sending follow at once on Memucan's speech.",
        "entries": null
      },

      "significant_absence": "Vashti is gone — never named again, her fate sealed without her presence. God is not named over the decree. And no one in the council or the empire is recorded as questioning either the law or its absurd scale: the disproportion is broadcast as wisdom, with no dissenting voice anywhere in view."
    }
  ],

  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "1:10",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "commanding_king": "B4",
        "king_named": "AHASUERUS",
        "king_state": "MERRY_WITH_WINE",
        "merry_seat": "HIS_HEART",
        "day_ordinal": "SEVENTH",
        "commanded_attendants": "B14",
        "attendant_count": "SEVEN",
        "attendant_office": "SERVING",
        "serves_before": "B4"
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
      "verse_anchor": "1:11",
      "proposition_kind": "INSTRUCTION",
      "status": "FORESEEN",
      "event_specific_slots": {
        "commanded_within": "P1",
        "bring_target": "B5",
        "target_capacity": "QUEEN",
        "bring_before": "B4",
        "wearing": "TH_ROYAL_CROWN",
        "crown_belonging": "ROYAL",
        "shown_to": ["THE_PEOPLES", "THE_PRINCES"],
        "displayed_attribute": "HER_BEAUTY",
        "reason_given": "BEAUTY_OF_APPEARANCE"
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
      "verse_anchor": "1:12",
      "proposition_kind": "DECLINED",
      "event_specific_slots": {
        "refuser": "B5",
        "refuser_capacity": "QUEEN",
        "refused_act": "COMING",
        "refused_word": "THE_KINGS_WORD",
        "word_carried_by": "B14",
        "consequence_components": [
          {
            "action": "GREW_ANGRY",
            "angered": "B4",
            "anger_degree": "VERY",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "BURNED",
            "burning": "HIS_RAGE",
            "burning_seat": "IN_HIM",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
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
      "verse_anchor": "1:13",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "speaker": "B4",
        "addressee": "WISE_MEN",
        "addressee_knowledge": "THE_TIMES",
        "reason": "THE_KINGS_CUSTOM",
        "put_before": "KNOWERS",
        "knowers_of": ["LAW", "JUDGMENT"]
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
      "scene_link": "S2",
      "verse_anchor": "1:14",
      "proposition_kind": "APPROACHED",
      "event_specific_slots": {
        "near_party": "B15",
        "near_to": "B4",
        "prince_count": "SEVEN",
        "princes_of": ["PL6", "PL7"],
        "sees": "THE_KINGS_FACE",
        "seated": "FIRST",
        "seated_in": "THE_KINGDOM"
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
      "verse_anchor": "1:15",
      "proposition_kind": "ASKED",
      "event_specific_slots": {
        "questioner": "B4",
        "governing_rule": "THE_LAW",
        "asked_about": "A_DOING",
        "doing_to": "B5",
        "doing_to_capacity": "QUEEN",
        "on_grounds_of": "A_NOT_DOING",
        "not_done_by": "B5",
        "not_done": "THE_KINGS_COMMAND",
        "command_carried_by": "B14",
        "speech_act": "ASKS_DELIBERATIVE_QUESTION"
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
      "verse_anchor": "1:16",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "alleger": "B10",
        "spoken_before": ["B4", "B15"],
        "wrong_doer": "B5",
        "doer_capacity": "QUEEN",
        "wronged_not_only": "B4",
        "wronged_also": ["THE_PRINCES", "THE_PEOPLES"],
        "spanning": "THE_PROVINCES",
        "provinces_of": "B4",
        "speech_act": "ALLEGES_AGAINST"
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
      "verse_anchor": "1:17",
      "proposition_kind": "DECLARED",
      "status": "FORESEEN",
      "event_specific_slots": {
        "voiced_within": "P7",
        "going_out": "THE_QUEENS_DEED",
        "deed_of": "B5",
        "out_to": "THE_WOMEN",
        "effect": "A_DESPISING",
        "despised": "THEIR_HUSBANDS",
        "despising_seat": "THEIR_EYES",
        "by_their_saying": "A_SAYING",
        "said_commander": "B4",
        "said_summoned": "B5",
        "said_outcome": "A_NOT_COMING",
        "speech_act": "ALLEGES_AGAINST"
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
      "scene_link": "S3",
      "verse_anchor": "1:18",
      "proposition_kind": "DECLARED",
      "status": "FORESEEN",
      "event_specific_slots": {
        "voiced_within": "P7",
        "when": "THIS_DAY",
        "sayers": "THE_LADIES",
        "ladies_of": ["PL6", "PL7"],
        "having_heard": "THE_QUEENS_DEED",
        "say_to": "THE_KINGS_PRINCES",
        "yielding": ["CONTEMPT", "ANGER"],
        "measure": "WITHOUT_END",
        "speech_act": "ALLEGES_AGAINST"
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
      "scene_link": "S3",
      "verse_anchor": "1:19",
      "proposition_kind": "PROPOSED",
      "event_specific_slots": {
        "proposer": "B10",
        "addressed_to": "B4",
        "let_go_out": "A_ROYAL_WORD",
        "out_from": "B4",
        "written_into": "THE_LAW",
        "law_of": ["PL6", "PL7"],
        "character": "IRREVOCABLE",
        "decree_components": [
          {
            "action": "DIRECTED",
            "barred_one": "B5",
            "barred_from": "B4",
            "speech_act": "PROPOSES_COURSE_OF_ACTION"
          },
          {
            "action": "DECREED_GIVING",
            "giver": "B4",
            "given": "HER_ROYAL_ESTATE",
            "given_to": "ANOTHER",
            "other_quality": "BETTER_THAN_SHE",
            "speech_act": "PROPOSES_COURSE_OF_ACTION"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P9",
        "condition_of": "THE_KINGS_PLEASURE",
        "purpose_of": "IRREVOCABILITY",
        "forward_link_to": "P11"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P11",
      "scene_link": "S3",
      "verse_anchor": "1:20",
      "proposition_kind": "DECLARED",
      "status": "FORESEEN",
      "event_specific_slots": {
        "voiced_within": "P10",
        "heard": "THE_KINGS_DECREE",
        "decree_of": "B4",
        "heard_in": "HIS_REALM",
        "realm_extent": "THE_WHOLE",
        "realm_size": "VAST",
        "then_giving": "HONOUR",
        "givers": "THE_WOMEN",
        "giver_extent": "ALL",
        "given_to": "THEIR_HUSBANDS",
        "from_high": "THE_GREAT",
        "to_low": "THE_SMALL",
        "speech_act": "PROPOSES_COURSE_OF_ACTION"
      },
      "inter_proposition_links": {
        "caused_by": "P10"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P12",
      "scene_link": "S4",
      "verse_anchor": "1:21",
      "proposition_kind": "COUNSEL_APPROVED",
      "event_specific_slots": {
        "pleasing_matter": "THE_WORD",
        "pleased": ["B4", "B15"],
        "then_acting": "B4",
        "acting_by": "MEMUCANS_WORD"
      },
      "inter_proposition_links": {
        "caused_by": "P10",
        "forward_link_to": "P13"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P13",
      "scene_link": "S4",
      "verse_anchor": "1:22",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "sender": "B4",
        "sent": "TH_EDICT",
        "sent_to": "THE_PROVINCES",
        "provinces_of": "B4",
        "province_extent": "EVERY_ONE",
        "written_in": "ITS_SCRIPT",
        "to_each_people": "EVERY_PEOPLE",
        "in_each_tongue": "ITS_TONGUE",
        "decree_content_components": [
          {
            "action": "DIRECTED",
            "ruler": "EVERY_MAN",
            "rules_in": "HIS_HOUSE",
            "speech_act": "PRESCRIBES_AS_LAW"
          },
          {
            "action": "PRESCRIBED_SPEAKING",
            "speaking_manner": "IN_THE_TONGUE",
            "tongue_of": "HIS_PEOPLE",
            "speech_act": "PRESCRIBES_AS_LAW"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P12"
      },
      "cb_flags": [],
      "figure_flags": []
    }
  ]
}
```

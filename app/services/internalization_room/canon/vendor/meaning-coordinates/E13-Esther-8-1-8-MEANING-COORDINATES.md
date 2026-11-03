---
type: "sta-meaning-coordinates"
pericope: "E13"
pericope-title: "The reversal of the ring: Haman's house to Esther, the signet to Mordecai, and a new decree the king grants"
source-meaning-map: [[E13-Esther-8-1-8]]
status: "valid"
pilot: "pilot-2"
---

# E13 — Esther 8:1–8 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "esther_pericope_13_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Esther 8:1-8",
    "pericope_title": "The reversal of the ring: Haman's house to Esther, the signet to Mordecai, and a new decree the king grants",
    "book_context_ref": "esther_pilot_BCD_v0_1",
    "source_meaning_map_ref": "E13-Esther-8-1-8",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "Whole passage stays INFORMAL_CASUAL — the plain narrator's voice reporting a swift throne-room turn, and Esther's plea is a deferential courtier's petition (quoted speech), not a decree. One moment-level FORMAL_OFFICIAL override at v.8b, where the king voices the irrevocable Medo-Persian decree-rule as binding law in his own mouth (the legal voice surfacing inside his speech). No COMMUNITY_MEMORY framing-lift: this is mid-book, deep in the action.",
      "scene_level": null,
      "moment_level": [
        {
          "verse": "8:8b",
          "override_value": "FORMAL_OFFICIAL",
          "genre_override": null,
          "genre_group_override": null
        }
      ]
    }
  },
  "level_1": {
    "arc_elements": [
      "GREAT_REVERSAL",
      "FAVOR_GRANTED",
      "PLEA_FOR_LIFE",
      "FAVOUR_GRANTED",
      "ROYAL_DECREE",
      "IRREVOCABLE_LIMIT"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "KINSHIP_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "POLITICAL_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT",
      "PERIL_CONTEXT"
    ],
    "tone_elements": [
      "DECISIVE",
      "RAW",
      "WEIGHTED",
      "TAUT",
      "ABSOLUTE"
    ],
    "pace_elements": [
      "BRISK",
      "BREAKING_TO_ANGUISH",
      "SETTLES"
    ],
    "communicative_function_elements": [
      "GRANTS",
      "HANDS_TOKENS",
      "VOICES_PLEA",
      "GRANTS_THE_PEN",
      "STATES_THE_LIMIT",
      "OPENS"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "8:1-2",
      "scene_kind": "AUTHORITY_GRANT_SCENE",
      "scene_communicative_purpose": "Shows authority and property passing from the fallen enemy to Esther and Mordecai — the house given, the ring transferred, Mordecai set in charge.",
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
            "being_id": "B1",
            "role_in_scene": "HONORED_ONE",
            "presence": "PRESENT"
          },
          {
            "being_id": "B3",
            "role_in_scene": "ADVERSARY",
            "presence": "REFERENCED",
            "referential_form": "THE_ENEMY_OF_THE_JEWS"
          },
          {
            "being_id": "B17",
            "role_in_scene": "THREATENED_PEOPLE",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "_note": "The royal presence (before the king) is the audience setting, a sub-location of the palace at Susa carried as scene-content prose, not a registry place. No registry place code in this scene (per the map's Scene 1).",
        "entries": null
      },
      "objects_in_scene": {
        "_note": "The house of Haman is the confiscated estate — a property handed over, carried as bare-atom content in the propositions, not a registry object. The signet ring (TH_SIGNET_RING) is the persistent registry object here.",
        "entries": [
          {
            "object_id": "TH_SIGNET_RING"
          }
        ]
      },
      "times_in_scene": {
        "_note": "'On that day' (the day of Haman's fall) is a bare descriptive scene-time, a back-reference to the prior scene, not a registry time-anchor; carried as content in Prop 1.",
        "entries": null
      },
      "significant_absence": "God is not named, though this is the decisive turn the whole book has built toward — the rescue advances by a ring and a deed of property, not by any word of the One who is never mentioned. And the king still asks nothing about who these people are or why their fates are bound together; the relationship is told to him in a half-line and passed over."
    },
    {
      "scene_id": "S2",
      "verse_range": "8:3-6",
      "scene_kind": "APPEAL_SCENE",
      "scene_communicative_purpose": "Shows Esther's desperate, formally-couched plea to revoke the standing death-decree, and the king's scepter-sign that she is heard — opening the question the rest of the book answers.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B2",
            "role_in_scene": "SUPPLIANT",
            "presence": "PRESENT"
          },
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT",
            "referential_form": "THE_KING"
          },
          {
            "being_id": "B3",
            "role_in_scene": "SCRIBES",
            "presence": "REFERENCED",
            "referential_form": "THE_AGAGITE"
          },
          {
            "being_id": "B17",
            "role_in_scene": "THREATENED_PEOPLE",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "_note": "The king's feet / before the king is the floor of the royal audience, carried as scene-content prose; no registry place code. The reach of the death-decree ('all the king's provinces', I5 in the registry) is left as descriptive scope-prose in this map, carried as bare-atom content in Prop 14, not wikilinked here.",
        "entries": null
      },
      "objects_in_scene": {
        "_note": "The evil / plan of Haman is the surviving scheme Esther asks be undone — bare-atom content in the propositions, not a registry object. The scepter (TH_SCEPTER) and the letters / death-decree (TH_EDICT) are the persistent registry objects here.",
        "entries": [
          {
            "object_id": "TH_SCEPTER"
          },
          {
            "object_id": "TH_EDICT"
          }
        ]
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; the plea follows directly on the handover, the same audience continuing.",
        "entries": null
      },
      "significant_absence": "Esther names her people and her kindred — but still never names her God, and pleads no covenant, no promise, no divine claim; the whole appeal is made in the language of the court (\"if it please the king,\" \"favour in your eyes\"), not of prayer. And she does not ask for revenge or for power; she asks only that the writing be turned back — the precise thing the law will not allow."
    },
    {
      "scene_id": "S3",
      "verse_range": "8:7-8",
      "scene_kind": "AUTHORITY_GRANT_SCENE",
      "scene_communicative_purpose": "Shows the king granting Esther and Mordecai the authority to write a new decree under his seal, and stating the irrevocable-law rule that makes a counter-decree the only road to rescue.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT",
            "referential_form": "KING_AHASUERUS"
          },
          {
            "being_id": "B2",
            "role_in_scene": "HONORED_ONE",
            "presence": "PRESENT",
            "referential_form": "ESTHER_THE_QUEEN"
          },
          {
            "being_id": "B1",
            "role_in_scene": "HONORED_ONE",
            "presence": "PRESENT",
            "referential_form": "MORDECAI_THE_JEW"
          },
          {
            "being_id": "B3",
            "role_in_scene": "ADVERSARY",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B17",
            "role_in_scene": "THREATENED_PEOPLE",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "_note": "The royal presence (the continuing audience) is the throne-room setting, carried as scene-content prose; no registry place code. The tree / gallows (where Haman was hanged) is referenced inside the king's speech as a thing, carried via TH_GALLOWS in Prop 19, not as a place here.",
        "entries": null
      },
      "objects_in_scene": {
        "_note": "The writing / new counter-decree to be written is carried as bare-atom content in the granted-writing proposition, not minted as a separate registry object (surfaced for Marcia — track distinctly from Haman's TH_EDICT?). The law of the Medes and Persians (I2 / dat, a registered INSTITUTION) is the irrevocable-decree rule voiced in Prop 22; the MEANING_COORDINATES scene containers have no institution slot and object_id excludes I-codes, so the rule rides as bare-atom content in the proposition. The signet ring (TH_SIGNET_RING) and the gallows / tree (TH_GALLOWS, the execution site the king cites as proof Haman is judged, referenced inside his speech at Prop 19) are the persistent registry objects here.",
        "entries": [
          {
            "object_id": "TH_SIGNET_RING"
          },
          {
            "object_id": "TH_GALLOWS"
          }
        ]
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; the king's reply continues the same audience, directly after Esther's plea.",
        "entries": null
      },
      "significant_absence": "The king grants the pen but offers no plan, no protection, no word of how the Jews are to be saved — only the right to write, and the rule that the old decree stands. He does not revoke the death-sentence, does not promise an outcome, and names no help beyond his seal. And once more no God is invoked over the moment of deliverance's opening; the rescue is left entirely to a ring, a name, and what two people will write."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "8:1",
      "proposition_kind": "GAVE",
      "event_specific_slots": {
        "giver": "B4",
        "giver_standing": "KING",
        "gift": "HOUSE_OF_HAMAN",
        "taken_from": "B3",
        "enemy_standing": "ENEMY_OF_JEWS",
        "imperilled_people": "B17",
        "given_to": "B2",
        "given_to_standing": "QUEEN",
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
      "verse_anchor": "8:1",
      "proposition_kind": "ARRIVED_AT",
      "event_specific_slots": {
        "comer": "B1",
        "came_before": "B4",
        "reason": "RELATION_TOLD",
        "teller": "B2",
        "told_content": "THE_KINSHIP_RELATION"
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
      "verse_anchor": "8:2",
      "proposition_kind": "REMOVED",
      "event_specific_slots": {
        "remover": "B4",
        "removed": "TH_SIGNET_RING",
        "removed_from_self": "OWN_SIGNET",
        "taken_earlier_from": "B3"
      },
      "inter_proposition_links": {
        "caused_by": "P1",
        "forward_link_to": "P4"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P4",
      "scene_link": "S1",
      "verse_anchor": "8:2",
      "proposition_kind": "GAVE",
      "event_specific_slots": {
        "giver": "B4",
        "gift": "TH_SIGNET_RING",
        "given_to": "B1"
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
      "scene_link": "S1",
      "verse_anchor": "8:2",
      "proposition_kind": "APPOINTED",
      "event_specific_slots": {
        "setter": "B2",
        "set_one": "B1",
        "set_over": "HOUSE_OF_HAMAN",
        "taken_from": "B3"
      },
      "inter_proposition_links": {
        "caused_by": "P1"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P6",
      "scene_link": "S2",
      "verse_anchor": "8:3",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "speaker": "B2",
        "spoke_before": "B4",
        "iteration": "ONCE_MORE"
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
      "scene_link": "S2",
      "verse_anchor": "8:3",
      "proposition_kind": "PROSTRATED",
      "event_specific_slots": {
        "faller": "B2",
        "fell_before": "FEET",
        "feet_of": "B4"
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
      "verse_anchor": "8:3",
      "proposition_kind": "WEPT",
      "event_specific_slots": {
        "weeper": "B2"
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
      "scene_link": "S2",
      "verse_anchor": "8:3",
      "proposition_kind": "APPEAL",
      "event_specific_slots": {
        "pleader": "B2",
        "pleaded_with": "B4",
        "pleaded_for": "PUTTING_AWAY",
        "put_away_target": "EVIL",
        "evil_of": "B3",
        "evil_doer_standing": "AGAGITE",
        "and_also": "PLAN",
        "plan_of": "B3",
        "plan_against": "B17"
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
      "verse_anchor": "8:4",
      "proposition_kind": "GRANTED",
      "event_specific_slots": {
        "holder_out": "B4",
        "held_out": "TH_SCEPTER",
        "scepter_material": "GOLD",
        "held_out_to": "B2"
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
      "scene_link": "S2",
      "verse_anchor": "8:4",
      "proposition_kind": "ROSE",
      "event_specific_slots": {
        "riser": "B2"
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
      "scene_link": "S2",
      "verse_anchor": "8:4",
      "proposition_kind": "APPROACHED",
      "event_specific_slots": {
        "stander": "B2",
        "stood_before": "B4"
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
      "verse_anchor": "8:5",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "speaker": "B2",
        "addressee": "B4",
        "condition_components": [
          {
            "court_formula": "KING_PLEASED",
            "pleased_one": "B4",
            "speech_act": "STATES_HOPED_FOR_CONDITION"
          },
          {
            "court_formula": "FAVOUR_FOUND",
            "favour_found_by": "B2",
            "favour_before": "B4",
            "speech_act": "STATES_HOPED_FOR_CONDITION"
          },
          {
            "court_formula": "MATTER_RIGHT",
            "right_before": "B4",
            "speech_act": "STATES_HOPED_FOR_CONDITION"
          },
          {
            "court_formula": "PLEASING_IN_EYES",
            "pleasing_one": "B2",
            "pleasing_to": "B4",
            "speech_act": "STATES_HOPED_FOR_CONDITION"
          }
        ]
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
      "verse_anchor": "8:5",
      "proposition_kind": "APPEAL",
      "event_specific_slots": {
        "voiced_within": "P13",
        "petitioner": "B2",
        "petitioned": "B4",
        "requested_act": "A_WRITING",
        "writing_purpose": "TURNING_BACK",
        "turned_back": "TH_EDICT",
        "edict_as": "PLAN",
        "plan_of": "B3",
        "plan_author_father": "HAMMEDATHA",
        "plan_author_standing": "AGAGITE",
        "edict_purpose": "DESTROYING",
        "destroy_target": "B17",
        "destroy_scope": "PROVINCES",
        "scope_extent": "ALL",
        "provinces_of": "B4",
        "speech_act": "PETITIONS_FOR_GRANT"
      },
      "inter_proposition_links": {
        "condition_of": "P13",
        "forward_link_to": "P15"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P15",
      "scene_link": "S2",
      "verse_anchor": "8:6",
      "proposition_kind": "ASKED",
      "event_specific_slots": {
        "voiced_within": "P13",
        "asker": "B2",
        "question": "HOW",
        "to_what": "TO_BEAR",
        "borne_sight": "EVIL",
        "evil_finding": "PEOPLE",
        "people_of": "B17",
        "speech_act": "ASKS_DELIBERATIVE_QUESTION"
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
      "verse_anchor": "8:6",
      "proposition_kind": "ASKED",
      "event_specific_slots": {
        "voiced_within": "P13",
        "asker": "B2",
        "question": "HOW",
        "to_what": "TO_BEAR",
        "borne_sight": "DESTRUCTION",
        "destruction_of": "KINDRED",
        "kindred_of": "B2",
        "speech_act": "ASKS_DELIBERATIVE_QUESTION"
      },
      "inter_proposition_links": {
        "caused_by": "P15"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P17",
      "scene_link": "S3",
      "verse_anchor": "8:7",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "speaker": "B4",
        "speaker_named": "AHASUERUS",
        "addressee": "B2",
        "addressee_standing": "QUEEN",
        "co_addressee": "B1",
        "co_addressee_standing": "THE_JEW"
      },
      "inter_proposition_links": {
        "caused_by": "P16",
        "forward_link_to": "P18"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P18",
      "scene_link": "S3",
      "verse_anchor": "8:7",
      "proposition_kind": "GAVE",
      "status": "RECALLED",
      "event_specific_slots": {
        "voiced_within": "P17",
        "giver": "B4",
        "gift": "HOUSE_OF_HAMAN",
        "taken_from": "B3",
        "given_to": "B2",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P17",
        "forward_link_to": "P19"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P19",
      "scene_link": "S3",
      "verse_anchor": "8:7",
      "proposition_kind": "STRUCK",
      "status": "RECALLED",
      "event_specific_slots": {
        "voiced_within": "P17",
        "hanged_one": "B3",
        "hanged_on": "TH_GALLOWS",
        "reason": "REACHING",
        "reaching_member": "HAND",
        "hand_of": "B3",
        "reached_against": "B17",
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
      "scene_link": "S3",
      "verse_anchor": "8:8",
      "proposition_kind": "DECLARED",
      "status": "PERMITTED",
      "event_specific_slots": {
        "voiced_within": "P17",
        "grantor": "B4",
        "writers": ["B2", "B1"],
        "write_concerning": "B17",
        "write_content": "WHAT_SEEMS_GOOD",
        "good_in_eyes_of": "WRITERS",
        "in_name_of": "B4",
        "speech_act": "PRESCRIBES_AS_LAW"
      },
      "inter_proposition_links": {
        "caused_by": "P17",
        "forward_link_to": "P21"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P21",
      "scene_link": "S3",
      "verse_anchor": "8:8",
      "proposition_kind": "DECLARED",
      "status": "PERMITTED",
      "event_specific_slots": {
        "voiced_within": "P17",
        "grantor": "B4",
        "sealers": ["B2", "B1"],
        "seal_with": "TH_SIGNET_RING",
        "ring_of": "B4",
        "speech_act": "PRESCRIBES_AS_LAW"
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
      "scene_link": "S3",
      "verse_anchor": "8:8b",
      "proposition_kind": "DECLARED",
      "status": "NORM",
      "event_specific_slots": {
        "voiced_within": "P17",
        "prescriber": "B4",
        "stated_as": "REASON_FOR_GRANT",
        "rule_concerning": "A_WRITING",
        "written_in_name_of": "B4",
        "sealed_with": "TH_SIGNET_RING",
        "ring_of": "B4",
        "revocability": "NONE",
        "speech_act": "PRESCRIBES_AS_LAW"
      },
      "inter_proposition_links": {
        "caused_by": "P20",
        "paired_with": "P21"
      },
      "cb_flags": [],
      "figure_flags": []
    }
  ]
}
```

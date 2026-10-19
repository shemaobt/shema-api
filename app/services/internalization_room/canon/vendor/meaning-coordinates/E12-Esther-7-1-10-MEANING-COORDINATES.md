---
type: "sta-meaning-coordinates"
pericope: "E12"
pericope-title: "The second banquet: Esther names the adversary, and Haman hangs on his own gallows"
source-meaning-map: [[E12-Esther-7-1-10]]
status: "valid"
pilot: "pilot-2"
---

# E12 — Esther 7:1–10 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "esther_pericope_12_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Esther 7:1-10",
    "pericope_title": "The second banquet: Esther names the adversary, and Haman hangs on his own gallows",
    "book_context_ref": "esther_pilot_BCD_v0_1",
    "source_meaning_map_ref": "E12-Esther-7-1-10",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "Whole passage stays INFORMAL_CASUAL — a storyteller's account of the trap closing, carried mostly in quoted speech (the king's repeated offer, Esther's plea, the king's demand, the naming, the death-order). None of it is a written/sealed edict being read out; even the king's final 'Hang him on it' (P15) is a spoken verdict in the room, not a law of the Medes and Persians — so NO FORMAL_OFFICIAL override (Mapper's note 1, surfaced for Marcia). No COMMUNITY_MEMORY framing-lift: this is mid-book, deep in the action.",
      "scene_level": null,
      "moment_level": null
    }
  },
  "level_1": {
    "arc_elements": [
      "FAVOR_GRANTED",
      "PLEA_FOR_LIFE",
      "ADVERSARY_NAMED",
      "WRATH_AND_FALL",
      "GREAT_REVERSAL"
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
      "MEASURED",
      "TAUT",
      "HEATED",
      "IRONIC",
      "DECISIVE"
    ],
    "pace_elements": [
      "DELIBERATE",
      "ACCELERATES",
      "SETTLES"
    ],
    "communicative_function_elements": [
      "REACTIVATES",
      "STATES_DANGER",
      "TURNS_ON_A_NAME",
      "REVERSES",
      "CLOSES"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "7:1-2",
      "scene_kind": "MEAL_SCENE",
      "scene_communicative_purpose": "Sets the second banquet and the king's renewed, open-ended offer — the door through which Esther will finally speak.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT",
            "referential_form": "THE_KING"
          },
          {
            "being_id": "B3",
            "role_in_scene": "HONORED_ONE",
            "presence": "PRESENT"
          },
          {
            "being_id": "B2",
            "role_in_scene": "QUEEN",
            "presence": "PRESENT",
            "referential_form": "ESTHER_THE_QUEEN"
          }
        ]
      },
      "places_in_scene": {
        "_note": "Susa (PL1) is the inferred setting but is NOT named in this pericope's Hebrew, and PL1.appears_in does not list E12 (Mapper's note + modality-spec compile risk). Kept as descriptive setting, not a confirmed registry place, pending Marcia's appears_in ruling. The banquet venue rides as bare-atom institution content (banquet_named:MISHTEH) inside the propositions.",
        "entries": null
      },
      "objects_in_scene": {
        "_note": "The royal wine-banquet (I1 / mishteh ha-yayin, a registered INSTITUTION) is the table where Esther speaks; the MEANING_COORDINATES scene containers have no institution slot and object_id excludes I-codes, so it rides as bare-atom content (banquet_named:MISHTEH) in the propositions. 'Up to half the kingdom' is the king's set, formulaic measure of his offer — descriptive scene content, not a registry object.",
        "entries": null
      },
      "times_in_scene": {
        "_note": "'The second day' (the day of the renewed offer) is content carried inside Prop 2, not a registry calendar time; no TM_ code.",
        "entries": null
      },
      "significant_absence": "The king still does not know, and is not told here, that the man drinking beside him is the enemy of the woman across the table — or that she is one of the people his own decree has condemned. And no god is invoked over the feast; the deliverance about to begin is set up with no word of the One the book never names."
    },
    {
      "scene_id": "S2",
      "verse_range": "7:3-4",
      "scene_kind": "APPEAL_SCENE",
      "scene_communicative_purpose": "Delivers Esther's plea — risking herself to set the danger to her people before the king, still without naming the man behind it.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B2",
            "role_in_scene": "SUPPLIANT",
            "presence": "PRESENT",
            "referential_form": "ESTHER_THE_QUEEN"
          },
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT",
            "referential_form": "THE_KING"
          }
        ]
      },
      "places_in_scene": {
        "entries": []
      },
      "objects_in_scene": {
        "_note": "'Sold to be destroyed, killed, and wiped out' (the threefold annihilation formula echoing the decree's wording) is the heart of the plea, carried as bare-atom content inside Prop 4 (preserve_form), not a registry object.",
        "entries": null
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame; the plea follows directly on the king's offer.",
        "entries": null
      },
      "significant_absence": "Esther names the threat but holds back the name of its author to the very last — and she still does not say outright that she herself is a Jew; she lets \"my people\" carry it. No appeal to God is made; the plea rests entirely on the king's favour and on what the king stands to lose."
    },
    {
      "scene_id": "S3",
      "verse_range": "7:5-6",
      "scene_kind": "EXPOSURE_SCENE",
      "scene_communicative_purpose": "Delivers the naming — the single word that turns the accuser into the accused and exposes Haman to the king's wrath.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "ACCUSER",
            "presence": "PRESENT",
            "referential_form": "KING_AHASUERUS"
          },
          {
            "being_id": "B2",
            "role_in_scene": "ACCUSER",
            "presence": "PRESENT",
            "referential_form": "ESTHER_THE_QUEEN"
          },
          {
            "being_id": "B3",
            "role_in_scene": "ADVERSARY",
            "presence": "PRESENT"
          }
        ]
      },
      "places_in_scene": {
        "entries": []
      },
      "objects_in_scene": {
        "entries": []
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame; the demand and answer follow at once.",
        "entries": null
      },
      "significant_absence": "The king asks \"who\" as though the deed were a stranger's, never suspecting his own hand in it through the decree he sold. Nothing is said of God's timing in bringing the enemy to this exact table; the turn is left to read as the bare collision of a question and a name."
    },
    {
      "scene_id": "S4",
      "verse_range": "7:7-8",
      "scene_kind": "REVERSAL_SCENE",
      "scene_communicative_purpose": "Shows the king's wrath breaking out, Haman's desperate fall, and the king's furious misreading of it as assault — sealing Haman's doom.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT",
            "referential_form": "THE_KING"
          },
          {
            "being_id": "B3",
            "role_in_scene": "SUPPLIANT",
            "presence": "PRESENT"
          },
          {
            "being_id": "B2",
            "role_in_scene": "QUEEN",
            "presence": "PRESENT",
            "referential_form": "ESTHER_THE_QUEEN"
          }
        ]
      },
      "places_in_scene": {
        "_note": "Three sub-locations of the palace are carried as descriptive scene venues (no registry place code, per map convention): the palace garden (ginnat ha-bitan — Mapper's note 4 asks whether it earns a PL-code since it recurs in E01), the house of the wine-banquet (the feast-room), and Esther's couch (ha-mittah — Mapper's note 5 asks whether the couch earns a TH-code since the king's misreading turns on it). All ride as bare-atom content in the propositions.",
        "entries": null
      },
      "objects_in_scene": {
        "_note": "'They covered Haman's face' — the sign that the condemned man is now a dead man — is carried as bare-atom content inside Prop 13, not a registry object.",
        "entries": null
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame; the wrath, the exit, the fall, and the return run on directly.",
        "entries": null
      },
      "significant_absence": "The king never learns, and is never told, that Haman's \"attack\" was a plea for mercy; the misreading stands, and the story lets it. And the swing of fortune — the enemy collapsing on the very couch of the woman he meant to destroy — comes with no word of who arranged it."
    },
    {
      "scene_id": "S5",
      "verse_range": "7:9-10",
      "scene_kind": "REVERSAL_SCENE",
      "scene_communicative_purpose": "Closes the reversal: the gallows built for Mordecai claims Haman, the king's order is carried out, and his anger settles.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B13",
            "role_in_scene": "EUNUCH_WHO_POINTS_THE_GALLOWS",
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
            "role_in_scene": "ADVERSARY",
            "presence": "PRESENT_BECOMES_DECEASED"
          },
          {
            "being_id": "B1",
            "role_in_scene": "THREATENED_PEOPLE",
            "presence": "REFERENCED",
            "referential_form": "MORDECAI_WHO_SPOKE_GOOD_FOR_THE_KING"
          }
        ]
      },
      "places_in_scene": {
        "_note": "'Haman's house' (bet Haman — where the gallows stands) is a descriptive sub-location, not a registry place; it rides as bare-atom content inside Prop 14.",
        "entries": null
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "TH_GALLOWS"
          }
        ]
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame; the pointing-out, the order, and the hanging follow at once.",
        "entries": null
      },
      "significant_absence": "No trial, no defence, no appeal — the verdict and the execution are immediate. And the perfect fit of it — the gallows raised for the rescuer falling to the schemer — is left to stand on its own, with no word naming the hand behind the timing."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "7:1",
      "proposition_kind": "ARRIVED_AT",
      "event_specific_slots": {
        "comer": "B4",
        "accompanying": "B3",
        "activity": "DRINKING",
        "host": "B2",
        "host_standing": "QUEEN",
        "banquet_named": "MISHTEH"
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
      "verse_anchor": "7:2",
      "proposition_kind": "PROPOSED",
      "event_specific_slots": {
        "speaker": "B4",
        "addressee": "B2",
        "occasion_day": "SECOND_DAY",
        "banquet_named": "MISHTEH",
        "asked_for": "REQUEST",
        "request_of": "B2",
        "speech_act": "ASKS_INFORMATION_SEEKING_QUESTION",
        "offer_components": [
          {
            "granted_thing": "REQUEST",
            "extent_offered": "THE_KINGDOM",
            "extent_fraction": "HALF",
            "extent_bound": "UP_TO",
            "status": "PERMITTED",
            "speech_act": "GRANTS_PERMISSION_TO_DO"
          },
          {
            "promised_action": "DOING",
            "status": "PERMITTED",
            "speech_act": "GRANTS_PERMISSION_TO_DO"
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
      "scene_link": "S2",
      "verse_anchor": "7:3",
      "proposition_kind": "APPEAL",
      "event_specific_slots": {
        "petitioner": "B2",
        "petitioner_standing": "QUEEN",
        "petitioned_one": "B4",
        "petition_components": [
          {
            "sought_grant": "A_LIFE",
            "for_whom": "B2",
            "as_what": "REQUEST",
            "speech_act": "PETITIONS_FOR_GRANT"
          },
          {
            "sought_grant": "A_PEOPLE",
            "for_whom": "HER_PEOPLE",
            "as_what": "PETITION",
            "speech_act": "PETITIONS_FOR_GRANT"
          }
        ]
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
      "scene_link": "S2",
      "verse_anchor": "7:4",
      "proposition_kind": "APPEAL",
      "event_specific_slots": {
        "voiced_within": "P3",
        "stater": "B2",
        "grounds_components": [
          {
            "sold_party": ["B2", "HER_PEOPLE"],
            "sold_for": ["DESTRUCTION", "KILLING", "PERISHING"],
            "preserve_form": true,
            "status": "RECALLED",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "hypothetical_sold_as": ["SLAVES", "MAIDSERVANTS"],
            "hypothetical_response": "KEEPING_SILENT",
            "silent_one": "B2",
            "status": "COUNTERFACTUAL",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "reason_not_silent": "LOSS",
            "loss_borne_by": "B4",
            "beyond_worth_of": "AN_ADVERSARY",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "content_of": "P3"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P5",
      "scene_link": "S3",
      "verse_anchor": "7:5",
      "proposition_kind": "INTERROGATED",
      "event_specific_slots": {
        "speaker": "B4",
        "addressee": "B2",
        "addressee_standing": "QUEEN",
        "asked_who": "A_MAN",
        "asked_where": "HIS_PLACE",
        "filled_by": "A_HEART",
        "to_do": "SUCH_A_THING",
        "speech_act": "ASKS_INFORMATION_SEEKING_QUESTION"
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
      "scene_link": "S3",
      "verse_anchor": "7:6",
      "proposition_kind": "IDENTIFIED",
      "event_specific_slots": {
        "speaker": "B2",
        "named_one": "B3",
        "named_as": ["AN_ADVERSARY", "AN_ENEMY"],
        "character": "WICKED",
        "speech_act": "ALLEGES_AGAINST"
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
      "verse_anchor": "7:6",
      "proposition_kind": "FEARED",
      "event_specific_slots": {
        "terrified_one": "B3",
        "before_whom": ["B4", "B2"]
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
      "scene_link": "S4",
      "verse_anchor": "7:7",
      "proposition_kind": "ANGER_KINDLED",
      "event_specific_slots": {
        "riser": "B4",
        "in_what": "WRATH",
        "from_what": "MISHTEH",
        "to_where": "PALACE_GARDEN"
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
      "verse_anchor": "7:7",
      "proposition_kind": "APPEAL",
      "event_specific_slots": {
        "stander": "B3",
        "begging_for": "A_LIFE",
        "life_of": "B3",
        "begged_from": "B2",
        "begged_from_standing": "QUEEN",
        "motive": "A_SEEING",
        "seen_thing": "A_DOOM",
        "doom_settled_by": "B4"
      },
      "inter_proposition_links": {
        "caused_by": "P8",
        "purpose_of": "P9",
        "forward_link_to": "P10"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P10",
      "scene_link": "S4",
      "verse_anchor": "7:8",
      "proposition_kind": "RETURNED",
      "event_specific_slots": {
        "returner": "B4",
        "from_where": "PALACE_GARDEN",
        "to_where": "MISHTEH"
      },
      "inter_proposition_links": {
        "caused_by": "P8",
        "forward_link_to": "P11"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P11",
      "scene_link": "S4",
      "verse_anchor": "7:8",
      "proposition_kind": "PROSTRATED",
      "event_specific_slots": {
        "faller": "B3",
        "onto_what": "A_COUCH",
        "couch_of": "B2"
      },
      "inter_proposition_links": {
        "caused_by": "P9",
        "forward_link_to": "P12"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P12",
      "scene_link": "S4",
      "verse_anchor": "7:8",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "speaker": "B4",
        "alleged_act": "AN_ASSAULT",
        "alleged_against": "B2",
        "alleged_against_standing": "QUEEN",
        "where": "THE_HOUSE",
        "in_whose_presence": "B4",
        "construal_marker": "KINGS_MISREADING",
        "speech_act": "ALLEGES_AGAINST"
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
      "scene_link": "S4",
      "verse_anchor": "7:8",
      "proposition_kind": "TOOK",
      "event_specific_slots": {
        "covered_part": "A_FACE",
        "covered_party": "B3",
        "caused_by_word": "A_WORD",
        "word_from": "A_MOUTH",
        "mouth_of": "B4"
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
      "verse_anchor": "7:9",
      "proposition_kind": "IDENTIFIED",
      "event_specific_slots": {
        "speaker": "B13",
        "speaker_standing": "EUNUCH",
        "before_whom": "B4",
        "pointed_thing": "TH_GALLOWS",
        "gallows_height": "FIFTY_CUBITS",
        "made_by": "B3",
        "made_for": "B1",
        "intended_one_merit": "SPOKE_GOOD",
        "spoke_good_for": "B4",
        "standing_at": "HAMANS_HOUSE",
        "speech_act": "ADVISES_COURSE_OF_ACTION"
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
      "verse_anchor": "7:9",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "speaker": "B4",
        "ordered_act": "HANGING",
        "hanged_one": "B3",
        "on_what": "TH_GALLOWS",
        "speech_act": "DIRECTS_HEARER_TO_DO"
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
      "scene_link": "S5",
      "verse_anchor": "7:10",
      "proposition_kind": "STRUCK",
      "event_specific_slots": {
        "hanged_one": "B3",
        "on_what": "TH_GALLOWS",
        "prepared_by": "B3",
        "prepared_for": "B1"
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
      "scene_link": "S5",
      "verse_anchor": "7:10",
      "proposition_kind": "WRATH_SUBSIDED",
      "event_specific_slots": {
        "subsided_thing": "WRATH",
        "wrath_of": "B4"
      },
      "inter_proposition_links": {
        "caused_by": "P16"
      },
      "cb_flags": [],
      "figure_flags": []
    }
  ]
}
```

---
type: "sta-meaning-coordinates"
pericope: "E08"
pericope-title: "Mordecai mourns at the gate; Esther sends to learn the matter, and is charged to plead with the king"
source-meaning-map: [[E08-Esther-4-1-8]]
status: "valid"
pilot: "pilot-2"
---

# E08 — Esther 4:1–8 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "esther_pericope_08_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Esther 4:1-8",
    "pericope_title": "Mordecai mourns at the gate; Esther sends to learn the matter, and is charged to plead with the king",
    "book_context_ref": "esther_pilot_BCD_v0_1",
    "source_meaning_map_ref": "E08-Esther-4-1-8",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "Whole passage stays INFORMAL_CASUAL — the plain voice of a storyteller reporting grief, errands, and a relayed message. The decree (the dat) is pervasive — learned, mourned, physically handed over — but it is only ever referred to, never voiced: no line of the edict's own wording is quoted or read out, so no FORMAL_OFFICIAL moment-override (Mapper's note 1, surfaced for Marcia). No COMMUNITY_MEMORY framing-lift: this is mid-book, deep in the action, with no 'in the days of' narrator-frame.",
      "scene_level": null,
      "moment_level": null
    }
  },
  "level_1": {
    "arc_elements": [
      "AFFLICTION_LEARNED",
      "PUBLIC_LAMENT",
      "SHARED_LAMENT",
      "NEWS_RECEPTION",
      "CHANNEL_OPENED",
      "ACCUSATION_LAID"
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
      "RAW",
      "WEIGHTED",
      "ECONOMICAL",
      "URGENT",
      "RISING"
    ],
    "pace_elements": [
      "STEADY",
      "WIDENS",
      "BRISK"
    ],
    "communicative_function_elements": [
      "PUBLISHES",
      "ADVANCES",
      "INFORMS_THE_QUEEN",
      "OPENS",
      "ACCUSES"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "4:1-2",
      "scene_kind": "LAMENT_SCENE",
      "scene_communicative_purpose": "Shows the decree's weight landing first on Mordecai, whose open mourning is carried into the city but stopped at the palace threshold.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B1",
            "role_in_scene": "COMPLAINANT",
            "presence": "PRESENT"
          }
        ]
      },
      "places_in_scene": {
        "_note": "The midst of the city (the open streets Mordecai cries through) and the king's gate (PL8 — the threshold his mourning cannot cross) are the two settings here. PL8 is the registered king's gate; the city's open square is a sub-setting of PL1/Susa carried as bare-atom content in the propositions (THE_CITY), not a registry place.",
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
        "_note": "Sackcloth-and-ashes and the torn clothes are the mourning-garb, carried as bare-atom content in the propositions (SACKCLOTH / ASHES / CLOTHES), not registry objects. The decree (I2 / dat, a registered INSTITUTION) is the unseen cause Mordecai has learned; the MEANING_COORDINATES scene containers have no institution slot and object_id excludes I-codes, so the decree rides as bare-atom content (WHAT_HAD_BEEN_DONE). No persistent registry object in this scene.",
        "entries": null
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; it follows directly on the sealing of the decree in the previous pericope.",
        "entries": null
      },
      "significant_absence": "In a scene built entirely of the gestures of crying out — torn clothes, sackcloth, ashes, a great and bitter cry — God is never named, and Mordecai's cry is addressed to no one we are told of. The very acts that elsewhere mean \"appealing to the LORD\" here rise toward a silence the book never fills."
    },
    {
      "scene_id": "S2",
      "verse_range": "4:3",
      "scene_kind": "LAMENT_SCENE",
      "scene_communicative_purpose": "Widens the grief from one man to the whole people, showing the decree's reach measured in mourning.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B17",
            "role_in_scene": "DELIVERED_PEOPLE",
            "presence": "PRESENT_COLLECTIVE"
          }
        ]
      },
      "places_in_scene": {
        "_note": "The provinces (the 127, I5 — a registered INSTITUTION) are the empire-wide span the decree reaches; the MEANING_COORDINATES scene containers have no institution slot and object_id/place_id exclude I-codes, so the realm-span rides as bare-atom content in Prop 8 (EVERY_PROVINCE). No registry place code in this scene.",
        "entries": null
      },
      "objects_in_scene": {
        "_note": "The decree (I2 / dat) reaching each province, and the mourning-acts (fasting, weeping, wailing) and sackcloth-and-ashes, are carried as bare-atom content in the propositions, not registry objects. No persistent registry object in this scene.",
        "entries": null
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; the provincial mourning runs concurrently with Mordecai's, as the decree reaches each place.",
        "entries": null
      },
      "significant_absence": "A whole people fasts and mourns across an empire — and no prayer, no LORD, no God is named over any of it. The fast is kept; the One a fast is kept toward is left unsaid."
    },
    {
      "scene_id": "S3",
      "verse_range": "4:4",
      "scene_kind": "GRIEF_REACHES_THE_QUEEN_SCENE",
      "scene_communicative_purpose": "Brings the grief to Esther, and shows her first response — to cover it, not yet understand it — meeting Mordecai's refusal.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B2",
            "role_in_scene": "QUEEN",
            "presence": "PRESENT"
          },
          {
            "being_id": "B1",
            "role_in_scene": "COMPLAINANT",
            "presence": "PRESENT"
          }
        ]
      },
      "places_in_scene": {
        "_note": "No registry place named in this scene; the action is the relay of word and garments between Esther inside the palace and Mordecai outside.",
        "entries": null
      },
      "objects_in_scene": {
        "_note": "The garments Esther sends and the sackcloth Mordecai keeps on are carried as bare-atom content in the propositions (GARMENTS / SACKCLOTH), not registry objects. No persistent registry object in this scene.",
        "entries": null
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; it follows on the mourning of v.1-3.",
        "entries": null
      },
      "significant_absence": "Esther is shaken to the core, yet the narrator tells us nothing of what she fears or thinks, and names no God she turns to. Her distress is reported from the outside only — and her first instinct is to clothe over the grief rather than ask what it means."
    },
    {
      "scene_id": "S4",
      "verse_range": "4:5-8",
      "scene_kind": "ACCOUNT_AND_CHARGE_AT_THE_SQUARE_SCENE",
      "scene_communicative_purpose": "Opens the channel of rescue: Esther sends to learn, Mordecai hands over the whole truth and the proof, and lays on her the charge to go to the king for her people.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B2",
            "role_in_scene": "SENDER",
            "presence": "PRESENT"
          },
          {
            "being_id": "B8",
            "role_in_scene": "COURIERS",
            "presence": "PRESENT",
            "referential_form": "THE_KINGS_EUNUCH_HATHACH"
          },
          {
            "being_id": "B1",
            "role_in_scene": "ACCOUNT_GIVER",
            "presence": "PRESENT"
          },
          {
            "being_id": "B3",
            "role_in_scene": "ACCUSER",
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
        "_note": "The open square before the king's gate (where Hathach finds Mordecai) is a sub-setting carried as bare-atom content in Prop 17 (THE_SQUARE / BEFORE_THE_GATE); the king's gate it stands before is the registered PL8. Susa (PL1) is referenced as the place where the decree was issued.",
        "entries": [
          {
            "place_id": "PL8"
          },
          {
            "place_id": "PL1"
          }
        ]
      },
      "objects_in_scene": {
        "_note": "The written copy of the decree Mordecai hands over (the dat / I2, a registered INSTITUTION) rides as bare-atom content in Prop 20 (A_COPY / THE_LAW); the MEANING_COORDINATES scene containers have no institution slot. The promised silver-sum and the charge-to-plead are bare-atom content in the propositions, not registry objects. No persistent registry object in this scene.",
        "entries": null
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; the errands run on directly from Esther's hearing in v.4.",
        "entries": null
      },
      "significant_absence": "Mordecai gives Esther every reason and every proof — the sum, the writing, the place — yet names no God, makes no appeal to heaven, and offers no promise of help beyond Esther herself. The charge is to go to the king; the only one named who could save is a man on a throne, and the One the book will never name stays absent even from the plea."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "4:1",
      "proposition_kind": "HEARD_REPORT",
      "event_specific_slots": {
        "learner": "B1",
        "learned_extent": "ALL",
        "learned_matter": "WHAT_WAS_DONE"
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
      "verse_anchor": "4:1",
      "proposition_kind": "LAMENT",
      "event_specific_slots": {
        "tearer": "B1",
        "torn_thing": "CLOTHES",
        "torn_garment_of": "B1"
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
      "verse_anchor": "4:1",
      "proposition_kind": "LAMENT",
      "event_specific_slots": {
        "donner": "B1",
        "garb_worn": ["SACKCLOTH", "ASHES"]
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
      "verse_anchor": "4:1",
      "proposition_kind": "WENT_OUT",
      "event_specific_slots": {
        "goer": "B1",
        "destination": "THE_MIDST",
        "of_place": "THE_CITY"
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
      "verse_anchor": "4:1",
      "proposition_kind": "LAMENT",
      "event_specific_slots": {
        "crier": "B1",
        "cry_uttered": "A_CRY",
        "cry_quality": ["GREAT", "BITTER"]
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
      "verse_anchor": "4:2",
      "proposition_kind": "ARRIVED_AT",
      "event_specific_slots": {
        "comer": "B1",
        "reached_limit": "BEFORE_THE_GATE",
        "gate_of": "THE_KING"
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
      "verse_anchor": "4:2",
      "proposition_kind": "DECLARED",
      "status": "NORM",
      "event_specific_slots": {
        "barred_place": "BEFORE_THE_GATE",
        "gate_of": "THE_KING",
        "bound_party": "ANY",
        "forbidden_state": "CLOTHED_IN_SACKCLOTH",
        "forbidden_act": "PASSES_THROUGH"
      },
      "inter_proposition_links": {
        "caused_by": "P6"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P8",
      "scene_link": "S2",
      "verse_anchor": "4:3",
      "proposition_kind": "LAMENT",
      "event_specific_slots": {
        "mourning_quality": "GREAT",
        "mourners": "B17",
        "reach": "EVERY_PROVINCE",
        "reached_by": "THE_KINGS_WORD",
        "also_reached_by": "HIS_LAW"
      },
      "inter_proposition_links": {
        "forward_link_to": "P9"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P9",
      "scene_link": "S2",
      "verse_anchor": "4:3",
      "proposition_kind": "LAMENT",
      "event_specific_slots": {
        "mourners": "B17",
        "grief_acts": ["A_FAST", "WEEPING", "WAILING"]
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
      "verse_anchor": "4:3",
      "proposition_kind": "LAMENT",
      "event_specific_slots": {
        "liers_down": "THE_MANY",
        "lain_in": ["SACKCLOTH", "ASHES"]
      },
      "inter_proposition_links": {
        "caused_by": "P9"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P11",
      "scene_link": "S3",
      "verse_anchor": "4:4",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "tellers": ["ESTHERS_MAIDS", "HER_EUNUCHS"],
        "told_one": "B2"
      },
      "inter_proposition_links": {
        "forward_link_to": "P12"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P12",
      "scene_link": "S3",
      "verse_anchor": "4:4",
      "proposition_kind": "FEARED",
      "event_specific_slots": {
        "distressed_one": "B2",
        "degree": "VERY"
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
      "scene_link": "S3",
      "verse_anchor": "4:4",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "sender": "B2",
        "thing_sent": "GARMENTS",
        "purpose_components": [
          {
            "intended_act": "A_CLOTHING",
            "clothed_one": "B1"
          },
          {
            "intended_act": "A_REMOVING",
            "removed_thing": "SACKCLOTH",
            "sackcloth_of": "B1",
            "removed_from": "OFF_HIM"
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
      "scene_link": "S3",
      "verse_anchor": "4:4",
      "proposition_kind": "DECLINED",
      "event_specific_slots": {
        "refuser": "B1",
        "refused_thing": "GARMENTS"
      },
      "inter_proposition_links": {
        "caused_by": "P13"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P15",
      "scene_link": "S4",
      "verse_anchor": "4:5",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "caller": "B2",
        "called_one": "B8",
        "called_from": "THE_KINGS_EUNUCHS",
        "appointed_to": "AN_ATTENDING",
        "attended_one": "B2"
      },
      "inter_proposition_links": {
        "forward_link_to": "P16"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P16",
      "scene_link": "S4",
      "verse_anchor": "4:5",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "charger": "B2",
        "charged_messenger": "B8",
        "concerning": "B1",
        "charged_act": "A_LEARNING",
        "to_learn": ["WHAT", "WHY"],
        "speech_act": "DIRECTS_HEARER_TO_DO"
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
      "verse_anchor": "4:6",
      "proposition_kind": "WENT_OUT",
      "event_specific_slots": {
        "goer": "B8",
        "went_to": "B1",
        "destination": "THE_SQUARE",
        "square_of": "THE_CITY",
        "square_location": "BEFORE_THE_GATE",
        "gate_of": "THE_KING"
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
      "scene_link": "S4",
      "verse_anchor": "4:7",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "teller": "B1",
        "told_one": "B8",
        "told_extent": "ALL",
        "told_matter": "WHAT_BEFELL_HIM"
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
      "scene_link": "S4",
      "verse_anchor": "4:7",
      "proposition_kind": "HEARD_REPORT",
      "status": "RECALLED",
      "event_specific_slots": {
        "voiced_within": "P18",
        "reported_thing": "A_SUM",
        "of_metal": "SILVER",
        "promiser": "B3",
        "promised_destination": "TREASURIES",
        "treasuries_of": "THE_KING",
        "promised_against": "B17",
        "promised_end": "A_DESTROYING",
        "destroyed_party": "B17",
        "speech_act": "ALLEGES_AGAINST"
      },
      "inter_proposition_links": {
        "content_of": "P18",
        "forward_link_to": "P20"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P20",
      "scene_link": "S4",
      "verse_anchor": "4:8",
      "proposition_kind": "GAVE",
      "event_specific_slots": {
        "giver": "B1",
        "given_to": "B8",
        "thing_given": "A_COPY",
        "copy_of": "A_WRITING",
        "writing_of": "THE_LAW",
        "issued_at": "PL1",
        "decree_purpose": "A_DESTROYING",
        "destroyed_party": "B17",
        "purpose_status": "RECALLED"
      },
      "inter_proposition_links": {
        "caused_by": "P18",
        "forward_link_to": "P21"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P21",
      "scene_link": "S4",
      "verse_anchor": "4:8",
      "proposition_kind": "GIVEN_TO_SHOW_AND_MAKE_KNOWN",
      "event_specific_slots": {
        "shown_to": "B2",
        "further_act": "A_MAKING_KNOWN",
        "made_known_to": "B2"
      },
      "inter_proposition_links": {
        "purpose_of": "P20",
        "forward_link_to": "P22"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P22",
      "scene_link": "S4",
      "verse_anchor": "4:8",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "charger": "B1",
        "charged_one": "B2",
        "charge_components": [
          {
            "charged_act": "A_GOING_IN",
            "going_in_to": "THE_KING",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "charged_act": "A_BEGGING",
            "begged_one": "THE_KING",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          },
          {
            "charged_act": "A_PLEADING",
            "pleaded_before": "THE_KING",
            "on_behalf_of": "HER_PEOPLE",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          }
        ]
      },
      "inter_proposition_links": {
        "purpose_of": "P20"
      },
      "cb_flags": [],
      "figure_flags": []
    }
  ]
}
```

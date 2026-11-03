---
type: "sta-meaning-coordinates"
pericope: "E04"
pericope-title: "Mordecai and Hadassah: the orphan cousin is taken into the harem, wins favor, hides her people, and is crowned queen"
source-meaning-map: [[E04-Esther-2-5-18]]
status: "valid"
pilot: "pilot-2"
---

# E04 — Esther 2:5–18 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "esther_pericope_04_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",

  "header": {
    "bcv": "Esther 2:5-18",
    "pericope_title": "Mordecai and Hadassah: the orphan cousin is taken into the harem, wins favor, hides her people, and is crowned queen",
    "book_context_ref": "esther_pilot_BCD_v0_1",
    "source_meaning_map_ref": "E04-Esther-2-5-18",
    "source_language": "Biblical Hebrew"
  },

  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "No overrides. Mid-book pericope, so no COMMUNITY_MEMORY framing lift. No FORMAL_OFFICIAL moment-override: the two rule-references — 'the king's word and his law' (v.8) and 'the rule for the women' (v.12) — are the narrator reporting that an order/procedure existed and was heard, not the decree's own words being voiced, so the register stays INFORMAL_CASUAL throughout.",
      "scene_level": null,
      "moment_level": null
    }
  },

  "level_1": {
    "arc_elements": [
      "FOREIGN_RESIDENCE",
      "ORPHAN_WARDSHIP",
      "TAKEN_INTO_HAREM",
      "FAVOR_GRANTED",
      "SECRECY_INJUNCTION",
      "MARRIAGE_CONSUMMATED"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "PHYSICAL_LOCATION",
      "KINSHIP_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "TEMPORAL_CONTEXT",
      "HISTORICAL_ERA_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT"
    ],
    "tone_elements": [
      "RESTRAINED",
      "WATCHFUL",
      "ANTICIPATORY",
      "QUIETLY_ACCELERATING"
    ],
    "pace_elements": [
      "BRISK",
      "SLOWED",
      "ACCELERATES"
    ],
    "communicative_function_elements": [
      "INTRODUCES",
      "BINDS",
      "PLANTS",
      "WITHHOLDS",
      "ELEVATES"
    ]
  },

  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "2:5-7",
      "scene_kind": "NARRATOR_INTRODUCTION_SCENE",
      "scene_communicative_purpose": "Introduces Mordecai and Esther, binds them as guardian and orphan ward, and roots them in the exile of Judah — the two people and the buried Jewish identity the whole book will turn on.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B1",
            "role_in_scene": "GUARDIAN",
            "presence": "PRESENT",
            "referential_form": "MORDECAI_THE_JEW_A_BENJAMINITE"
          },
          {
            "being_id": "B2",
            "role_in_scene": "WARD",
            "presence": "PRESENT",
            "referential_form": "HADASSAH_THAT_IS_ESTHER"
          }
        ]
      },

      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL1"
          },
          {
            "place_id": "PL4"
          },
          {
            "place_id": "PL5"
          }
        ]
      },

      "objects_in_scene": {
        "_note": "The exiled king Jeconiah and his conqueror Nebuchadnezzar are unregistered referenced beings carried as L3 slots (P2.exiled_king, P2.deporting_king); the exile-company (ha-golah) is descriptive content carried in L3 (P2.exile_company), not a registry object.",
        "entries": null
      },

      "times_in_scene": {
        "_note": "No distinct dated time-setting; the exile-with-Jeconiah is a back-reference fixing Mordecai's origin, carried in L3 (P2) as content rather than a scene clock.",
        "entries": null
      },

      "significant_absence": "God is not named in the account of the exile — the deportation of Judah is told as bare history, with no mention of the One who, in the rest of Scripture, stands behind it. And Esther's Jewishness, though her guardian's is stated plainly, is not yet spoken of as something to be hidden — the silence around it is about to become deliberate."
    },

    {
      "scene_id": "S2",
      "verse_range": "2:8",
      "scene_kind": "INTAKE_SCENE",
      "scene_communicative_purpose": "Brings Esther across the threshold into the harem and into Hegai's keeping — the move that puts the hidden Jewish girl inside reach of the throne.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B2",
            "role_in_scene": "WARD",
            "presence": "PRESENT",
            "referential_form": "ESTHER"
          },
          {
            "being_id": "B7",
            "role_in_scene": "GUARDIAN",
            "presence": "PRESENT",
            "referential_form": "HEGAI"
          },
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "REFERENCED",
            "referential_form": "THE_KING"
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
        "_note": "The harem institution I4 (beit ha-nashim) is carried as an L3 slot (P4.keeping_institution), not an in-scene object. 'The king's house' is the palace venue, carried in L3 (P4.taken_to_house); 'the king's word and his law' is the reported royal order — descriptive content carried in L3 (P4.heard_word, P4.heard_law), not a voiced decree and not a registry object; the gathered 'many young women' are an unregistered referenced group carried in L3 (P4.gathered_women).",
        "entries": null
      },

      "times_in_scene": {
        "_note": "No distinct temporal frame; the taking follows directly on the going-out of the king's word.",
        "entries": null
      },

      "significant_absence": "Esther's being taken is told without resistance, grief, or comment — no word of how she or Mordecai felt about it. The narrator records the event flatly, withholding the inner life, and (as throughout) names no God shaping it."
    },

    {
      "scene_id": "S3",
      "verse_range": "2:9-11",
      "scene_kind": "FAVOR_AND_CONCEALMENT_SCENE",
      "scene_communicative_purpose": "Shows favor quietly accruing to Esther, the deliberate concealment of her people holding under Mordecai's charge, and the guardian's unbroken watch from outside — the book's hidden-identity signature set in motion.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B2",
            "role_in_scene": "WARD",
            "presence": "PRESENT",
            "referential_form": "THE_GIRL"
          },
          {
            "being_id": "B7",
            "role_in_scene": "GUARDIAN",
            "presence": "PRESENT",
            "referential_form": "HEGAI"
          },
          {
            "being_id": "B1",
            "role_in_scene": "GUARDIAN",
            "presence": "PRESENT",
            "referential_form": "MORDECAI"
          }
        ]
      },

      "places_in_scene": {
        "_note": "The harem institution I4 (beit ha-nashim) is carried as an L3 slot (P5.house_institution); 'the court of the house of the women' is the forecourt venue where Mordecai paces, carried in L3 (P7.paced_before).",
        "entries": []
      },

      "objects_in_scene": {
        "_note": "Esther's cosmetics and food-portions, and the seven maids given to her, are descriptive favor-content carried in L3 (P5.hurried_cosmetics, P5.hurried_portions, P5.given_maids); none is a registry object. The seven maids are an unregistered referenced group.",
        "entries": null
      },

      "times_in_scene": {
        "_note": "Mordecai's iterative daily watch ('day after day') is not a dated time but the customary rhythm of the pacing — carried in L3 as status:HABITUAL on P7, per the locked decode-to-habitual ruling. No registry time-code minted.",
        "entries": null
      },

      "significant_absence": "At the center of the scene is a thing not said: Esther does not tell her people or her kindred. The withholding is the point — a Jewish identity deliberately kept silent inside the palace, on her guardian's order. And the God who might be invoked over so charged a concealment is, as always in this book, unnamed."
    },

    {
      "scene_id": "S4",
      "verse_range": "2:12-14",
      "scene_kind": "INTAKE_SCENE",
      "scene_communicative_purpose": "Slows the story to lay out the harem's machinery — the year of preparation, the single night, the un-returning aftermath — so the reader feels the length and the stakes of the turn Esther is approaching.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "REFERENCED",
            "referential_form": "THE_KING"
          },
          {
            "being_id": "B9",
            "role_in_scene": "GUARDIAN",
            "presence": "REFERENCED",
            "referential_form": "SHAASHGAZ"
          }
        ]
      },

      "places_in_scene": {
        "_note": "The harem institution I4 (beit ha-nashim, the first house) is carried as an L3 slot (P9.from_house); 'the second house of the women' (the concubines' house) is a venue carried in L3 (P10.returned_to_house).",
        "entries": []
      },

      "objects_in_scene": {
        "_note": "'The rule for the women' (k'dat ha-nashim) is the reported standing procedure — carried in L3 as governing_rule on P8 under status:NORM, not a voiced decree and not a registry object; the myrrh-oil, perfumes, and women's cosmetics of the regimen are descriptive content carried in L3 (P8.regimen_substances).",
        "entries": null
      },

      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_TWELVE_MONTHS"
          }
        ]
      },

      "significant_absence": "The women themselves are given no names, no words, no choice — the scene is all procedure, and the persons inside it are silent. Nothing is said of consent or of feeling, and no God is named over a process that disposes of lives by rule."
    },

    {
      "scene_id": "S5",
      "verse_range": "2:15-18",
      "scene_kind": "MEAL_SCENE",
      "scene_communicative_purpose": "Brings Esther through her turn to the crown — loved, chosen over Vashti, made queen — and marks it with a banquet and empire-wide favor: the hidden Jewish girl now sits on the throne, the pivot the whole deliverance will later need.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B2",
            "role_in_scene": "QUEEN",
            "presence": "PRESENT",
            "referential_form": "ESTHER_DAUGHTER_OF_ABIHAIL"
          },
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT",
            "referential_form": "KING_AHASUERUS"
          },
          {
            "being_id": "B7",
            "role_in_scene": "GUARDIAN",
            "presence": "REFERENCED",
            "referential_form": "HEGAI"
          },
          {
            "being_id": "B5",
            "role_in_scene": "QUEEN",
            "presence": "REFERENCED",
            "referential_form": "VASHTI"
          }
        ]
      },

      "places_in_scene": {
        "_note": "'His royal house' is the palace venue into which Esther is taken, carried in L3 (P12.taken_to_house); the realm-span institution I5 (the 127 provinces) granted the remission is carried as an L3 slot (P14.remission_recipients), not an in-scene place.",
        "entries": [
          {
            "place_id": "PL1"
          }
        ]
      },

      "objects_in_scene": {
        "_note": "The royal crown set on Esther's head and the banquet institution I1 (mishteh) are carried as L3 slots (P13.crown_set, P14.banquet_named); the empire-wide remission and the gifts are descriptive content carried in L3 (P14.granted_remission, P14.given_gift). The crown is left descriptive per the map; the registry TH_ROYAL_CROWN coverage is surfaced as an authoring question.",
        "entries": null
      },

      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_TEBETH"
          }
        ]
      },

      "significant_absence": "At the height of the book's first great reversal — an orphan exile crowned queen of the empire — God is still not named. The crowning is told as the king's love and the king's choice alone, with no word of any providence behind it, the book's signature silence held even here."
    }
  ],

  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "2:5",
      "proposition_kind": "NARRATOR_INTRODUCES",
      "event_specific_slots": {
        "introduced_one": "B1",
        "introduced_as": "JEWISH",
        "dwelt_at": "PL1",
        "place_qualifier": "THE_CITADEL",
        "father_line": ["JAIR", "SHIMEI", "KISH"],
        "tribe": "BENJAMINITE"
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
      "verse_anchor": "2:6",
      "proposition_kind": "TIME_ANCHOR_ESTABLISHED",
      "status": "RECALLED",
      "event_specific_slots": {
        "exiled_one": "B1",
        "exiled_from": "PL4",
        "exile_company": "THE_DEPORTED_COMPANY",
        "exiled_king": "JECONIAH",
        "exiled_king_capacity": "KING_OF_JUDAH",
        "deporting_king": "NEBUCHADNEZZAR",
        "deporting_king_capacity": "KING_OF_BABYLON",
        "deported_from_realm": "PL5"
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
      "verse_anchor": "2:7",
      "proposition_kind": "BROUGHT_UP",
      "event_specific_slots": {
        "raiser": "B1",
        "raised_one": "B2",
        "raised_one_first_name": "HADASSAH",
        "raised_one_second_name": "ESTHER",
        "kinship": "HIS_UNCLES_DAUGHTER",
        "reason_first": "NO_FATHER",
        "reason_second": "NO_MOTHER",
        "appearance_form": "BEAUTIFUL_IN_FORM",
        "appearance_sight": "LOVELY",
        "taken_when": "AT_DEATH",
        "death_of": "HER_PARENTS",
        "taken_by": "B1",
        "taken_as": "A_DAUGHTER"
      },
      "inter_proposition_links": {
        "caused_by": "P2"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P4",
      "scene_link": "S2",
      "verse_anchor": "2:8",
      "proposition_kind": "TOOK",
      "event_specific_slots": {
        "heard_word": "THE_KINGS_WORD",
        "word_belonging": "B4",
        "heard_law": "HIS_LAW",
        "gathered_women": "MANY_YOUNG_WOMEN",
        "gathered_to": "PL1",
        "gather_place_qualifier": "THE_CITADEL",
        "gathered_into_hand_of": "B7",
        "taken_one": "B2",
        "taken_to_house": "THE_KINGS_HOUSE",
        "taken_into_hand_of": "B7",
        "keeper_capacity": "KEEPER",
        "keeper_of": "THE_WOMEN",
        "keeping_institution": "BEIT_HA_NASHIM"
      },
      "inter_proposition_links": {
        "forward_link_to": "P5"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P5",
      "scene_link": "S3",
      "verse_anchor": "2:9",
      "proposition_kind": "PERCEIVED",
      "event_specific_slots": {
        "pleasing_one": "B2",
        "pleased_one": "B7",
        "pleased_in": "HIS_EYES",
        "won_favor_before": "B7",
        "hurried_cosmetics": "HER_COSMETICS",
        "hurried_portions": "HER_PORTIONS",
        "given_maids": "SEVEN_MAIDS",
        "maids_from": "THE_KINGS_HOUSE",
        "moved_one": "B2",
        "moved_with": "HER_MAIDS",
        "moved_to": "THE_BEST_PLACE",
        "house_institution": "BEIT_HA_NASHIM"
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
      "verse_anchor": "2:10",
      "proposition_kind": "IDENTIFIED",
      "event_specific_slots": {
        "withholder": "B2",
        "untold_people": "HER_PEOPLE",
        "untold_kindred": "HER_KINDRED",
        "charge_components": [
          {
            "charger": "B1",
            "charged_one": "B2",
            "charged_content": "NOT_TO_TELL",
            "speech_act": "DIRECTS_HEARER_TO_DO"
          }
        ]
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
      "verse_anchor": "2:11",
      "proposition_kind": "GUARDIAN_PACED",
      "status": "HABITUAL",
      "event_specific_slots": {
        "pacer": "B1",
        "pacing_rhythm": "DAY_AFTER_DAY",
        "paced_before": "THE_COURT",
        "court_belonging": "BEIT_HA_NASHIM",
        "watched_one": "B2",
        "watched_for": "HER_WELFARE",
        "watched_outcome": "HER_OUTCOME"
      },
      "inter_proposition_links": {
        "purpose_of": "P6",
        "caused_by": "P6"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P8",
      "scene_link": "S4",
      "verse_anchor": "2:12",
      "proposition_kind": "INSTRUCTION",
      "status": "NORM",
      "event_specific_slots": {
        "regulated_party": "EACH_GIRL",
        "going_in_to": "B4",
        "governing_rule": "THE_WOMENS_RULE",
        "regimen_duration": "TM_TWELVE_MONTHS",
        "first_half": "SIX_MONTHS",
        "first_substance": "OIL_OF_MYRRH",
        "second_half": "SIX_MONTHS",
        "second_substances": ["PERFUMES", "WOMENS_COSMETICS"]
      },
      "inter_proposition_links": {
        "forward_link_to": "P9"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P9",
      "scene_link": "S4",
      "verse_anchor": "2:13",
      "proposition_kind": "GOING_IN_PROVISIONED",
      "status": "HABITUAL",
      "event_specific_slots": {
        "going_in_one": "THE_GIRL",
        "going_in_to": "B4",
        "granted_request": "WHATEVER_SHE_ASKED",
        "request_purpose": "TO_TAKE",
        "take_companion": "WITH_HER",
        "from_house": "BEIT_HA_NASHIM",
        "to_house": "THE_KINGS_HOUSE"
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
      "verse_anchor": "2:14",
      "proposition_kind": "NIGHT_THEN_NO_RETURN",
      "status": "HABITUAL",
      "event_specific_slots": {
        "went_in_when": "IN_THE_EVENING",
        "returned_when": "IN_THE_MORNING",
        "returned_to_house": "THE_WOMENS_HOUSE",
        "house_ordinal": "THE_SECOND",
        "returned_into_hand_of": "B9",
        "keeper_capacity": "OFFICER",
        "officer_of": "B4",
        "keeper_of": "THE_CONCUBINES",
        "return_outcome": "NO_RETURNING",
        "return_to": "B4",
        "return_components": [
          {
            "reprieve_condition_delight": "A_DELIGHT",
            "delight_holder": "B4",
            "reprieve_condition_summons": "A_SUMMONING",
            "summons_by": "NAME",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P9",
        "condition_of": "P9",
        "forward_link_to": "P11"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P11",
      "scene_link": "S5",
      "verse_anchor": "2:15",
      "proposition_kind": "ESTHERS_TURN_CAME",
      "event_specific_slots": {
        "turn_holder": "B2",
        "father": "ABIHAIL",
        "father_capacity": "AN_UNCLE",
        "uncle_of": "B1",
        "taken_by": "B1",
        "taken_as": "A_DAUGHTER",
        "going_in_to": "B4",
        "asked_for": "NOTHING",
        "advice_components": [
          {
            "advised_one": "B2",
            "advised_content": "WHAT_TO_TAKE",
            "adviser": "B7",
            "adviser_capacity": "OFFICER",
            "officer_of": "B4",
            "adviser_of": "THE_WOMEN",
            "speech_act": "ADVISES_COURSE_OF_ACTION"
          }
        ],
        "carried_favor": "FAVOR",
        "favor_before": "ALL_BEHOLDERS"
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
      "scene_link": "S5",
      "verse_anchor": "2:16",
      "proposition_kind": "TOOK",
      "event_specific_slots": {
        "taken_one": "B2",
        "taken_to": "B4",
        "taken_to_house": "HIS_ROYAL_HOUSE",
        "taken_in_month": "TM_TEBETH",
        "month_ordinal": "THE_TENTH",
        "reign_year": "A_SEVENTH_YEAR",
        "year_belonging": "HIS_REIGN"
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
      "verse_anchor": "2:17",
      "proposition_kind": "GAVE",
      "event_specific_slots": {
        "loving_king": "B4",
        "loved_one": "B2",
        "loved_above": "ALL_THE_WOMEN",
        "won_grace": "GRACE",
        "won_favor": "FAVOR",
        "favor_before": "B4",
        "favor_above": "ALL_THE_VIRGINS",
        "crown_set": "THE_ROYAL_CROWN",
        "crown_set_on": "HER_HEAD",
        "made_queen": "B2",
        "in_place_of": "B5"
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
      "verse_anchor": "2:18",
      "proposition_kind": "BANQUET_AND_REMISSION",
      "event_specific_slots": {
        "banquet_host": "B4",
        "banquet_named": "MISHTEH",
        "banquet_scale": "GREAT",
        "feasted_court": "HIS_PRINCES",
        "feasted_servants": "HIS_SERVANTS",
        "banquet_called": "ESTHERS_BANQUET",
        "granted_remission": "A_REMISSION",
        "remission_recipients": "THE_PROVINCES",
        "given_gift": "A_GIFT",
        "gift_measure": "THE_KINGS_LIBERALITY"
      },
      "inter_proposition_links": {
        "caused_by": "P13"
      },
      "cb_flags": [],
      "figure_flags": []
    }
  ]
}
```

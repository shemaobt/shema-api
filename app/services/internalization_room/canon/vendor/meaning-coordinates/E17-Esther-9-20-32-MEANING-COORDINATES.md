---
type: "sta-meaning-coordinates"
pericope: "E17"
pericope-title: "The institution of Purim: Mordecai's letters, the days bound for every year, and Esther's confirming word"
source-meaning-map: [[E17-Esther-9-20-32]]
status: "valid"
pilot: "pilot-2"
---

# E17 — Esther 9:20–32 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "esther_pericope_17_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",

  "header": {
    "bcv": "Esther 9:20-32",
    "pericope_title": "The institution of Purim: Mordecai's letters, the days bound for every year, and Esther's confirming word",
    "book_context_ref": "esther_pilot_BCD_v0_1",
    "source_meaning_map_ref": "E17-Esther-9-20-32",
    "source_language": "Biblical Hebrew"
  },

  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "Two scene-level FORMAL_OFFICIAL overrides on the two letter-acts where a binding obligation is enacted in writing: Scene 1 (Mordecai's instituting charge, v.20-22) and Scene 3 (the second confirming letter of peace and truth, v.29-31). Scene 2 (the name-explanation, v.24-26) stays INFORMAL_CASUAL — the narrator's plain etiology. The v.20 narrator-report of the writing/sending and the v.23 people's taking-on are narrator's voice, not the decree's voiced words, but the override is scoped at scene level per the map's call (Mapper note 1, open for Marcia).",
      "scene_level": [
        {
          "scene_id": "S1",
          "override_value": "FORMAL_OFFICIAL",
          "genre_override": null,
          "genre_group_override": null
        },
        {
          "scene_id": "S3",
          "override_value": "FORMAL_OFFICIAL",
          "genre_override": null,
          "genre_group_override": null
        }
      ],
      "moment_level": null
    }
  },

  "level_1": {
    "arc_elements": [
      "DELIVERANCE_MEMORIALIZED",
      "FESTIVAL_FOUNDED",
      "NAME_EXPLAINED",
      "OBLIGATION_BOUND",
      "RECORD_SEALED"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "TEMPORAL_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT",
      "HISTORICAL_ERA_CONTEXT"
    ],
    "tone_elements": [
      "SETTLED",
      "SLOWED",
      "FORWARD_LOOKING",
      "WEIGHTED_WITH_PERMANENCE",
      "WARM"
    ],
    "pace_elements": [
      "DELIBERATE",
      "MEASURED",
      "ACCUMULATES"
    ],
    "communicative_function_elements": [
      "BINDS",
      "PRESCRIBES",
      "EXPLAINS",
      "SEALS",
      "RECORDS"
    ]
  },

  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "9:20-23",
      "scene_kind": "FESTIVAL_FOUNDING_SCENE",
      "scene_communicative_purpose": "Founds the festival by written charge: which days, how often, and how they are to be kept.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B1",
            "role_in_scene": "SCRIBES",
            "presence": "PRESENT",
            "referential_form": "MORDECAI_THE_WRITER_OF_THE_LETTERS"
          },
          {
            "being_id": "B17",
            "role_in_scene": "PEOPLE",
            "presence": "PRESENT"
          },
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "REFERENCED"
          }
        ]
      },

      "places_in_scene": {
        "_note": "The reach of the letters is the 127 royal provinces (I5, an institution-span carried in L3 slots as bare atoms — realm_span / addressed_provinces — not a registry place). No discrete registry place is staged.",
        "entries": null
      },

      "objects_in_scene": {
        "_note": "The founded festival (I3-Purim) and its festal feasting (I1-mishteh) are institutions carried in L3 slots as bare atoms (founded_observance, banquet_named: MISHTEH); only the letters are a scene object.",
        "entries": [
          {
            "object_id": "TH_EDICT"
          }
        ]
      },

      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_ADAR"
          }
        ]
      },

      "significant_absence": "No God is named as the one who turned the sorrow to gladness — the reversal is stated in the passive (\"the month that was turned for them\"), with no hand assigned to it. The deliverance being commemorated is credited to no one in the text. And no priest, sanctuary, or sacrifice is named — this is a festival founded by letter, not by altar."
    },

    {
      "scene_id": "S2",
      "verse_range": "9:24-26",
      "scene_kind": "FESTIVAL_FOUNDING_SCENE",
      "scene_communicative_purpose": "Gives the festival's name and its reason — the lot, the plot, and its reversal — so the keeping is understood, not just observed.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B3",
            "role_in_scene": "ADVERSARY",
            "presence": "REFERENCED",
            "referential_form": "HAMAN_THE_AGAGITE_FOE_OF_THE_JEWS"
          },
          {
            "being_id": "B17",
            "role_in_scene": "PEOPLE",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B16",
            "role_in_scene": "SLAIN_SONS",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "REFERENCED"
          }
        ]
      },

      "places_in_scene": {
        "_note": "No scene-setting place; this is the narrator's explanation, set nowhere in particular.",
        "entries": null
      },

      "objects_in_scene": {
        "entries": [
          {
            "object_id": "TH_PUR_LOT"
          },
          {
            "object_id": "TH_GALLOWS"
          },
          {
            "object_id": "TH_EDICT"
          }
        ]
      },

      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; the narrator steps back to explain, outside the festival calendar.",
        "entries": null
      },

      "significant_absence": "The reversal is told with no word of God turning it — the plot simply \"returns on his own head.\" The book's signature silence holds even at the moment of explanation: the deliverance is named, dated, and named-after, but never credited to the One Israel would credit it to."
    },

    {
      "scene_id": "S3",
      "verse_range": "9:27-32",
      "scene_kind": "FESTIVAL_FOUNDING_SCENE",
      "scene_communicative_purpose": "Seals the festival with a second, doubly-authorized letter and a written record — making the observance permanent and binding on every generation.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B17",
            "role_in_scene": "PEOPLE",
            "presence": "PRESENT"
          },
          {
            "being_id": "B2",
            "role_in_scene": "SCRIBES",
            "presence": "PRESENT",
            "referential_form": "ESTHER_THE_QUEEN_DAUGHTER_OF_ABIHAIL"
          },
          {
            "being_id": "B1",
            "role_in_scene": "SCRIBES",
            "presence": "PRESENT",
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
        "_note": "The confirming letter reaches the 127 provinces (I5, an institution-span carried in L3 slots as bare atoms — realm_span / province_count: 127). No discrete registry place is staged. Abihail (Esther's father) is named only to identify Esther; per the map he is a descriptive patronymic carried as a being referential_form (ESTHER_THE_QUEEN_DAUGHTER_OF_ABIHAIL), not a registered being — open registry-delta call (Mapper note 3).",
        "entries": null
      },

      "objects_in_scene": {
        "_note": "The founded festival (I3-Purim) is an institution carried in L3 slots as bare atoms (purim_days). The scene objects are the second confirming letter and the book of record.",
        "entries": [
          {
            "object_id": "TH_EDICT"
          },
          {
            "object_id": "TH_ANNALS"
          }
        ]
      },

      "times_in_scene": {
        "entries": [
          {
            "time_id": "TM_ADAR"
          }
        ]
      },

      "significant_absence": "No oath to God, no blessing, no covenant-language of the LORD seals this binding — it is bound \"upon themselves and their seed\" by the people's own word and Esther's, recorded in a book, with no divine name invoked over the most solemn act of the chapter. And though \"fasting and lamentation\" are named, no prayer and no object of any prayer is."
    }
  ],

  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "9:20",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "writer": "B1",
        "written_record": "the_words",
        "record_qualifier": "these",
        "dispatched_letters": "TH_EDICT",
        "addressees": "B17",
        "addressee_extent": "all",
        "addressed_provinces": "the_provinces",
        "provinces_of": "B4",
        "province_reach": ["the_near", "the_far"]
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
      "verse_anchor": "9:21",
      "proposition_kind": "INSTRUCTION",
      "status": "NORM",
      "event_specific_slots": {
        "charge_components": [
          {
            "action": "DIRECTED",
            "charger": "B1",
            "charged_party": "B17",
            "charge_borne_in": "TH_EDICT",
            "charged_obligation": "a_keeping",
            "kept_day_first": "the_fourteenth",
            "kept_day_second": "the_fifteenth",
            "kept_month": "TM_ADAR",
            "keeping_frequency": "every_year",
            "status": "NORM",
            "speech_act": "PRESCRIBES_AS_LAW"
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
      "verse_anchor": "9:22",
      "proposition_kind": "INSTRUCTION",
      "status": "HABITUAL",
      "event_specific_slots": {
        "ground_of_charge": "a_turning",
        "turned_from_first": "grief",
        "turned_to_first": "joy",
        "turned_from_second": "mourning",
        "turned_to_second": "a_good_day",
        "turned_for": "B17",
        "freed_from": "their_enemies",
        "keeping_manner": ["feasting", "gladness", "sending", "gifts"],
        "banquet_named": "MISHTEH",
        "sent_thing": "portions",
        "sent_from": "a_man",
        "sent_to": "his_fellow",
        "gifts_to": "the_poor"
      },
      "inter_proposition_links": {
        "content_of": "P2",
        "forward_link_to": "P4"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P4",
      "scene_link": "S1",
      "verse_anchor": "9:23",
      "proposition_kind": "VOW",
      "event_specific_slots": {
        "obligated_party": "B17",
        "taken_on": "the_doing",
        "doing_qualifier": "what_they_had_begun",
        "also_taken_on": "the_writing",
        "writing_of": "B1",
        "written_to": "them"
      },
      "inter_proposition_links": {
        "caused_by": "P2"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P5",
      "scene_link": "S2",
      "verse_anchor": "9:24",
      "proposition_kind": "PLOTTED_AND_CAST_LOT",
      "status": "RECALLED",
      "event_specific_slots": {
        "plotter": "B3",
        "plotter_patronymic": "Hammedathas",
        "plotter_people": "the_Agagite",
        "plotter_standing": "a_foe",
        "foe_of": "B17",
        "plotted_against": "B17",
        "plotted_end": "destroying",
        "cast_thing": "TH_PUR_LOT",
        "lot_name": "the_pur",
        "lot_gloss": "the_goral",
        "casting_end": ["crushing", "destroying"]
      },
      "inter_proposition_links": {
        "forward_link_to": "P6"
      },
      "cross_ref": "The casting of this lot is at E07 (the lot-turned figure, shared with E07); not minted in this draft.",
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P6",
      "scene_link": "S2",
      "verse_anchor": "9:25",
      "proposition_kind": "INSTRUCTION",
      "status": "RECALLED",
      "event_specific_slots": {
        "coming_before": "B4",
        "order_components": [
          {
            "action": "DIRECTED",
            "orderer": "B4",
            "order_instrument": "a_letter",
            "ordered_outcome": "a_returning",
            "returned_thing": "the_plot",
            "plot_qualifier": "the_evil_one",
            "plot_of": "B3",
            "plot_against": "B17",
            "returned_onto": "his_head",
            "head_of": "B3",
            "speech_act": "PRESCRIBES_AS_LAW"
          }
        ],
        "hanged_party": "B3",
        "also_hanged": "B16",
        "hanged_on": "TH_GALLOWS"
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
      "verse_anchor": "9:26",
      "proposition_kind": "RENAMING",
      "event_specific_slots": {
        "named_thing": "the_days",
        "days_qualifier": "these",
        "given_name": "PURIM",
        "named_after": "the_name",
        "lot_namesake": "TH_PUR_LOT",
        "namesake_word": "the_pur",
        "grounded_in": "the_words",
        "words_of": "TH_EDICT",
        "letter_qualifier": "this_one",
        "also_grounded_in": ["what_they_had_seen", "what_had_come_upon_them"]
      },
      "inter_proposition_links": {
        "caused_by": "P6"
      },
      "cross_ref": "Candidate lot-turned figure (shared with E07) would flag here and at P5; not minted in this draft.",
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P8",
      "scene_link": "S3",
      "verse_anchor": "9:27",
      "proposition_kind": "VOW",
      "status": "NORM",
      "event_specific_slots": {
        "binding_components": [
          {
            "action": "BOUND",
            "binder": "B17",
            "bound_on_self": "themselves",
            "bound_on_seed": "their_seed",
            "bound_on_joiners": "all_who_joined_them",
            "binding_limit": "never_to_fail",
            "bound_obligation": "keeping",
            "kept_thing": "the_days",
            "days_count": "two",
            "days_qualifier": "these",
            "kept_manner": ["as_written", "at_their_appointed_time"],
            "keeping_frequency": "every_year",
            "status": "NORM",
            "speech_act": "RESOLVES_TO_ACT"
          }
        ]
      },
      "inter_proposition_links": {
        "forward_link_to": "P9"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P9",
      "scene_link": "S3",
      "verse_anchor": "9:28",
      "proposition_kind": "NAME_PRESERVED",
      "status": "NORM",
      "event_specific_slots": {
        "remembered_thing": "the_days",
        "also_done": "keeping",
        "remembered_scope": ["every_generation", "every_clan", "every_province", "every_city"],
        "non_lapse": "should_not_pass",
        "non_lapse_from": "B17",
        "memory_non_perish": "should_not_perish",
        "memory_from": "their_seed"
      },
      "inter_proposition_links": {
        "purpose_of": "P8"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P10",
      "scene_link": "S3",
      "verse_anchor": "9:29",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "confirm_components": [
          {
            "action": "WROTE",
            "writer_first": "B2",
            "writer_first_capacity": "queen",
            "writer_first_patronymic": "Abihails",
            "writer_second": "B1",
            "writer_second_qualifier": "the_Jew",
            "writing_authority": "full_authority",
            "writing_end": "confirming",
            "confirmed_letter": "TH_EDICT",
            "letter_qualifier": "the_Purim_one",
            "letter_order": "the_second",
            "speech_act": "PRESCRIBES_AS_LAW"
          }
        ]
      },
      "inter_proposition_links": {
        "forward_link_to": "P11"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P11",
      "scene_link": "S3",
      "verse_anchor": "9:30",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "dispatched_letters": "TH_EDICT",
        "addressees": "B17",
        "addressee_extent": "all",
        "addressed_provinces": "the_provinces",
        "province_count": "127",
        "provinces_of": "the_kingdom",
        "kingdom_of": "B4",
        "letter_content": "words",
        "content_qualities": ["peace", "truth"]
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
      "scene_link": "S3",
      "verse_anchor": "9:31",
      "proposition_kind": "DECLARED",
      "status": "NORM",
      "event_specific_slots": {
        "confirm_components": [
          {
            "action": "STATED",
            "confirmed_thing": "the_days",
            "days_qualifier": "the_Purim_ones",
            "kept_when": "at_their_appointed_times",
            "bound_by_first": "B1",
            "binder_first_qualifier": "the_Jew",
            "bound_by_second": "B2",
            "binder_second_capacity": "queen",
            "people_bound_on_self": "themselves",
            "people_bound_on_seed": "their_seed",
            "attendant_matters": ["fasting", "lamentation"],
            "status": "NORM",
            "speech_act": "PRESCRIBES_AS_LAW"
          }
        ]
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
      "scene_link": "S3",
      "verse_anchor": "9:32",
      "proposition_kind": "NAME_PRESERVED",
      "event_specific_slots": {
        "confirming_instrument": "a_word",
        "word_of": "B2",
        "confirmed_thing": "the_matters",
        "matters_of": "PURIM",
        "matters_qualifier": "these",
        "also_done": "writing",
        "written_in": "TH_ANNALS"
      },
      "inter_proposition_links": {
        "caused_by": "P12"
      },
      "cross_ref": "The book at v.32 (TH_ANNALS): Mapper note 5 flags whether this is the royal annals (registered, used here) or the book of Esther / a community Purim-record warranting a new THING-code. Open for Marcia; TH_ANNALS used in this draft.",
      "cb_flags": [],
      "figure_flags": []
    }
  ]
}
```

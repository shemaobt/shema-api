---
type: "sta-meaning-coordinates"
pericope: "E06"
pericope-title: "Haman raised, Mordecai unbowed: one man's refusal becomes a death-sentence for a people"
source-meaning-map: [[E06-Esther-3-1-6]]
status: "valid"
pilot: "pilot-2"
---

# E06 — Esther 3:1–6 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "esther_pericope_06_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Esther 3:1-6",
    "pericope_title": "Haman raised, Mordecai unbowed: one man's refusal becomes a death-sentence for a people",
    "book_context_ref": "esther_pilot_BCD_v0_1",
    "source_meaning_map_ref": "E06-Esther-3-1-6",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "Whole passage stays INFORMAL_CASUAL — the storyteller's plain voice reporting a promotion, a standoff at the gate, and a man's hidden rage from the outside. The king's order to bow (v.2) is NARRATED ('for so the king had commanded concerning him'), not quoted as an edict, so it draws no FORMAL_OFFICIAL moment-override (the command proposition carries status:NORM + speech_act:PRESCRIBES_AS_LAW as the underlying act, but the register stays casual because no decree is voiced on-stage — Marcia's standing rule). The one direct-speech moment, the servants' 'Why do you transgress the king's commandment?' (v.3), is ordinary court speech and stays INFORMAL_CASUAL. The destroying-edict is only SOUGHT in v.6, not yet issued.",
      "scene_level": null,
      "moment_level": null
    }
  },
  "level_1": {
    "arc_elements": [
      "PUBLIC_HONOR",
      "COMPELLED_HOMAGE",
      "LONE_REFUSAL",
      "EXPOSURE",
      "ROYAL_RAGE",
      "DISPROPORTIONATE_AIM"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "KINSHIP_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "POLITICAL_CONTEXT",
      "ANCESTRAL_ENMITY_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT"
    ],
    "tone_elements": [
      "CEREMONIAL",
      "TAUT",
      "GRINDING",
      "MENACING",
      "COLD"
    ],
    "pace_elements": [
      "STEADY",
      "DELIBERATE",
      "ACCELERATES"
    ],
    "communicative_function_elements": [
      "ELEVATES",
      "SETS_REFUSAL_AGAINST_HOMAGE",
      "TIES_REFUSAL_TO_IDENTITY",
      "SHOWS_DISPROPORTION",
      "LIGHTS_THE_FUSE"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "3:1",
      "scene_kind": "APPOINTMENT_SCENE",
      "scene_communicative_purpose": "Lifts Haman to the top of the court, establishing the height from which the conflict will fall.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT"
          },
          {
            "being_id": "B3",
            "role_in_scene": "ADVERSARY",
            "presence": "PRESENT",
            "referential_form": "THE_AGAGITE"
          }
        ]
      },
      "places_in_scene": {
        "_note": "No place named in this verse; the scene is the court, unspecified. No registry place code (per the map's Scene 1).",
        "entries": null
      },
      "objects_in_scene": {
        "_note": "Two load-bearing scene-content items ride as bare-atom prose, neither a registry object: Haman's seat of rank set above the other princes (his_seat / set_above_the_princes), and 'the Agagite' lineage tag (carried as B3's registered referential form 'the Agagite' on the being entry, not normalized away). Hammedatha (Haman's father, named only to fix lineage) is B3's registered referential form 'son of Hammedatha', carried as a lineage atom in Prop 1, not a standalone being. The princes over whom the seat is set are descriptive (the_princes / all_of_them) — see authoring question on B19.",
        "entries": null
      },
      "times_in_scene": {
        "_note": "The verse opens 'after these things' (a loose narrative seam, carried as the bare time atom 'after these things' in Prop 1), not a dated time-setting; no registry time code.",
        "entries": null
      },
      "significant_absence": "No reason is given for the promotion — no service rendered, no merit named (and pointedly, just before this, it was Mordecai who saved the king's life and went unrewarded). And no god is named over this raising-up; the elevation is the king's bare choice. The \"Agagite\" tag is dropped without explanation, left for the reader who knows the old story to feel its weight."
    },
    {
      "scene_id": "S2",
      "verse_range": "3:2-4",
      "scene_kind": "GATE_CONFRONTATION_SCENE",
      "scene_communicative_purpose": "Sets one man's refusal against the whole court's homage, ties the refusal to his Jewish identity, and hands the matter to Haman.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B1",
            "role_in_scene": "REFUSER",
            "presence": "PRESENT",
            "referential_form": "THE_JEW"
          },
          {
            "being_id": "B3",
            "role_in_scene": "REFUSER",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B18",
            "role_in_scene": "NOBLES",
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
        "entries": [
          {
            "place_id": "PL8"
          }
        ]
      },
      "objects_in_scene": {
        "_note": "Two load-bearing scene-content items ride as bare-atom prose, neither a registry object: the king's standing order that all bow to Haman (the_kings_commandment — the rule Mordecai breaks; carried in Prop 6 as status:NORM), and Mordecai's Jewishness (a_jew — the single reason he gives, the load-bearing identity disclosure; carried in Prop 12 and as B1's registered referential form 'the Jew').",
        "entries": null
      },
      "times_in_scene": {
        "_note": "'Day after day' (the repeated, grinding interval over which the servants press Mordecai) is iterative content carried inside Prop 9 as status:HABITUAL, not a dated time; no registry time code.",
        "entries": null
      },
      "significant_absence": "Mordecai gives no reason but \"I am a Jew\" — the text withholds any further explanation (no appeal to the commandment against bowing, no theology stated). The book's signature silence holds: God is never named as the ground of the refusal, even though the refusal is the book's first act of faithful defiance. And Mordecai never answers the servants' \"why\" — he simply does not listen, leaving the gap they then carry to Haman."
    },
    {
      "scene_id": "S3",
      "verse_range": "3:5-6",
      "scene_kind": "FURY_AND_GENOCIDAL_AIM_SCENE",
      "scene_communicative_purpose": "Shows Haman's rage breaking out, and the catastrophic widening of his aim from one man to an entire people across the empire.",
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
            "presence": "REFERENCED"
          },
          {
            "being_id": "B17",
            "role_in_scene": "THREATENED_PEOPLE",
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
        "_note": "'The whole kingdom of Ahasuerus' (the empire-wide reach of the intended destruction) is carried as the bare scene-content atom 'a kingdom / the whole of it' inside Prop 17, anchored to B4 (Ahasuerus's kingdom), not a registry place code.",
        "entries": null
      },
      "objects_in_scene": {
        "_note": "'Striking with the hand on Mordecai alone' (the narrow revenge Haman scorns) is carried as the bare scene-content atom 'a striking / a hand / him alone' inside Prop 15, not a registry object.",
        "entries": null
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; the fury and the plot follow directly on the servants' report.",
        "entries": null
      },
      "significant_absence": "Haman's leap from Mordecai to \"all the Jews\" is made with no stated deliberation, no counsel, no pause — the disproportion is left bare and uncommented. And the people now marked for death are named only as \"Mordecai's people,\" with no hint yet of the deliverance to come and, once more, no mention of God — the threat stands alone, unanswered, at the pericope's close."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "3:1",
      "proposition_kind": "APPOINTED",
      "event_specific_slots": {
        "promoter": "B4",
        "promoter_standing": "KING",
        "promoted": "B3",
        "promoted_lineage": "SON_OF_HAMMEDATHA",
        "promoted_line": "THE_AGAGITE",
        "when": "AFTER_THESE_THINGS"
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
      "verse_anchor": "3:1",
      "proposition_kind": "APPOINTED",
      "event_specific_slots": {
        "lifter": "B4",
        "lifted": "B3"
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
      "verse_anchor": "3:1",
      "proposition_kind": "APPOINTED",
      "event_specific_slots": {
        "setter": "B4",
        "seat_holder": "B3",
        "set_where": "ABOVE",
        "set_above": "THE_PRINCES",
        "princes_extent": "ALL",
        "princes_qualifier": "WITH_HIM"
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
      "verse_anchor": "3:2",
      "proposition_kind": "PROSTRATED",
      "event_specific_slots": {
        "kneeler": "B18",
        "kneeler_extent": "ALL",
        "where": "PL8",
        "knelt_to": "B3"
      },
      "inter_proposition_links": {
        "caused_by": "P6"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P5",
      "scene_link": "S2",
      "verse_anchor": "3:2",
      "proposition_kind": "PROSTRATED",
      "event_specific_slots": {
        "bower": "B18",
        "bowed_to": "B3"
      },
      "inter_proposition_links": {
        "caused_by": "P6"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P6",
      "scene_link": "S2",
      "verse_anchor": "3:2",
      "proposition_kind": "INSTRUCTION",
      "status": "NORM",
      "event_specific_slots": {
        "commander": "B4",
        "commanded_act": "BOWING",
        "concerning": "B3"
      },
      "inter_proposition_links": {
        "forward_link_to": "P7"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P7",
      "scene_link": "S2",
      "verse_anchor": "3:2",
      "proposition_kind": "DECLINED",
      "event_specific_slots": {
        "refuser": "B1",
        "refused_act": "KNEELING",
        "refused_also": "BOWING"
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
      "verse_anchor": "3:3",
      "proposition_kind": "QUESTIONED",
      "event_specific_slots": {
        "questioner": "B18",
        "where": "PL8",
        "questioned": "B1",
        "question_components": [
          {
            "challenge": "WHY_TRANSGRESS",
            "transgressed_thing": "COMMANDMENT",
            "commandment_giver": "B4",
            "speech_act": "ASKS_RHETORICAL_QUESTION_AS_PROTEST"
          }
        ]
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
      "verse_anchor": "3:4",
      "proposition_kind": "SPOKE",
      "status": "HABITUAL",
      "event_specific_slots": {
        "speaker": "B18",
        "spoken_to": "B1",
        "frequency": "DAY_AFTER_DAY"
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
      "verse_anchor": "3:4",
      "proposition_kind": "DECLINED",
      "event_specific_slots": {
        "non_listener": "B1",
        "unheeded": "B18"
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
      "verse_anchor": "3:4",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "informer": "B18",
        "informed": "B3",
        "purpose": "TO_SEE",
        "tested_thing": "WHETHER_STAND_HOLDS",
        "stander": "B1",
        "speech_act": "ALLEGES_AGAINST"
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
      "verse_anchor": "3:4",
      "proposition_kind": "IDENTIFIED",
      "event_specific_slots": {
        "discloser": "B1",
        "disclosed_to": "B18",
        "disclosed": "A_JEW",
        "disclosed_of": "B1",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P11"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P13",
      "scene_link": "S3",
      "verse_anchor": "3:5",
      "proposition_kind": "PERCEIVED",
      "event_specific_slots": {
        "seer": "B3",
        "saw": "NOT_KNEELING",
        "saw_also": "NOT_BOWING",
        "non_doer": "B1",
        "not_to": "B3"
      },
      "inter_proposition_links": {
        "forward_link_to": "P14"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P14",
      "scene_link": "S3",
      "verse_anchor": "3:5",
      "proposition_kind": "ANGER_KINDLED",
      "event_specific_slots": {
        "filled_one": "B3",
        "filled_with": "FURY"
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
      "scene_link": "S3",
      "verse_anchor": "3:6",
      "proposition_kind": "DECLINED",
      "event_specific_slots": {
        "scorner": "B3",
        "scorned_act": "STRIKING",
        "striking_means": "A_HAND",
        "struck_target": "B1",
        "target_extent": "HIM_ALONE"
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
      "scene_link": "S3",
      "verse_anchor": "3:6",
      "proposition_kind": "PEOPLE_REPORTED_TO_HAMAN",
      "event_specific_slots": {
        "reporter": "B18",
        "reported_to": "B3",
        "reported": "A_PEOPLE",
        "people_of": "B1"
      },
      "inter_proposition_links": {
        "back_reference_to_proposition": "P12",
        "forward_link_to": "P17"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P17",
      "scene_link": "S3",
      "verse_anchor": "3:6",
      "proposition_kind": "PROPOSED",
      "event_specific_slots": {
        "seeker": "B3",
        "sought_act": "DESTROYING",
        "destroy_target": "B17",
        "target_extent": "ALL",
        "people_of": "B1",
        "where": "A_KINGDOM",
        "kingdom_of": "B4",
        "kingdom_extent": "ENTIRE"
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

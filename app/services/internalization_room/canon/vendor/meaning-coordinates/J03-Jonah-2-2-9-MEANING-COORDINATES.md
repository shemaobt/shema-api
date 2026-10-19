---
type: "sta-meaning-coordinates"
pericope: "J03"
pericope-title: "The prayer from the deep: down to Sheol, up from the pit"
source-meaning-map: [[J03-Jonah-2-2-9]]
status: "valid"
pilot: "pilot-2"
drafter: "claude-opus-4-8 · fm-drafter prompt (see _spec/pins.json) · machine-drafted, ruled by Marcia (SC-0064 batch ruling §A–§E + arc_element, 2026-06-19); MODEL_DRAFTED_REVIEWER_RULED"
---

# J03 — Jonah 2:2–9 — MEANING_COORDINATES

> Judgment gaps filled by the SC-0063 drafter (`tripod draft --live`); the merge layer enforced the patch-only contract. NOT canon until ruled.

```json
{
  "sta_id": "jonah_pericope_03_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Jonah 2:2-9",
    "pericope_title": "The prayer from the deep: down to Sheol, up from the pit",
    "book_context_ref": "jonah_pilot_BCD_v0_3",
    "source_meaning_map_ref": "J03-Jonah-2-2-9",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "POETIC_SUNG",
    "genre": "PRAYER",
    "register": "RELIGIOUS_WORSHIP",
    "register_overrides": {
      "_note": "MM Section 1 states explicitly: no scene-level or moment-level shifts; the whole prayer holds RELIGIOUS_WORSHIP throughout (recounting, confessing, vowing all inside worship).",
      "scene_level": null,
      "moment_level": null
    }
  },
  "level_1": {
    "arc_elements": [
      "RESCUE_DECLARED",
      "AFFLICTION",
      "DESCENT_INTO_THE_DEEP",
      "TEMPLE_TURN",
      "LIFT_FROM_THE_PIT",
      "THANKSGIVING_VOW",
      "SALVATION_THESIS"
    ],
    "context_elements": [
      "PRIOR_PERICOPE_CARRY_FORWARD",
      "PRIOR_ACTION_CONTEXT",
      "STORY_WORLD_CONTEXT",
      "PHYSICAL_LOCATION",
      "INSTITUTIONAL_CONTEXT",
      "DIVINE_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT"
    ],
    "tone_elements": [
      "WEIGHTED",
      "RISING",
      "SLOWED",
      "STILLED",
      "DECLARATIVE"
    ],
    "pace_elements": [
      "SLOWED",
      "NARROWS",
      "SETTLES"
    ],
    "communicative_function_elements": [
      "ADVANCES",
      "REACTIVATES",
      "PLANTS",
      "CLOSES"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "2:3",
      "scene_kind": "RESCUE_DECLARATION_SCENE",
      "scene_communicative_purpose": "States the rescue before the road: the answered call is the headline, and everything after walks back through how deep the cry came from.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B1",
            "role_in_scene": "SUPPLIANT",
            "presence": "PRESENT",
            "referential_form": "UNNAMED_PRAYING_I"
          },
          {
            "being_id": "B2",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "PRESENT",
            "referential_form": "YHWH"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL6"
          }
        ]
      },
      "objects_in_scene": {
        "entries": []
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "The prayer never says where the speaker is — the fish is not mentioned in the poem, here or anywhere. The distress is named, never explained: nothing of the storm, the sailors, or why he was in the sea at all."
    },
    {
      "scene_id": "S2",
      "verse_range": "2:4-5",
      "scene_kind": "DISTRESS_RECOUNTING_SCENE",
      "scene_communicative_purpose": "Names the thrower: what the sailors' hands did, the prayer credits to YHWH — the sea was his sentence. And it sets the prayer's hinge: banishment answered not with despair but with a face turned toward the temple.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B1",
            "role_in_scene": "SUPPLIANT",
            "presence": "PRESENT"
          },
          {
            "being_id": "B2",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "PRESENT"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL4"
          },
          {
            "place_id": "PL7"
          }
        ]
      },
      "objects_in_scene": {
        "entries": []
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "The sailors who hurled him are gone from the telling — \"you cast me\" gives YHWH their act, and no human hand is mentioned. The banishment is stated without protest: there is no \"why?\", no plea against the sentence, and no asking to be spared."
    },
    {
      "scene_id": "S3",
      "verse_range": "2:6-8",
      "scene_kind": "DELIVERANCE_SCENE",
      "scene_communicative_purpose": "Touches bottom so the lift can be measured: three lines down, one line up. The remembering at the faint — not at the start — is the honest center: rescue came at the end of strength, and the prayer crossed the whole distance from the roots of the mountains to the temple.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B1",
            "role_in_scene": "SUPPLIANT",
            "presence": "PRESENT"
          },
          {
            "being_id": "B2",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "PRESENT",
            "referential_form": "YHWH_MY_GOD"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL8"
          },
          {
            "place_id": "PL7"
          }
        ]
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "O7"
          },
          {
            "object_id": "O8"
          }
        ]
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "There is no cry for help at the bottom — the poem records sinking, fainting, and remembering, but no plea; the lift is given before any asking is told. And still no word of guilt: the man dying under God's waves never says the flight was wrong."
    },
    {
      "scene_id": "S4",
      "verse_range": "2:9-10",
      "scene_kind": "VOW_SCENE",
      "scene_communicative_purpose": "Closes the prayer outward and forward: the rescued man takes the worshiper's side against the idol-keepers, promises the thanksgiving sacrifice and the paid vow — the very acts the sailors did on deck — and hands the book its thesis before the mission resumes.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B1",
            "role_in_scene": "VOWER",
            "presence": "PRESENT",
            "referential_form": "BUT_I"
          },
          {
            "being_id": "B2",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "PRESENT"
          },
          {
            "being_id": "B8",
            "role_in_scene": "IDOL_KEEPERS",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "entries": []
      },
      "objects_in_scene": {
        "entries": [
          {
            "object_id": "CB_0055"
          },
          {
            "object_id": "CB_0011"
          },
          {
            "object_id": "CB_0056"
          }
        ]
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "The vow's content is never told — what he vowed stays unsaid. There is no promise to go to Nineveh, no word about the errand he fled; the prayer ends with salvation declared and the obedience question still open."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "2:2",
      "proposition_kind": "APPEAL",
      "event_specific_slots": {
        "caller": "B1",
        "called_to": "B2",
        "answered_by": "B2",
        "speech_act": "STATES_AS_TRUE"
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
      "verse_anchor": "2:2",
      "proposition_kind": "APPEAL",
      "event_specific_slots": {
        "crier": "B1",
        "cried_from": "PL6",
        "heard_by": "B2",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P3",
        "paired_with": "P1"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P3",
      "scene_link": "S2",
      "verse_anchor": "2:3",
      "proposition_kind": "CAST_INTO_DEEP",
      "event_specific_slots": {
        "caster": "B2",
        "cast_one": "B1",
        "cast_location": "PL4",
        "speech_act": "STATES_AS_TRUE"
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
      "verse_anchor": "2:3",
      "proposition_kind": "ENGULFED",
      "event_specific_slots": {
        "engulfed_one": "B1",
        "waters_belong_to": "B2",
        "speech_act": "STATES_AS_TRUE"
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
      "verse_anchor": "2:4",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "speaker": "B1",
        "banished_from": "B2",
        "speech_act": "STATES_LAMENT_OBSERVATION"
      },
      "inter_proposition_links": {
        "forward_link_to": "P6"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P6",
      "scene_link": "S2",
      "verse_anchor": "2:4",
      "proposition_kind": "AFFIRMED_RESOLVE",
      "event_specific_slots": {
        "resolver": "B1",
        "directed_toward": "PL7",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "paired_with": "P11",
        "forward_link_to": "P7"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0202"
      ]
    },
    {
      "prop_id": "P7",
      "scene_link": "S3",
      "verse_anchor": "2:5",
      "proposition_kind": "ENGULFED",
      "event_specific_slots": {
        "surrounding_deep": "O7",
        "wrapping_weeds": "O8",
        "engulfed_one": "B1",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P8"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0203"
      ]
    },
    {
      "prop_id": "P8",
      "scene_link": "S3",
      "verse_anchor": "2:6",
      "proposition_kind": "DESCENDED",
      "event_specific_slots": {
        "descender": "B1",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P9"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0198"
      ]
    },
    {
      "prop_id": "P9",
      "scene_link": "S3",
      "verse_anchor": "2:6",
      "proposition_kind": "BROUGHT_UP",
      "event_specific_slots": {
        "raiser": "B2",
        "raised_life_of": "B1",
        "raised_from": "PL8",
        "divine_address_form": "YHWH_MY_GOD",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P10"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P10",
      "scene_link": "S3",
      "verse_anchor": "2:7",
      "proposition_kind": "REMEMBERED",
      "event_specific_slots": {
        "fainting_soul_of": "B1",
        "rememberer": "B1",
        "remembered_one": "B2",
        "speech_act": "STATES_AS_TRUE"
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
      "verse_anchor": "2:7",
      "proposition_kind": "ARRIVED_AT",
      "event_specific_slots": {
        "arriving_prayer_of": "B1",
        "prayer_reached": "B2",
        "arrival_destination": "PL7",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P10",
        "paired_with": "P6",
        "forward_link_to": "P12"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0202"
      ]
    },
    {
      "prop_id": "P12",
      "scene_link": "S4",
      "verse_anchor": "2:8",
      "proposition_kind": "FORSOOK",
      "event_specific_slots": {
        "forsakers": "B8",
        "idols_kept": "CB_0055",
        "forsaken_loyalty": "CB_0011",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "forward_link_to": "P13"
      },
      "cb_flags": [
        "CB_0011",
        "CB_0055"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P13",
      "scene_link": "S4",
      "verse_anchor": "2:9",
      "proposition_kind": "VOW",
      "event_specific_slots": {
        "vower": "B1",
        "vowed_to": "B2",
        "contrast_with_proposition": "P12",
        "speech_act": "VOWS"
      },
      "inter_proposition_links": {
        "forward_link_to": "P14"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P14",
      "scene_link": "S4",
      "verse_anchor": "2:9",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "declarer": "B1",
        "salvation_belongs_to": "B2",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {},
      "cb_flags": [
        "CB_0056"
      ],
      "figure_flags": []
    }
  ]
}
```

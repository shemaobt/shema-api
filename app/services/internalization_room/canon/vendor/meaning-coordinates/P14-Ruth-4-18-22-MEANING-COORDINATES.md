---
type: "sta-meaning-coordinates"
pericope: "P14"
pericope-title: "The generations of Perez: ten names to David"
source-meaning-map: [[P14-Ruth-4-18-22]]
status: "valid"
pilot: "pilot-2"
drafter: "claude-opus-4-8 · fm-drafter prompt (see _spec/pins.json) · machine-drafted, ruled by Marcia (SC-0064 batch ruling §A–§E + arc_element, 2026-06-19); MODEL_DRAFTED_REVIEWER_RULED"
---

# P14 — Ruth 4:18-22 — MEANING_COORDINATES

> Judgment gaps filled by the SC-0063 drafter (`tripod draft --live`); the merge layer enforced the patch-only contract. NOT canon until ruled.

```json
{
  "sta_id": "ruth_pericope_14_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Ruth 4:18-22",
    "pericope_title": "The generations of Perez: ten names to David",
    "book_context_ref": "ruth_pilot_BCD_v0_3",
    "source_meaning_map_ref": "P14-Ruth-4-18-22",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "GENEALOGY",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "MM Section 1 explicitly states there are no character speeches, no ceremony, and no register shift anywhere in the unit — pericope-level INFORMAL_CASUAL throughout. No scene-level or moment-level overrides.",
      "scene_level": null,
      "moment_level": null
    }
  },
  "level_1": {
    "arc_elements": [
      "GENEALOGICAL_DESCENT",
      "LINE_TERMINUS_REACHED",
      "NARRATOR_FRAMING_CLOSE"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "KINSHIP_CONTEXT",
      "HISTORICAL_ERA_CONTEXT",
      "TEMPORAL_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT",
      "DIVINE_CONTEXT",
      "PRIOR_PERICOPE_CARRY_FORWARD"
    ],
    "tone_elements": [
      "CHRONICLE",
      "DECLARATIVE",
      "WEIGHTED",
      "RESTRAINED"
    ],
    "pace_elements": [
      "STEADY",
      "SETTLES"
    ],
    "communicative_function_elements": [
      "ESTABLISHES",
      "ADVANCES",
      "CLOSES"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "4:18-22",
      "scene_kind": "GENEALOGY_SCENE",
      "scene_communicative_purpose": "Closes the book with a line of ten names from Perez to David; Boaz and Obed are among them.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B27",
            "role_in_scene": "ANCESTOR",
            "presence": "REFERENCED",
            "referential_form": "SALMAH_AND_SALMON"
          },
          {
            "being_id": "B13",
            "role_in_scene": "ANCESTOR",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B25",
            "role_in_scene": "ANCESTOR",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B26",
            "role_in_scene": "LINE_TERMINUS",
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
            "object_id": "CB_0049"
          }
        ]
      },
      "times_in_scene": {
        "_note": "no distinct temporal frame for this scene (per meaning map)",
        "entries": null
      },
      "significant_absence": "The list names no woman — not Tamar, not Ruth, not Naomi; it names only fathers and sons. It does not name God. It adds no comment on David; the list stops at his name."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "4:18a",
      "proposition_kind": "GENEALOGY_HEADER",
      "event_specific_slots": {
        "lineage_founder": "B27",
        "founder_name": "Perez",
        "line_form": "TOLEDOT_OF_PEREZ"
      },
      "inter_proposition_links": {
        "forward_link_to": "P2"
      },
      "cb_flags": [
        "CB_0049",
        "CB_0005"
      ],
      "figure_flags": [
        "FIG_0193",
        "FIG_0191"
      ]
    },
    {
      "prop_id": "P2",
      "scene_link": "S1",
      "verse_anchor": "4:18b",
      "proposition_kind": "FATHERED",
      "event_specific_slots": {
        "begetter": "B27",
        "begetter_name": "Perez",
        "begotten": "B27",
        "begotten_name": "Hezron"
      },
      "inter_proposition_links": {
        "forward_link_to": "P3"
      },
      "cb_flags": [
        "CB_0049"
      ],
      "figure_flags": [
        "FIG_0190"
      ]
    },
    {
      "prop_id": "P3",
      "scene_link": "S1",
      "verse_anchor": "4:19a",
      "proposition_kind": "FATHERED",
      "event_specific_slots": {
        "begetter": "B27",
        "begetter_name": "Hezron",
        "begotten": "B27",
        "begotten_name": "Ram"
      },
      "inter_proposition_links": {
        "forward_link_to": "P4"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P4",
      "scene_link": "S1",
      "verse_anchor": "4:19b",
      "proposition_kind": "FATHERED",
      "event_specific_slots": {
        "begetter": "B27",
        "begetter_name": "Ram",
        "begotten": "B27",
        "begotten_name": "Amminadab"
      },
      "inter_proposition_links": {
        "forward_link_to": "P5"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P5",
      "scene_link": "S1",
      "verse_anchor": "4:20a",
      "proposition_kind": "FATHERED",
      "event_specific_slots": {
        "begetter": "B27",
        "begetter_name": "Amminadab",
        "begotten": "B27",
        "begotten_name": "Nahshon"
      },
      "inter_proposition_links": {
        "forward_link_to": "P6"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P6",
      "scene_link": "S1",
      "verse_anchor": "4:20b",
      "proposition_kind": "FATHERED",
      "event_specific_slots": {
        "begetter": "B27",
        "begetter_name": "Nahshon",
        "begotten": "B27",
        "begotten_name": "Salmon",
        "begotten_name_form": "SALMAH"
      },
      "inter_proposition_links": {
        "forward_link_to": "P7"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P7",
      "scene_link": "S1",
      "verse_anchor": "4:21a",
      "proposition_kind": "FATHERED",
      "event_specific_slots": {
        "begetter": "B27",
        "begetter_name": "Salmon",
        "begetter_name_form": "SALMON",
        "begotten": "B13",
        "begotten_name": "Boaz"
      },
      "inter_proposition_links": {
        "forward_link_to": "P8"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P8",
      "scene_link": "S1",
      "verse_anchor": "4:21b",
      "proposition_kind": "FATHERED",
      "event_specific_slots": {
        "begetter": "B13",
        "begetter_name": "Boaz",
        "begotten": "B25",
        "begotten_name": "Obed"
      },
      "inter_proposition_links": {
        "forward_link_to": "P9"
      },
      "cb_flags": [
        "CB_0047"
      ],
      "figure_flags": [
        "FIG_0192",
        "FIG_0194"
      ]
    },
    {
      "prop_id": "P9",
      "scene_link": "S1",
      "verse_anchor": "4:22a",
      "proposition_kind": "FATHERED",
      "event_specific_slots": {
        "begetter": "B25",
        "begetter_name": "Obed",
        "begotten": "B26",
        "begotten_name": "Jesse"
      },
      "inter_proposition_links": {
        "forward_link_to": "P10"
      },
      "cb_flags": [],
      "figure_flags": [
        "FIG_0192",
        "FIG_0194"
      ]
    },
    {
      "prop_id": "P10",
      "scene_link": "S1",
      "verse_anchor": "4:22b",
      "proposition_kind": "FATHERED",
      "event_specific_slots": {
        "begetter": "B26",
        "begetter_name": "Jesse",
        "begotten": "B26",
        "begotten_name": "David",
        "begotten_role": "LINE_TERMINUS"
      },
      "inter_proposition_links": {},
      "cb_flags": [
        "CB_0048"
      ],
      "figure_flags": [
        "FIG_0192",
        "FIG_0189",
        "FIG_0194"
      ]
    }
  ]
}
```

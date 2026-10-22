---
type: "sta-meaning-coordinates"
pericope: "P03"
pericope-title: "Naomi's last appeal; Ruth's vow; Naomi's silence"
source-meaning-map: [[P03-Ruth-1-15-18]]
status: "valid"
pilot: "pilot-2"
---

# P03 — Ruth 1:15–18 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "ruth_pericope_03_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Ruth 1:15-18",
    "pericope_title": "Naomi's last appeal; Ruth's vow; Naomi's silence",
    "book_context_ref": "ruth_pilot_BCD_v0_3",
    "source_meaning_map_ref": "P03-Ruth-1-15-18",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "Two scene-level INTIMATE overrides on S1 (Naomi's last appeal) and S2 (Ruth's vow). S3 returns to INFORMAL_CASUAL narrator default. No moment-level overrides.",
      "scene_level": [
        {
          "scene_id": "S1",
          "override_value": "INTIMATE",
          "genre_override": null,
          "genre_group_override": null
        },
        {
          "scene_id": "S2",
          "override_value": "INTIMATE",
          "genre_override": "BLESSING",
          "genre_group_override": "POETIC_SUNG"
        }
      ],
      "moment_level": null
    }
  },
  "level_1": {
    "arc_elements": [
      "RELEASE_ATTEMPT",
      "REFUSAL_OF_RELEASE",
      "COVENANT_BINDING_BY_VOW",
      "OATH_SEALING",
      "SILENCE_AFTER_VOW"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "KINSHIP_CONTEXT",
      "TRAJECTORY_CONTEXT_ON_RETURN_ROAD",
      "AUDIENCE_KNOWLEDGE_CONTEXT",
      "PRIOR_PERICOPE_CARRY_FORWARD"
    ],
    "tone_elements": [
      "INTIMATE",
      "WEIGHTED",
      "SLOWED",
      "RISING",
      "UNSETTLED_AT_CLOSE"
    ],
    "pace_elements": [
      "NARROWS",
      "DELIBERATE",
      "PAUSED"
    ],
    "communicative_function_elements": [
      "ESTABLISHES",
      "ADVANCES",
      "PLACES",
      "WITHHOLDS"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "1:15",
      "scene_kind": "APPEAL_SCENE",
      "scene_communicative_purpose": "Records Naomi's last try to send Ruth away, holding up Orpah's going-back to her people and her gods as the example Ruth should follow.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B3",
            "role_in_scene": "MOTHER_IN_LAW",
            "presence": "PRESENT"
          },
          {
            "being_id": "B9",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "PRESENT"
          },
          {
            "being_id": "B8",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "REFERENCED",
            "referential_form": "YEBIMTEKH"
          }
        ]
      },
      "places_in_scene": {
        "entries": [
          {
            "place_id": "PL2"
          },
          {
            "place_id": "PL_LAND_OF_JUDAH"
          }
        ]
      },
      "objects_in_scene": {
        "_note": "No persistent objects in this scene.",
        "entries": null
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; time is continuous with the journey established in P02.",
        "entries": null
      },
      "significant_absence": "Naomi names no place; she speaks of where Orpah went only as 'her people' and 'her gods.' The gods of Moab go unnamed at v.15; YHWH is named only at v.17 (Scene 2). The unnamed gods stand against the named God."
    },
    {
      "scene_id": "S2",
      "verse_range": "1:16-17",
      "scene_kind": "VOW_SCENE",
      "scene_communicative_purpose": "Ruth refuses to turn back and binds herself to Naomi in six rising steps, sealed with an oath that calls down a curse on herself and names YHWH out loud.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B9",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "PRESENT"
          },
          {
            "being_id": "B3",
            "role_in_scene": "MOTHER_IN_LAW",
            "presence": "PRESENT"
          },
          {
            "being_id": "B10",
            "role_in_scene": "DIVINE_AGENT",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B31",
            "role_in_scene": "PEOPLE",
            "presence": "REFERENCED"
          }
        ]
      },
      "places_in_scene": {
        "_note": "No proper place is named inside the vow. Ruth uses four indefinite-place constructions across the binding ladder (where you go / where you lodge / where you die / there I will be buried) without naming any PL-coded place. PL_LAND_OF_JUDAH continues as implicit onward destination of the road. No PL-coded place is anchored to a specific binding.",
        "entries": [
          {
            "place_id": "PL_LAND_OF_JUDAH"
          }
        ]
      },
      "objects_in_scene": {
        "_note": "No persistent objects in this scene.",
        "entries": null
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame for this scene; time is continuous with the journey.",
        "entries": null
      },
      "significant_absence": "Narrator never calls Ruth 'the Moabite' (FIG_0001) anywhere in this scene. Ruth names no place inside the vow — not Bethlehem, not anywhere. She says 'your God' at v.16 without naming him; God's name comes only in the oath at v.17. And she gives no reasons for the bond beyond the bond itself."
    },
    {
      "scene_id": "S3",
      "verse_range": "1:18",
      "scene_kind": "RATIFICATION_SCENE",
      "scene_communicative_purpose": "Marks the failure of Naomi's last try to send Ruth away, and the moment from which the two go on together. Ends the talk on the road.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B3",
            "role_in_scene": "MOTHER_IN_LAW",
            "presence": "PRESENT"
          },
          {
            "being_id": "B9",
            "role_in_scene": "DAUGHTER_IN_LAW",
            "presence": "PRESENT"
          }
        ]
      },
      "places_in_scene": {
        "_note": "No PL-coded place anchored to this scene. The road continues as a structural object.",
        "entries": null
      },
      "objects_in_scene": {
        "_note": "No persistent objects in this scene.",
        "entries": null
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame; closing moment continuous with the journey.",
        "entries": null
      },
      "significant_absence": "Narrator tells us Naomi sees and stops speaking, but nothing of what is going on inside her. No agreement, no blessing, no further word from Naomi in this passage. We are let into Ruth's resolve, but not into how Naomi takes it."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "1:15",
      "proposition_kind": "APPEAL",
      "event_specific_slots": {
        "speaker": "B3",
        "addressees": [
          "B9"
        ],
        "appeal_components": [
          {
            "action": "STATED",
            "speaker": "B3",
            "exemplar_party": "B8",
            "exemplar_referential_form": "YEBIMTEKH",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "DIRECTED",
            "speaker": "B3",
            "addressee": "B9",
            "exemplar_party": "B8",
            "exemplar_referential_form": "YEBIMTEKH",
            "speech_act": "DIRECTS_HEARER_TO_RETURN"
          }
        ]
      },
      "inter_proposition_links": {
        "forward_link_to": "P2"
      },
      "cb_flags": [
        "CB_0019",
        "CB_0004"
      ],
      "figure_flags": []
    },
    {
      "prop_id": "P2",
      "scene_link": "S2",
      "verse_anchor": "1:16a",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "refuser": "B9",
        "addressee": "B3",
        "speech_act": "REFUSES_REQUEST_WITH_COUNTER_DECLARATION"
      },
      "inter_proposition_links": {
        "back_reference_to_proposition": "P1",
        "forward_link_to": "P3"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P3",
      "scene_link": "S2",
      "verse_anchor": "1:16b-17a",
      "proposition_kind": "VOW",
      "event_specific_slots": {
        "speaker": "B9",
        "addressee": "B3",
        "vow_structural_form": "SIX_STEP_LADDER_PATH_LODGING_PEOPLE_GOD_DEATH_BURIAL",
        "vow_components": [
          {
            "action": "VOWED",
            "binder": "B9",
            "bound_to": "B3",
            "binding_indefinite_place_form": "WHERE_YOU_GO",
            "matched_action_form": "I_WILL_GO",
            "list_position": "FIRST",
            "speech_act": "VOWS"
          },
          {
            "action": "VOWED",
            "binder": "B9",
            "bound_to": "B3",
            "binding_indefinite_place_form": "WHERE_YOU_LODGE",
            "matched_action_form": "I_WILL_LODGE",
            "list_position": "SECOND",
            "speech_act": "VOWS"
          },
          {
            "action": "VOWED",
            "binder": "B9",
            "bound_to": "B3",
            "bound_to_collective": "B31",
            "nominal_equation_half": "PEOPLE_HALF",
            "list_position": "THIRD",
            "speech_act": "VOWS"
          },
          {
            "action": "VOWED",
            "binder": "B9",
            "bound_to": "B3",
            "invoked_deity": "B10",
            "referential_form_at_verse": "UNNAMED_DEITY",
            "nominal_equation_half": "GOD_HALF",
            "list_position": "FOURTH",
            "speech_act": "VOWS"
          },
          {
            "action": "VOWED",
            "binder": "B9",
            "bound_to": "B3",
            "binding_indefinite_place_form": "WHERE_YOU_DIE",
            "matched_action_form": "I_WILL_DIE",
            "binding_domain": "IDENTITY_AT_LIMIT_OF_EXISTENCE",
            "list_position": "FIFTH",
            "speech_act": "VOWS"
          },
          {
            "action": "VOWED",
            "binder": "B9",
            "bound_to": "B3",
            "binding_demonstrative_place_form": "THERE_DEMONSTRATIVE_LINKING_TO_DEATH_PLACE",
            "matched_action_form": "I_WILL_BE_BURIED",
            "binding_domain": "PLACE_OF_FINAL_REST",
            "list_position": "SIXTH",
            "speech_act": "VOWS"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P2",
        "forward_link_to": "P4"
      },
      "cb_flags": [
        "CB_0021"
      ],
      "figure_flags": [
        "FIG_0072",
        "FIG_0074"
      ]
    },
    {
      "prop_id": "P4",
      "scene_link": "S2",
      "verse_anchor": "1:17b",
      "proposition_kind": "VOW",
      "event_specific_slots": {
        "speaker": "B9",
        "addressee": "B3",
        "named_doer": "B10",
        "named_doer_referential_form": "YHWH",
        "speech_act": "INVOKES_SELF_CURSE_AS_OATH_ENFORCEMENT"
      },
      "inter_proposition_links": {
        "caused_by": "P3",
        "forward_link_to": "P5"
      },
      "cb_flags": [
        "CB_0020"
      ],
      "figure_flags": [
        "FIG_0075"
      ]
    },
    {
      "prop_id": "P5",
      "scene_link": "S3",
      "verse_anchor": "1:18",
      "proposition_kind": "PERCEIVED",
      "event_specific_slots": {
        "narrator_report_components": [
          {
            "action": "SAW",
            "perceiver": "B3",
            "perceived": "B9",
            "list_position": "FIRST",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "CEASED_SPEAKING",
            "ceaser": "B3",
            "ceased_speaking_to": "B9",
            "list_position": "SECOND",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P3",
        "back_reference_to_proposition": "P4"
      },
      "cb_flags": [],
      "figure_flags": []
    }
  ],
  "fidelity":   {
    "elements": [
      {
        "ref": {
          "prop_id": "P3",
          "slot": "vow_components",
          "list_position": "FIRST"
        },
        "preserve_meaning": true,
        "preserve_form": false
      },
      {
        "ref": {
          "prop_id": "P3",
          "slot": "vow_components",
          "list_position": "SECOND"
        },
        "preserve_meaning": true,
        "preserve_form": false
      },
      {
        "ref": {
          "prop_id": "P3",
          "slot": "vow_components",
          "list_position": "THIRD"
        },
        "preserve_meaning": true,
        "preserve_form": false,
        "group": "people_god_inseparability"
      },
      {
        "ref": {
          "prop_id": "P3",
          "slot": "vow_components",
          "list_position": "FOURTH"
        },
        "preserve_meaning": true,
        "preserve_form": false,
        "group": "people_god_inseparability"
      },
      {
        "ref": {
          "prop_id": "P3",
          "slot": "vow_components",
          "list_position": "FIFTH"
        },
        "preserve_meaning": true,
        "preserve_form": false,
        "group": "unto_the_end"
      },
      {
        "ref": {
          "prop_id": "P3",
          "slot": "vow_components",
          "list_position": "SIXTH"
        },
        "preserve_meaning": true,
        "preserve_form": false,
        "group": "unto_the_end"
      }
    ],
    "groups": [
      {
        "group_id": "people_god_inseparability",
        "members": [
          {
            "prop_id": "P3",
            "slot": "vow_components",
            "list_position": "THIRD"
          },
          {
            "prop_id": "P3",
            "slot": "vow_components",
            "list_position": "FOURTH"
          }
        ],
        "preserve_meaning": true,
        "preserve_form": false
      },
      {
        "group_id": "unto_the_end",
        "members": [
          {
            "prop_id": "P3",
            "slot": "vow_components",
            "list_position": "FIFTH"
          },
          {
            "prop_id": "P3",
            "slot": "vow_components",
            "list_position": "SIXTH"
          }
        ],
        "preserve_meaning": true,
        "preserve_form": false
      }
    ],
    "structure_flags": [
      {
        "ref": {
          "prop_id": "P3",
          "field": "vow_structural_form"
        },
        "preserve_meaning": true,
        "preserve_form": false
      }
    ],
    "register_overrides": [
      {
        "ref": {
          "scene_id": "S2"
        },
        "preserve_meaning": true,
        "preserve_form": false
      }
    ]
  }
}
```

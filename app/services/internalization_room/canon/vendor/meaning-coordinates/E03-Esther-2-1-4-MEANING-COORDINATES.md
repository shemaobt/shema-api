---
type: "sta-meaning-coordinates"
pericope: "E03"
pericope-title: "The remedy proposed: a search for a new queen"
source-meaning-map: [[E03-Esther-2-1-4]]
status: "valid"
pilot: "pilot-2"
---

# E03 — Esther 2:1–4 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "esther_pericope_03_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Esther 2:1-4",
    "pericope_title": "The remedy proposed: a search for a new queen",
    "book_context_ref": "esther_pilot_BCD_v0_1",
    "source_meaning_map_ref": "E03-Esther-2-1-4",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "The whole passage sits in INFORMAL_CASUAL. The voiced proposal (v.2-4) is courtiers floating a plan to their lord, not a sealed/written edict, so it stays INFORMAL_CASUAL — the decree-key (FORMAL_OFFICIAL + PRESCRIBES_AS_LAW) is reserved for voiced/granted decrees. No scene- or moment-level overrides.",
      "scene_level": null,
      "moment_level": null
    }
  },
  "level_1": {
    "arc_elements": [
      "ANGER_SUBSIDING",
      "VACANCY",
      "REMEDY_PROPOSED",
      "SEARCH_SET_IN_MOTION",
      "FAVOR_GRANTED"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "ROYAL_COURT_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "IMPERIAL_ADMINISTRATION_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT"
    ],
    "tone_elements": [
      "QUIET",
      "WEIGHTED",
      "PROCEDURAL",
      "BUSINESSLIKE",
      "COOL"
    ],
    "pace_elements": [
      "DELIBERATE",
      "ACCELERATES",
      "DECISIVE_CLOSE"
    ],
    "communicative_function_elements": [
      "OPENS",
      "STAGES",
      "ADVANCES",
      "PLANTS",
      "RESOLVES"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "2:1",
      "scene_kind": "ROYAL_RECOLLECTION_SCENE",
      "scene_communicative_purpose": "Shows the king, his rage spent, brooding over the queen he removed — opening the vacancy the rest of the passage will move to fill.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT",
            "referential_form": "THE_KING_AHASUERUS"
          },
          {
            "being_id": "B5",
            "role_in_scene": "QUEEN",
            "presence": "REFERENCED",
            "referential_form": "VASHTI_REMOVED"
          }
        ]
      },
      "places_in_scene": {
        "_note": "No place named in this verse; the setting is the court at Susa carried over from the preceding scenes.",
        "entries": null
      },
      "objects_in_scene": {
        "_note": "The king's cooled anger and the recalled decree against Vashti are descriptive scene content (not registry objects); they are carried as bare-atom slots in the propositions.",
        "entries": null
      },
      "times_in_scene": {
        "_note": "The bridge-phrase 'after these things' is a narrative seam, not a dated time; carried as a bare-atom slot in Proposition P1.",
        "entries": null
      },
      "significant_absence": "The king remembers what Vashti did and what was decreed — but no word of regret, of missing her, or of any wish to undo it is stated. Whether he longs for her or merely registers the empty place is left blank. And God, who is nowhere named in this book, is absent here too: the king's memory turns, but nothing turns it."
    },
    {
      "scene_id": "S2",
      "verse_range": "2:2-4",
      "scene_kind": "CRISIS_DELIBERATION_SCENE",
      "scene_communicative_purpose": "Sets the empire-wide search in motion — the officers, the gathering to the harem under Hegai, the selection-by-pleasing — and shows the king approving it, turning a suggestion into imperial action.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT",
            "referential_form": "THE_KING"
          },
          {
            "being_id": "B18",
            "role_in_scene": "NOBLES",
            "presence": "PRESENT",
            "referential_form": "THE_KINGS_YOUNG_MEN_WHO_ATTENDED_HIM"
          },
          {
            "being_id": "B7",
            "role_in_scene": "GUARDIAN",
            "presence": "REFERENCED",
            "referential_form": "HEGAI_THE_KINGS_EUNUCH"
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
        "_note": "The harem (the house of the women) is an institution carried as bare-atom slots in the propositions, not a registry object; the cosmetics and the royal office of queen are descriptive scene content, likewise carried as bare-atom slots.",
        "entries": null
      },
      "times_in_scene": {
        "_note": "No distinct temporal frame; the proposal follows directly on the king's remembering in Scene 1.",
        "entries": null
      },
      "significant_absence": "No one asks whether Vashti might be restored, or whether the women have any say. The plan speaks of them entirely by beauty and availability, never by name, will, or family. And again God is not named: the search that will bring the book's deliverer to the throne is proposed and approved as pure court business, with no hint that anything but royal appetite is steering it."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "2:1",
      "proposition_kind": "WRATH_SUBSIDED",
      "event_specific_slots": {
        "subsided_emotion": "ANGER",
        "emotion_holder": "B4",
        "narrative_seam": "AFTER_THESE_THINGS"
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
      "verse_anchor": "2:1",
      "proposition_kind": "REMEMBERED",
      "event_specific_slots": {
        "rememberer": "B4",
        "remembered_party": "B5",
        "recalled_components": [
          {
            "action": "DID",
            "doer": "B5",
            "deed": "WHAT_SHE_DID",
            "status": "RECALLED",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "DIRECTED",
            "decree_target": "B5",
            "decreed_thing": "THE_DECREE",
            "status": "RECALLED",
            "speech_act": "STATES_AS_TRUE"
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
      "verse_anchor": "2:2",
      "proposition_kind": "PROPOSED",
      "event_specific_slots": {
        "speaker": "B18",
        "addressee": "B4",
        "proposal_content": ["P4", "P5", "P6", "P7", "P8"],
        "speech_act": "PROPOSES_COURSE_OF_ACTION"
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
      "verse_anchor": "2:2",
      "proposition_kind": "QUESTIONED",
      "status": "FORESEEN",
      "event_specific_slots": {
        "seeker": "B18",
        "sought_for": "B4",
        "sought_party": "YOUNG_WOMEN",
        "sought_kind": "VIRGINS",
        "sought_quality": "GOOD_IN_APPEARANCE"
      },
      "inter_proposition_links": {
        "content_of": "P3",
        "forward_link_to": "P5"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P5",
      "scene_link": "S2",
      "verse_anchor": "2:3",
      "proposition_kind": "APPOINTED",
      "status": "FORESEEN",
      "event_specific_slots": {
        "appointer": "B4",
        "appointed_party": "OFFICERS",
        "realm_span": "ALL_THE_PROVINCES",
        "realm_holder": "B4"
      },
      "inter_proposition_links": {
        "content_of": "P3",
        "forward_link_to": "P6"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P6",
      "scene_link": "S2",
      "verse_anchor": "2:3",
      "proposition_kind": "GATHERED",
      "status": "FORESEEN",
      "event_specific_slots": {
        "gatherer": "OFFICERS",
        "gathered_party": "EVERY_YOUNG_WOMAN",
        "gathered_kind": "VIRGIN",
        "gathered_quality": "GOOD_IN_APPEARANCE",
        "gathering_destination": "PL1",
        "holding_house": "BEIT_HANASHIM",
        "custodian": "B7",
        "custodian_office": "KEEPER_OF_WOMEN",
        "custodian_is_eunuch": "EUNUCH",
        "custodian_master": "B4"
      },
      "inter_proposition_links": {
        "content_of": "P3",
        "purpose_of": "P5"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P7",
      "scene_link": "S2",
      "verse_anchor": "2:3",
      "proposition_kind": "GAVE",
      "status": "FORESEEN",
      "event_specific_slots": {
        "given_thing": "COSMETICS",
        "given_to": "THE_WOMEN"
      },
      "inter_proposition_links": {
        "content_of": "P3",
        "forward_link_to": "P8"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P8",
      "scene_link": "S2",
      "verse_anchor": "2:4",
      "proposition_kind": "REIGNED",
      "status": "FORESEEN",
      "event_specific_slots": {
        "reigning_party": "THE_PLEASING_WOMAN",
        "pleased_one": "B4",
        "pleasing_in": "HIS_EYES",
        "replaced_party": "B5"
      },
      "inter_proposition_links": {
        "content_of": "P3"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P9",
      "scene_link": "S2",
      "verse_anchor": "2:4",
      "proposition_kind": "GRANTED",
      "event_specific_slots": {
        "pleasing_thing": "THE_MATTER",
        "pleased_one": "B4",
        "pleasing_in": "HIS_EYES"
      },
      "inter_proposition_links": {
        "caused_by": "P3",
        "forward_link_to": "P10"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P10",
      "scene_link": "S2",
      "verse_anchor": "2:4",
      "proposition_kind": "ACTED",
      "event_specific_slots": {
        "doer": "B4",
        "deed": "SO"
      },
      "inter_proposition_links": {
        "caused_by": "P9"
      },
      "cb_flags": [],
      "figure_flags": []
    }
  ]
}
```

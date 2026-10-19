---
type: "sta-meaning-coordinates"
pericope: "E18"
pericope-title: "The book closes: the king's tribute and Mordecai's greatness in the chronicles"
source-meaning-map: [[E18-Esther-10-1-3]]
status: "valid"
pilot: "pilot-2"
---

# E18 — Esther 10:1–3 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "esther_pericope_18_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",

  "header": {
    "bcv": "Esther 10:1-3",
    "pericope_title": "The book closes: the king's tribute and Mordecai's greatness in the chronicles",
    "book_context_ref": "esther_pilot_BCD_v0_1",
    "source_meaning_map_ref": "E18-Esther-10-1-3",
    "source_language": "Biblical Hebrew"
  },

  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "One moment-level framing override at v.2 (NARRATIVE_FRAMING axis): the chronicle-colophon formula ('are they not written in the book of the chronicles…') raises the closing voice into the archival key of an old official record, echoing the COMMUNITY_MEMORY opening-frame of the book. No social-register override: the colophon is the narrator citing a record, not a decree being voiced, so no FORMAL_OFFICIAL applies. No scene-level overrides.",
      "scene_level": null,
      "moment_level": [
        {
          "verse": "10:2",
          "framing_override": "COMMUNITY_MEMORY",
          "genre_override": null,
          "genre_group_override": null
        }
      ]
    }
  },

  "level_1": {
    "arc_elements": [
      "RECORD_SEALED",
      "CERTIFICATION",
      "PUBLIC_HONOR",
      "VINDICATION",
      "SEALING"
    ],
    "context_elements": [
      "STORY_WORLD_CONTEXT",
      "POLITICAL_CONTEXT",
      "KINSHIP_CONTEXT",
      "INSTITUTIONAL_CONTEXT",
      "AUDIENCE_KNOWLEDGE_CONTEXT",
      "HISTORICAL_ERA_CONTEXT"
    ],
    "tone_elements": [
      "SETTLED",
      "OFFICIAL",
      "QUIETLY_PROUD",
      "DECISIVE"
    ],
    "pace_elements": [
      "SLOWED",
      "WIDENS"
    ],
    "communicative_function_elements": [
      "CLOSES",
      "ESTABLISHES",
      "RECORDS",
      "ELEVATES",
      "SEALS"
    ]
  },

  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "10:1",
      "scene_kind": "NARRATOR_FRAMING_CLOSE_SCENE",
      "scene_communicative_purpose": "Re-establishes the empire's full reach and the king's standing power as the book closes — the wide frame returning at the end.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "PRESENT"
          }
        ]
      },

      "places_in_scene": {
        "_note": "Two unregistered scope referents — 'the land' (ha-aretz, the empire's mainland) and 'the sea-coasts/isles' (iyyei ha-yam, the far maritime edge) — are the spatial reach of the tribute, not named registry places. They are carried as scope atoms in the Proposition P1 event slots, not as place entries.",
        "entries": null
      },

      "objects_in_scene": {
        "_note": "The tribute (mas) is an EVENT the king imposed, not a persistent registry object (locked ruling: do not mint TH_TRIBUTE/TH_MAS). It is realized in Proposition P1 as the laying-on event.",
        "entries": null
      },

      "times_in_scene": {
        "_note": "No distinct temporal frame; the tribute is a standing closing fact of the reign, not anchored to a dated moment.",
        "entries": null
      },

      "significant_absence": "No God is named over the empire's power, as nowhere in the book. And nothing here is troubled or threatened — the tribute is stated as settled fact, with no danger, no enemy, and no crisis; the storm of the book is wholly past."
    },

    {
      "scene_id": "S2",
      "verse_range": "10:2",
      "scene_kind": "NARRATOR_FRAMING_CLOSE_SCENE",
      "scene_communicative_purpose": "Certifies the whole account as recorded imperial history and binds the king's might to Mordecai's rise — sealing the story in the official annals.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B1",
            "role_in_scene": "ELEVATED_SUBORDINATE",
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
        "entries": [
          {
            "place_id": "PL7"
          },
          {
            "place_id": "PL6"
          }
        ]
      },

      "objects_in_scene": {
        "_note": "The 'kings of Media and Persia' are the dynastic line whose annals hold the record — carried as a scope atom in the Proposition P2 slots, not as new individual cast (no B-code minted; confirm). The king's might and Mordecai's greatness are the recorded MATTER, realized as content atoms in the Proposition P2 slots, not as a registry object.",
        "entries": [
          {
            "object_id": "TH_ANNALS"
          }
        ]
      },

      "times_in_scene": {
        "_note": "No distinct temporal frame; the chronicle-formula points to a standing record, not a dated event.",
        "entries": null
      },

      "significant_absence": "The narrator points to the chronicle as proof, but God — the unnamed mover behind every reversal — is nowhere credited; the rescue is filed as plain royal history. And the formula asks \"are they not written…?\" yet shows nothing of the record's words: the content is sealed away, only pointed to."
    },

    {
      "scene_id": "S3",
      "verse_range": "10:3",
      "scene_kind": "NARRATOR_FRAMING_CLOSE_SCENE",
      "scene_communicative_purpose": "Closes the book with the portrait of Mordecai exalted yet self-giving — the once-endangered Jew now second to the throne, using his power for his people's good and peace.",

      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B1",
            "role_in_scene": "ELEVATED_SUBORDINATE",
            "presence": "PRESENT",
            "referential_form": "MORDECAI_THE_JEW"
          },
          {
            "being_id": "B4",
            "role_in_scene": "KING",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B17",
            "role_in_scene": "DELIVERED_PEOPLE",
            "presence": "REFERENCED"
          }
        ]
      },

      "places_in_scene": {
        "_note": "No place is set in v.3; the verse is a standing portrait of Mordecai's status, not a located scene.",
        "entries": null
      },

      "objects_in_scene": {
        "_note": "'Second to the king' (mishneh la-melekh) is Mordecai's rank, and 'good' (tov) and 'peace' (shalom) are what he seeks and speaks — all carried as content atoms in the Proposition P3 slots, not as registry objects. 'His brothers / his seed' (his kindred) is coextensive with B17 (the Jews seen as kin), not new cast.",
        "entries": null
      },

      "times_in_scene": {
        "_note": "No time-setting; the verse is a timeless closing characterization of Mordecai.",
        "entries": null
      },

      "significant_absence": "God is not named even here, at the summit of the deliverance: Mordecai's rise and his people's safety are stated without a word of thanks or attribution to the One the book never names. And nothing is said of any private reward or self-enrichment — his greatness is described only as turned outward, toward his people; the personal is left silent so the communal can stand."
    }
  ],

  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "10:1",
      "proposition_kind": "TRIBUTE_IMPOSED",
      "event_specific_slots": {
        "imposer": "B4",
        "imposer_standing": "KING",
        "imposed_levy": "TRIBUTE",
        "imposed_upon_land": "THE_LAND",
        "imposed_upon_coasts": "THE_SEA_COASTS"
      },
      "inter_proposition_links": {
        "forward_link_to": "P2"
      },
      "cb_flags": [],
      "figure_flags": []
    },

    {
      "prop_id": "P2",
      "scene_link": "S2",
      "verse_anchor": "10:2",
      "proposition_kind": "HEARD_REPORT",
      "event_specific_slots": {
        "citing_components": [
          {
            "action": "POINTED_TO_RECORD",
            "citer": "NARRATOR",
            "cited_record": "TH_ANNALS",
            "record_of_kings": "MEDIA_AND_PERSIA",
            "speech_act": "STATES_AS_TRUE"
          }
        ],
        "recorded_might_holder": "B4",
        "recorded_might": "POWER",
        "recorded_strength": "MIGHT",
        "recorded_elevation_target": "B1",
        "recorded_elevation_granter": "B4",
        "recorded_elevation": "GREATNESS"
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
      "scene_link": "S3",
      "verse_anchor": "10:3",
      "proposition_kind": "DECLARED",
      "event_specific_slots": {
        "characterized_one": "B1",
        "characterized_referential_form": "THE_JEW",
        "rank_held": "SECOND",
        "rank_under": "B4",
        "standing_among": "B17",
        "standing_quality": "GREAT",
        "accepted_by": "BROTHERS",
        "accepting_extent": "THE_MULTITUDE",
        "benefactive_components": [
          {
            "action": "SEEKING",
            "seeker": "B1",
            "sought_good": "GOOD",
            "whose_good": "HIS_PEOPLE",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "action": "STATED",
            "speaker": "B1",
            "spoken_peace": "PEACE",
            "addressee": "KINDRED",
            "addressee_extent": "ALL_HIS",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
      },
      "inter_proposition_links": {
        "caused_by": "P2",
        "purpose_of": {
          "components": ["benefactive_components"],
          "_note": "Mordecai's standing is oriented toward a goal — the good of his people and peace to his kindred. The benefactive seeking/speaking is the purpose-toward-which his height is turned (power-turned-to-the-people's-good, the book's last note)."
        }
      },
      "cb_flags": [],
      "figure_flags": []
    }
  ]
}
```

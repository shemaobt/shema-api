---
type: "sta-meaning-coordinates"
pericope: "E09"
pericope-title: "The summons refused, then accepted: 'who knows whether for such a time as this' and 'if I perish, I perish'"
source-meaning-map: [[E09-Esther-4-9-17]]
status: "valid"
pilot: "pilot-2"
---

# E09 — Esther 4:9–17 — MEANING_COORDINATES

This page renders the MEANING_COORDINATES JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder.

```json
{
  "sta_id": "esther_pericope_09_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "header": {
    "bcv": "Esther 4:9-17",
    "pericope_title": "The summons refused, then accepted: 'who knows whether for such a time as this' and 'if I perish, I perish'",
    "book_context_ref": "esther_pilot_BCD_v0_1",
    "source_meaning_map_ref": "E09-Esther-4-9-17",
    "source_language": "Biblical Hebrew"
  },
  "pericope_classification": {
    "genre_group": "NARRATIVE",
    "genre": "HISTORICAL_NARRATIVE",
    "register": "INFORMAL_CASUAL",
    "register_overrides": {
      "_note": "Whole passage stays INFORMAL_CASUAL — private, urgent, person-to-person messaging relayed across the gate. The v.11 death-law is Esther QUOTING the rule to explain her danger, not the king enacting a decree on-stage, so no FORMAL_OFFICIAL moment-override (Mapper's note 1, surfaced for Marcia). No COMMUNITY_MEMORY framing-lift: this is mid-book, deep in the action.",
      "scene_level": null,
      "moment_level": null
    }
  },
  "level_1": {
    "arc_elements": [
      "NEWS_RECEPTION",
      "DANGER_STATED",
      "RESOLVE_TO_ACT",
      "PROVIDENCE_QUESTION",
      "RESOLVE",
      "SELF_SURRENDER",
      "OBEDIENT_DEPARTURE"
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
      "TAUT",
      "SOBER",
      "PRESSED",
      "DECISIVE",
      "SETTLED"
    ],
    "pace_elements": [
      "BACK_AND_FORTH",
      "NARROWS",
      "SETTLES"
    ],
    "communicative_function_elements": [
      "STATES_DANGER",
      "DISMANTLES",
      "REVERSES",
      "RECORDS",
      "PLANTS",
      "CLOSES"
    ]
  },
  "level_2_scenes": [
    {
      "scene_id": "S1",
      "verse_range": "4:9-11",
      "scene_kind": "REPORT_SCENE",
      "scene_communicative_purpose": "Lays out the danger in exact legal terms: the death-law for the uncalled, the scepter as the only reprieve, and Esther's thirty days of silence — her reason she cannot simply act.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B8",
            "role_in_scene": "COURIERS",
            "presence": "PRESENT",
            "referential_form": "THE_KINGS_EUNUCH_HATHACH"
          },
          {
            "being_id": "B2",
            "role_in_scene": "QUEEN",
            "presence": "PRESENT"
          },
          {
            "being_id": "B1",
            "role_in_scene": "SUPPLIANT",
            "presence": "REFERENCED"
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
        "_note": "The inner court of the king (the lethal threshold named inside Esther's speech) is a sub-location of the palace carried as scene-content prose, not a registry place. No registry place code in this scene (per the map's Scene 1).",
        "entries": null
      },
      "objects_in_scene": {
        "_note": "The law (I2 / dat, a registered INSTITUTION) is the death-rule voiced in Prop 5 and the rule Esther resolves to break in Prop 18. The MEANING_COORDINATES scene containers have no institution slot and object_id excludes I-codes, so the law rides as bare-atom content in the propositions; its per-pericope tracking lives in the registry appears_in (E09 listed). Authoring question for Marcia: how should INSTITUTION codes be declared in a scene? The scepter (TH_SCEPTER) is the only persistent registry object here.",
        "entries": [
          {
            "object_id": "TH_SCEPTER"
          }
        ]
      },
      "times_in_scene": {
        "_note": "Thirty days (the span of Esther's not-being-summoned) is content carried inside Prop 6, not a calendar time; no registry time code.",
        "entries": null
      },
      "significant_absence": "No God is named, and none is appealed to — Esther answers the plea entirely on the ground of Persian law and royal favour, as if rescue had only human levers. The death of her people is the unstated thing the whole exchange is about, yet she names only her own risk. And there is no defiance yet: this first speech is all reasons why she cannot."
    },
    {
      "scene_id": "S2",
      "verse_range": "4:12-14",
      "scene_kind": "CHARGE_AND_PROVIDENCE_QUESTION_SCENE",
      "scene_communicative_purpose": "Dismantles every reason for silence — no exemption in the palace, no monopoly on rescue — and reframes Esther's position as possible appointment for this very hour: the book's central, God-shaped, God-unnamed question.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B1",
            "role_in_scene": "ACCUSER",
            "presence": "PRESENT"
          },
          {
            "being_id": "B2",
            "role_in_scene": "CHARGED_ONE",
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
        "entries": []
      },
      "objects_in_scene": {
        "entries": []
      },
      "times_in_scene": {
        "_note": "'This time / a time like this' (the decisive hour at the heart of Mordecai's question) is content carried inside Props 9 and 12, not a calendar time; no registry time code.",
        "entries": null
      },
      "significant_absence": "This is the loudest silence in the book. 'Relief and deliverance will arise from another place' and 'for such a time as this' both press hard toward God — yet He is never named. The certainty of rescue is stated; its source is left a blank 'other place.' Mordecai assumes a providence he does not, or will not, name."
    },
    {
      "scene_id": "S3",
      "verse_range": "4:15-16",
      "scene_kind": "CONSENT_SCENE",
      "scene_communicative_purpose": "Records the turn: Esther stops refusing and commands a three-day corporate fast, resolves to enter the king's presence in defiance of the death-law, and consents in advance to her own death — 'if I perish, I perish.'",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B2",
            "role_in_scene": "RESOLVER",
            "presence": "PRESENT"
          },
          {
            "being_id": "B1",
            "role_in_scene": "CHARGED_TO_GATHER",
            "presence": "REFERENCED"
          },
          {
            "being_id": "B17",
            "role_in_scene": "DELIVERED_PEOPLE",
            "presence": "REFERENCED"
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
        "_note": "The law (I2 / dat, a registered INSTITUTION) Esther resolves to break rides as bare-atom content in Prop 18 (against THE_LAW); the MEANING_COORDINATES scene containers have no institution slot. No persistent registry object in this scene.",
        "entries": null
      },
      "times_in_scene": {
        "_note": "'Three days, night and day' (the span of the fast) is content carried inside Props 16 and 17, not a calendar time; no registry time code.",
        "entries": null
      },
      "significant_absence": "A three-day fast is called and no prayer, no God, no reason for the fasting is stated — the religious shape is there, the religious Name is not. 'If I perish, I perish' surrenders her life without naming any hand she surrenders it into. The deliverance she fasts toward remains, as throughout, assumed and unspoken."
    },
    {
      "scene_id": "S4",
      "verse_range": "4:17",
      "scene_kind": "OBEDIENCE_CLOSING_SCENE",
      "scene_communicative_purpose": "Closes the exchange on obedience and on a quiet reversal: the one who pressed the queen now does everything the queen commands — the fast begins.",
      "beings_in_scene": {
        "entries": [
          {
            "being_id": "B1",
            "role_in_scene": "OBEYER",
            "presence": "PRESENT"
          },
          {
            "being_id": "B2",
            "role_in_scene": "COMMANDER",
            "presence": "REFERENCED"
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
        "_note": "No distinct temporal frame for this scene; the verse runs directly on from Esther's resolve.",
        "entries": null
      },
      "significant_absence": "Nothing is said of God going with Mordecai, nor of any prayer as the fast begins; the verse records only the act. And nothing is said of what comes next — the pericope ends on obedience, the outcome still hanging."
    }
  ],
  "level_3_propositions": [
    {
      "prop_id": "P1",
      "scene_link": "S1",
      "verse_anchor": "4:9",
      "proposition_kind": "ARRIVED_AT",
      "event_specific_slots": {
        "comer": "B8"
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
      "verse_anchor": "4:9",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "relayer": "B8",
        "addressee": "B2",
        "relayed_content": "WORDS",
        "original_speaker": "B1",
        "speech_act": "REPORTS_PRIOR_SPEECH_REQUEST"
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
      "verse_anchor": "4:10",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "speaker": "B2",
        "addressee": "B8"
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
      "verse_anchor": "4:10",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "charger": "B2",
        "charged_messenger": "B8",
        "message_for": "B1"
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
      "verse_anchor": "4:11",
      "proposition_kind": "DECLARED",
      "status": "NORM",
      "event_specific_slots": {
        "voiced_within": "P4",
        "knowers": ["KINGS_SERVANTS", "PROVINCE_PEOPLES"],
        "law_components": [
          {
            "bound_party": ["ANY_MAN", "ANY_WOMAN"],
            "forbidden_act": "COMES_UNSUMMONED",
            "place_entered": "INNER_COURT",
            "approached_one": "B4",
            "penalty": "DEATH",
            "speech_act": "STATES_AS_TRUE"
          },
          {
            "reprieve_condition": "SCEPTER_HELD_OUT",
            "reprieve_granter": "B4",
            "reprieve_token": "TH_SCEPTER",
            "reprieve_outcome": "LIFE",
            "speech_act": "STATES_AS_TRUE"
          }
        ]
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
      "verse_anchor": "4:11",
      "proposition_kind": "TIME_ANCHOR_ESTABLISHED",
      "status": "RECALLED",
      "event_specific_slots": {
        "voiced_within": "P4",
        "unsummoned_one": "B2",
        "to_approach": "B4",
        "interval": "THIRTY_DAYS",
        "speech_act": "STATES_AS_TRUE"
      },
      "inter_proposition_links": {
        "caused_by": "P5"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P7",
      "scene_link": "S2",
      "verse_anchor": "4:12",
      "proposition_kind": "SPOKE",
      "event_specific_slots": {
        "addressee": "B1",
        "relayed_content": "WORDS",
        "original_speaker": "B2",
        "speech_act": "REPORTS_PRIOR_SPEECH_REQUEST"
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
      "verse_anchor": "4:13",
      "proposition_kind": "ANSWERED",
      "event_specific_slots": {
        "speaker": "B1",
        "addressee": "B2",
        "warning_components": [
          {
            "warned_against": "IMAGINING_SELF_EXEMPT",
            "false_refuge": "KINGS_HOUSE",
            "exempt_from": "B17",
            "speech_act": "ADVISES_COURSE_OF_ACTION"
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
      "verse_anchor": "4:14",
      "proposition_kind": "DECLARED",
      "status": "NORM",
      "event_specific_slots": {
        "voiced_within": "P8",
        "silent_one": "B2",
        "silence_time": "THIS_TIME",
        "speech_act": "ADVISES_COURSE_OF_ACTION"
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
      "verse_anchor": "4:14",
      "proposition_kind": "GRANTED",
      "status": "FORESEEN",
      "event_specific_slots": {
        "voiced_within": "P8",
        "deliverance": ["RELIEF", "DELIVERANCE"],
        "rescued_people": "B17",
        "rescue_origin": "ANOTHER_PLACE",
        "speech_act": "ADVISES_COURSE_OF_ACTION"
      },
      "inter_proposition_links": {
        "condition_of": "P9",
        "forward_link_to": "P11"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P11",
      "scene_link": "S2",
      "verse_anchor": "4:14",
      "proposition_kind": "DECLARED",
      "status": "FORESEEN",
      "event_specific_slots": {
        "voiced_within": "P8",
        "perisher": "B2",
        "perishing_also": "FATHERS_HOUSE",
        "speech_act": "ADVISES_COURSE_OF_ACTION"
      },
      "inter_proposition_links": {
        "condition_of": "P9",
        "forward_link_to": "P12"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P12",
      "scene_link": "S2",
      "verse_anchor": "4:14",
      "proposition_kind": "PROVIDENCE_QUESTION_POSED",
      "event_specific_slots": {
        "voiced_within": "P8",
        "questioner": "B1",
        "reached_one": "B2",
        "attained_standing": "THE_KINGSHIP",
        "for_this_hour": "THIS_TIME",
        "speech_act": "ASKS_DELIBERATIVE_QUESTION"
      },
      "inter_proposition_links": {
        "caused_by": "P8"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P13",
      "scene_link": "S3",
      "verse_anchor": "4:15",
      "proposition_kind": "ANSWERED",
      "event_specific_slots": {
        "speaker": "B2",
        "addressee": "B1"
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
      "verse_anchor": "4:16",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "voiced_within": "P13",
        "commander": "B2",
        "commanded_one": "B1",
        "commanded_act": "GO",
        "speech_act": "DIRECTS_HEARER_TO_DO"
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
      "verse_anchor": "4:16",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "voiced_within": "P13",
        "commander": "B2",
        "commanded_act": "GATHER",
        "gathered": "B17",
        "gathered_at": "PL1",
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
      "scene_link": "S3",
      "verse_anchor": "4:16",
      "proposition_kind": "INSTRUCTION",
      "event_specific_slots": {
        "voiced_within": "P13",
        "commander": "B2",
        "commanded_act": "FAST",
        "fast_for": "B2",
        "abstain_from": ["EATING", "DRINKING"],
        "fast_span": "THREE_DAYS",
        "fast_continuity": "NIGHT_AND_DAY",
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
      "scene_link": "S3",
      "verse_anchor": "4:16",
      "proposition_kind": "AFFIRMED_RESOLVE",
      "event_specific_slots": {
        "voiced_within": "P13",
        "resolver": "B2",
        "fasting_also": "MY_YOUNG_WOMEN",
        "manner": "LIKEWISE",
        "speech_act": "RESOLVES_TO_ACT"
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
      "scene_link": "S3",
      "verse_anchor": "4:16",
      "proposition_kind": "AFFIRMED_RESOLVE",
      "event_specific_slots": {
        "voiced_within": "P13",
        "resolver": "B2",
        "going_in_to": "B4",
        "against": "THE_LAW",
        "speech_act": "RESOLVES_TO_ACT"
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
      "scene_link": "S3",
      "verse_anchor": "4:16",
      "proposition_kind": "AFFIRMED_RESOLVE",
      "status": "COUNTERFACTUAL",
      "event_specific_slots": {
        "voiced_within": "P13",
        "perisher": "B2",
        "perishing_condition": "IF_I_PERISH",
        "preserve_form": true,
        "speech_act": "RESOLVES_TO_ACT"
      },
      "inter_proposition_links": {
        "condition_of": "P18"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P20",
      "scene_link": "S4",
      "verse_anchor": "4:17",
      "proposition_kind": "DEPARTED",
      "event_specific_slots": {
        "passer": "B1"
      },
      "inter_proposition_links": {
        "caused_by": "P19",
        "forward_link_to": "P21"
      },
      "cb_flags": [],
      "figure_flags": []
    },
    {
      "prop_id": "P21",
      "scene_link": "S4",
      "verse_anchor": "4:17",
      "proposition_kind": "DID_AS_COMMANDED",
      "event_specific_slots": {
        "doer": "B1",
        "extent": "EVERYTHING",
        "commanded_by": "B2"
      },
      "inter_proposition_links": {
        "caused_by": "P20"
      },
      "cb_flags": [],
      "figure_flags": []
    }
  ]
}
```

---
type: "sta-compilation-log"
pericope: "P02"
pericope-title: "The return road begins; Naomi urges her daughters-in-law back; Orpah turns, Ruth clings"
source-meaning-map: [[P02-Ruth-1-6-14]]
source-meaning-coordinates: [[P02-Ruth-1-6-14-MEANING-COORDINATES]]
related-bcd-delta: [[P02-Ruth-1-6-14-BCD-DELTA]]
status: "valid"
pilot: "pilot-2"
---

# P02 — Ruth 1:6–14 — COMPILATION-LOG

This page renders the COMPILATION-LOG JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder. Registry promotions for this pericope live in the paired BCD-DELTA page.

```json
{
  "sta_id": "ruth_pericope_02_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Ruth 1:6-14",
  "pericope_id": "P02",
  "pericope_title": "The return road begins; Naomi urges her daughters-in-law back; Orpah turns, Ruth clings",
  "compiled_at": "2026-05-24",
  "review_status": {
    "meaning_map_status": "APPROVED",
    "sta_compilation_status": "PILOT_2_COMPILATION",
    "community_verified": false,
    "translation_team_verified": false,
    "consultant_review_required": false,
    "production_use": false
  },
  "confidence_overall": "MEDIUM_HIGH",
  "confidence_overall_note": "P02 compiles cleanly with 15 propositions across 3 scenes. Meaning-map P1 was split into MEANING_COORDINATES P1 (HEARD_REPORT) and P2 (VISITED_AND_PROVIDED) per Agent 1's gate-D guidance. Pericope-level register INFORMAL_CASUAL with two scene-level INTIMATE overrides on S2 and S3 (first multi-scene scene-level overrides in the pilot). First non-NONE agent_named in the pilot at P2 (B10 YHWH gives bread to B31 his people), structurally inverting P01 P2's agent_named: NONE. Naomi's lament-frame ascription at P12 names B10 again with opposite valence. FIG_0013 cross-pericope pair closes here at P2 (VERIFIED). FIG_0012 opens at P15 (DEFERRED). Two new working codes (B31, PL_LAND_OF_JUDAH) plus extensive new bounded-open vocabulary (proposition_kinds, scene_kinds, role-in-scene values, referential_forms) expected to drift-warn — none are closed-list violations.",
  "compilation_decisions": [
    {
      "decision_id": "P02-D1",
      "decision": "Pericope-level register set to INFORMAL_CASUAL with two scene-level INTIMATE overrides on S2 and S3.",
      "description": "Per hard rule, biblical narrator voice is INFORMAL_CASUAL at the pericope level. Scenes 2 and 3 carry mother-and-daughters-in-law road-side dialogue with kiss, weeping, and 'my daughters' address — INTIMATE fits the moment better than CEREMONIAL despite the institutional weight of the blessings at 1:8-9. Scene 1 (the news and the departure) stays at the narrator default. No moment-level overrides. Two scene-level overrides on consecutive scenes is a first in the pilot; documented for future scene-cascade work."
    },
    {
      "decision_id": "P02-D2",
      "decision": "Meaning-map P1 split into MEANING_COORDINATES P1 (HEARD_REPORT) and P2 (VISITED_AND_PROVIDED).",
      "description": "The meaning map's Proposition 1 conflates two structurally distinct events with different participant structures: Naomi's hearing-event (B3 hearer) and YHWH's visiting-and-providing-event (B10 agent_named, B31 recipient-collective). Per Agent 1's gate-D guidance the MEANING_COORDINATES splits them. The hearing prop carries CB_0017 (kallotehah collective). The visiting prop carries CB_0016 (paqad), CB_0012 (bread), agent_named B10, and the FIG_0013 cross-pericope closure. Inter-prop link: hearing.forward_link_to = P3 (departure); visiting.paired_with = P1 (hearing references its content). The content-reference itself is encoded inside event_specific_slots as report_content_link on the hearing prop, because the inter_proposition_links schema is closed and admits no new key."
    },
    {
      "decision_id": "P02-D3",
      "decision": "First non-NONE agent_named in the pilot at P2 (B10 YHWH).",
      "description": "P01's three death-and-affliction events (P2, P7, P12) all carried agent_named: NONE per source-text discipline (narrator withholds divine agency). P02 P2 names YHWH as the agent of visiting and providing — the first explicit divine agency in the book. Structurally encoded as agent_named: B10. The contrast with P01's pattern is intentional and recorded under high_risk_register_audit as STRUCTURAL_DIVINE_AGENCY_FIRST_NAMED."
    },
    {
      "decision_id": "P02-D4",
      "decision": "Same B10 invoked with opposite valence at P12 lament-frame.",
      "description": "Naomi's 'the hand of YHWH has gone out against me' at 1:13 ascribes her bitterness to the same divine agent who has just given bread to his people in Judah. agent_named: B10 appears within the lament_components ASCRIBED_BITTERNESS_TO_DIVINE_AGENT record (speech_act: ASCRIBES_AFFLICTION_TO_GOD_IN_LAMENT). The opposite-valence pairing is structurally significant: the same divine subject is named as provider at the pericope's opening and as antagonist at the pericope's near-close. Recorded as a STRUCTURAL_CONTRAST high-risk entry."
    },
    {
      "decision_id": "P02-D5",
      "decision": "Blessing speech_act set to WISHES_FOR_HEARER for both P5 and P6.",
      "description": "Both blessings (hesed at 1:8b, rest at 1:9a) take WISHES_FOR_HEARER per the closed list. The wished-for state (receiving hesed; finding rest) is for the daughters-in-law as hearers. YHWH is the invoked agent of the wished-for state, not the beneficiary of the wish. Speech_act follows the beneficiary, not the invoked agent. WISHES_FOR_THIRD_PARTY would apply only if the beneficiary were a third party (e.g., 'may YHWH bless the dead'); that is not the case here. INVOKES_DIVINE_AS_OATH_GUARANTOR does not apply (this is not an oath)."
    },
    {
      "decision_id": "P02-D6",
      "decision": "Wife-pairing withholding from P01 carried forward at P5 prior-hesed clause.",
      "description": "Naomi's 'as you have dealt with the dead and with me' at 1:8 references B2, B4, B5 collectively as 'the dead.' P01 P9 withheld the Mahlon-Ruth and Chilion-Orpah pairings (wife_taken: B?), with pairing disclosure deferred to 4:10. Source-text discipline at P02 maintains the withholding: prior_hesed_targets is encoded as the unordered collection [B2, B4, B5, B3] (the three deceased plus Naomi as the additional referent), with prior_hesed_targets_referential_form: THE_DEAD_AND_NAOMI. The reconstructor must not infer which daughter-in-law's hesed went to which dead husband."
    },
    {
      "decision_id": "P02-D7",
      "decision": "New B-code B31-People-of-YHWH registered for the Israelite people-collective.",
      "description": "The narrator at 1:6 says YHWH 'visited his people' (עַמּוֹ); Naomi at 1:10 names 'your people' (לְעַמֵּךְ) as her destination. The referent is the Israelite people-collective. A B-code is registered to represent this referenced participant. Kind: COLLECTIVE_PEOPLE. Ethnic identity: ISRAELITE. First appearance: 1:6. Will recur in later pericopes. The decision was handed to Agent 2 at gate A as 'assess or defer'; Agent 2 chose to propose the B-code; Agent 1 accepted at gate C. The page B31-People-of-YHWH will be created at write-back."
    },
    {
      "decision_id": "P02-D8",
      "decision": "New working code PL_LAND_OF_JUDAH for 'the land of Judah' at 1:7.",
      "description": "The narrator at 1:7 names אֶרֶץ יְהוּדָה (the land of Judah) as the destination of the return road, broader than PL1-Bethlehem-of-Judah (specific town, arrival in P03) and narrower than PL_ISRAEL (the whole land). PL_LAND_OF_JUDAH is used here as a working code parallel to P01's PL_HA_ARETZ pattern, pending formal PL-code assignment in BCD v0.4. Kind: COVENANT_TERRITORY. Recorded as known_limitations entry."
    },
    {
      "decision_id": "P02-D9",
      "decision": "'The road' encoded as a structural object (TH_THE_RETURN_ROAD), not a registered place.",
      "description": "The narrative locus of all three scenes is the road from Moab to Judah (בַּדֶּרֶךְ at 1:7). Rather than register a new place code for the road, the road is encoded as a TH_-prefixed structural object (TH_THE_RETURN_ROAD) appearing in objects_in_scene across S1, S2, S3. Rationale: the road is a movement-trajectory more than a named place; PL_LAND_OF_JUDAH is the destination, PL2 is the departure point, and the road between them is the connecting structural element. Avoids unnecessary registry expansion."
    },
    {
      "decision_id": "P02-D10",
      "decision": "Inter-proposition link from hearing to visiting encoded inside event_specific_slots.",
      "description": "The semantic relationship between MEANING_COORDINATES P1 (hearing) and P2 (visiting) is 'P1 references the content of P2.' The validation-rules.json inter_proposition_links schema is closed (additionalProperties: false; admits only caused_by, forward_link_to, paired_with, purposed_for, back_reference_to_proposition). No existing key cleanly fits the content-reference relation. The structural reference is therefore encoded inside event_specific_slots as report_content_link: P2 on the hearing prop. Inter_proposition_links uses paired_with: P1 on the visiting prop to mark the pairing structurally. This preserves both the structural relation and the schema constraint."
    },
    {
      "decision_id": "P02-D11",
      "decision": "Orpah's exit from the book encoded as referential_form change at S3 plus narrative_status marker on P14.",
      "description": "At 1:14 the narrator names Orpah's act using the kinship form לַחֲמוֹתָהּ (her mother-in-law) rather than addressing Orpah by name. After 1:14 Orpah is not named again in the book. The structural exit is encoded by: (a) referential_form on B8 in S3 beings_in_scene as HER_MOTHER_IN_LAW; (b) narrative_status: EXITS_BOOK_HERE on the TURNED_BACK component of P14. High-risk register entry uses kind NAMING_SHIFT with exit-marker note."
    },
    {
      "decision_id": "P02-D12",
      "decision": "Cross-pericope pair verification status: FIG_0013 VERIFIED, FIG_0012 DEFERRED.",
      "description": "FIG_0013 BREAD_HOUSE_IN_FAMINE opened at P01 Proposition 2 (1:1) and closes at P02 P2 (1:6). The cross-pericope pair is now verifiable: bread (לָחֶם) appears in both with the structural reversal preserved (famine in the bread-house at 1:1; YHWH gives bread to his people at 1:6). VERIFIED. FIG_0012 CLINGING_DABAQ_IMAGE_RHYME opens at P02 P15 (1:14). Cross-pericope pair will close at P07 (2:23). Verification DEFERRED pending P07 compilation."
    }
  ],
  "vocabulary_additions": {
    "action_values": [
      { "value": "AROSE_TO_RETURN", "source": "first introduced in P02 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "ASCRIBED", "source": "first introduced in P02 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "ASKED", "source": "first introduced in P02 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "DIRECTED", "source": "first introduced in P02 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "KISSED", "source": "first introduced in P02 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "STATED", "source": "first introduced in P02 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "TURNED_BACK", "source": "first introduced in P02 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "WALKED", "source": "first introduced in P02 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "WENT_OUT", "source": "first introduced in P02 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "WEPT_ALOUD", "source": "first introduced in P02 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" }
    ],
    "proposition_kinds": [
      {
        "value": "APPEAL",
        "source": "P4 1:8a",
        "status": "PROPOSED"
      },
      {
        "value": "BLESSING",
        "source": "P5 1:8b",
        "status": "PROPOSED"
      },
      {
        "value": "CLUNG_TO",
        "source": "P15 1:14c",
        "status": "PROPOSED"
      },
      {
        "value": "DEPARTED",
        "source": "P14 1:14b",
        "status": "PROPOSED"
      },
      {
        "value": "GAVE",
        "source": "P2 1:6b",
        "status": "PROPOSED"
      },
      {
        "value": "HEARD_REPORT",
        "source": "P1 1:6a",
        "status": "PROPOSED"
      },
      {
        "value": "KISSED",
        "source": "P7 1:9b",
        "status": "PROPOSED"
      },
      {
        "value": "LAMENT",
        "source": "P12 1:13d",
        "status": "PROPOSED"
      },
      {
        "value": "RETURNED",
        "source": "P3 1:6b-7",
        "status": "PROPOSED"
      },
      {
        "value": "SPOKE",
        "source": "P8 1:10",
        "status": "PROPOSED"
      },
      {
        "value": "WEPT",
        "source": "P13 1:14a",
        "status": "PROPOSED"
      }
    ],
    "scene_kinds": [
      {
        "value": "APPEAL_SCENE",
        "source": "S2 1:8-10",
        "status": "PROPOSED"
      },
      {
        "value": "DEPARTURE_SCENE",
        "source": "S1 1:6-7",
        "status": "PROPOSED"
      }
    ],
    "presence_values": [],
    "role_in_scene_beings": [
      {
        "value": "DIVINE_AGENT",
        "source": "B10 @S1",
        "status": "PROPOSED"
      },
      {
        "value": "PEOPLE",
        "source": "B31 @S1",
        "status": "PROPOSED"
      }
    ],
    "arc_elements": [
      { "value": "NEWS_RECEPTION", "source": "S1 1:6a Naomi hears in Moab that YHWH gave bread", "status": "PROPOSED" },
      { "value": "RETURN_INITIATED", "source": "S1 1:6b-7 arising to return from the fields of Moab", "status": "PROPOSED" },
      { "value": "BLESSING_APPEAL", "source": "S2 1:8-9 directive-and-blessing appeal to turn back", "status": "PROPOSED" },
      { "value": "ARGUED_DISMISSAL", "source": "S3 1:11-13 Naomi's expanded dissuasive appeal", "status": "PROPOSED" },
      { "value": "SEPARATION_AND_CHOICE", "source": "S3 1:14 Orpah turns back; the ways divide", "status": "PROPOSED" },
      { "value": "CLINGING", "source": "S3 1:14c Ruth clings (davqah)", "status": "PROPOSED" }
    ],
    "context_elements": [],
    "tone_elements": [
      { "value": "URGENT", "source": "S2-S3 1:8-13 Naomi's repeated directives to return", "status": "CONFIRMED" }
    ],
    "pace_elements": [
      { "value": "BRISK", "source": "S1 1:6-7 compressed hearing-and-departure", "status": "CONFIRMED" },
      { "value": "SLOWED", "source": "S2-S3 1:8-14 extended dialogue slows the pace", "status": "CONFIRMED" }
    ],
    "communicative_function_elements": [
      {
        "value": "CLOSES",
        "source": "level_1 communicative_function_elements",
        "status": "PROPOSED"
      }
    ],
    "high_risk_register_kinds": [
      { "value": "STRUCTURAL_DIVINE_AGENCY_FIRST_NAMED", "source": "R1: agent_named B10 on P2 (1:6)", "status": "PROPOSED" },
      { "value": "CROSS_PERICOPE_PAIRING_CLOSED_HERE", "source": "R2: FIG_0013 BREAD_HOUSE_IN_FAMINE closes at P2", "status": "PROPOSED" },
      { "value": "STRUCTURAL_DIVINE_ATTRIBUTION_IN_LAMENT", "source": "R3: B10 inside lament_components on P12 (1:13)", "status": "PROPOSED" },
      { "value": "PROVIDENTIAL_ANSWER_RECEIVED", "source": "R11: FIG_0013 closure answers the P01 irony", "status": "PROPOSED" },
      { "value": "REFERENTIAL_FORM_CHANGE", "source": "R15: kallotehah collective form tracking across S1-S3", "status": "PROPOSED" }
    ],
    "referential_forms": [
      {
        "value": "HER_MOTHER_IN_LAW",
        "source": "B8 at S3 / 1:14 (Orpah named only as 'her mother-in-law' at exit)",
        "status": "PROPOSED",
        "note": "Exit-marker referential form. Bounded-open."
      }
    ],
    "other": [
      {
        "category": "PLACE_KIND",
        "value": "COVENANT_TERRITORY",
        "source": "PL_LAND_OF_JUDAH at 1:7 (carries forward from PL_HA_ARETZ at P01)",
        "status": "CONFIRMED"
      },
      {
        "category": "BEING_KIND",
        "value": "COLLECTIVE_PEOPLE",
        "source": "B31 at 1:6",
        "status": "PROPOSED",
        "note": "First time a being_kind COLLECTIVE_PEOPLE is registered. Bounded-open."
      },
      {
        "category": "OBJECT_KIND",
        "value": "COVENANT_REMEMBRANCE_VERB",
        "source": "TH_PAQAD_VISITED_VERB at 1:6",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "COVENANT_PROVISION_PHRASE",
        "source": "TH_GIVE_BREAD_PROVISION at 1:6",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "AURAL_RECEPTION_FORMULA",
        "source": "TH_HEARING_FORMULA at 1:6",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "PAIRED_DEPARTURE_VERBS",
        "source": "TH_AROSE_AND_RETURNED_VERB_PAIR at 1:6",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "JOURNEY_LOCUS",
        "source": "TH_THE_RETURN_ROAD at 1:7",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "KINSHIP_COLLECTIVE_FORM",
        "source": "TH_KALLOTEHAH_COLLECTIVE_FORM at 1:6",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "DIRECTIVE_WITH_DISTRIBUTIVE_DESTINATION",
        "source": "TH_DIRECTIVE_GO_RETURN_TO_MOTHERS_HOUSE at 1:8",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "BLESSING_FORMULA",
        "source": "TH_HESED_BLESSING_FORMULA at 1:8; TH_REST_BLESSING_FORMULA at 1:9",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "BLESSING_GROUNDING_CLAUSE",
        "source": "TH_PRIOR_HESED_GROUNDING_CLAUSE at 1:8",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "DISTRIBUTIVE_HYPOTHETICAL_HOUSEHOLD",
        "source": "TH_HUSBANDS_HOUSE_DISTRIBUTIVE at 1:9",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "PHYSICAL_FAREWELL_GESTURE",
        "source": "TH_NAOMI_KISS_FAREWELL at 1:9",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "VOCAL_WEEPING_FORMULA",
        "source": "TH_WEEPING_FORMULA_FIRST at 1:9; TH_WEEPING_FORMULA_AGAIN at 1:14",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "REFUSAL_WITH_COUNTER_DECLARATION_FORMULA",
        "source": "TH_REFUSAL_COUNTER_DECLARATION at 1:10",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "REPEATED_DIRECTIVE_WITH_ADDRESS_FORM",
        "source": "TH_TURN_BACK_REPEATED_DIRECTIVE at 1:11-12",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "RHETORICAL_QUESTION_OF_DISSUASION",
        "source": "TH_WOMB_RHETORICAL_QUESTION at 1:11; TH_WAIT_/RESTRAIN_RHETORICAL_QUESTION at 1:13",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "PERSONAL_IMPOSSIBILITY_STATEMENT",
        "source": "TH_AGE_IMPOSSIBILITY_STATEMENT at 1:12",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "HYPOTHETICAL_EXTREME_CASE_CONCESSION",
        "source": "TH_TONIGHT_HYPOTHETICAL_HUSBAND at 1:12",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "HYPOTHETICAL_IMAGINED_OUTCOME",
        "source": "TH_HYPOTHETICAL_BORN_SONS at 1:12",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "LAMENT_OBSERVATION_COMPARISON",
        "source": "TH_BITTERNESS_COMPARISON at 1:13",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "LAMENT_FRAME_DIVINE_ASCRIPTION",
        "source": "TH_HAND_OF_YHWH_LAMENT_ASCRIPTION at 1:13",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "EXIT_FAREWELL_KISS_WITH_KINSHIP_FORM",
        "source": "TH_ORPAH_KISS_FAREWELL at 1:14",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "CLINGING_VERB_FIRST_OCCURRENCE",
        "source": "TH_DAVQAH_CLINGING_VERB at 1:14",
        "status": "PROPOSED"
      }
    ]
  },
  "proposition_kind_slot_sets": [
    {
      "proposition_kind": "HEARD_REPORT",
      "slot_set": [
        "hearer",
        "where",
        "report_content_link",
        "report_reception_form"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P1"
      ],
      "note": "report_content_link names the MEANING_COORDINATES prop that holds the content of what was heard; encodes structural cross-reference inside event_specific_slots because the inter_proposition_links schema is closed."
    },
    {
      "proposition_kind": "VISITED_AND_PROVIDED",
      "slot_set": [
        "agent_named",
        "people_provided_for",
        "provision_kind",
        "where_implied",
        "covenant_action_verb_form",
        "provision_phrase_form"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P2"
      ]
    },
    {
      "proposition_kind": "RETURNED_FROM_FOREIGN_RESIDENCE",
      "slot_set": [
        "departure_components",
        "departure_verb_pair_form"
      ],
      "component_record_shape": {
        "action": "required — AROSE_TO_RETURN | WENT_OUT_FROM_PLACE_OF_RESIDENCE | WALKED_ON_RETURN_ROAD",
        "subject": "required for single-subject actions",
        "subjects": "required for collective actions",
        "accompanying_household": "conditional",
        "from_place": "conditional",
        "via": "conditional",
        "destination": "conditional",
        "speech_act": "required — STATES_AS_TRUE for narrator chronicle"
      },
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P3"
      ]
    },
    {
      "proposition_kind": "SPOKE_DIRECTIVE_TO_RETURN",
      "slot_set": [
        "speaker",
        "addressees",
        "directive_content_form",
        "return_destination_distributive",
        "speech_act"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P4"
      ]
    },
    {
      "proposition_kind": "PRONOUNCED_BLESSING",
      "slot_set": [
        "blesser",
        "blessing_recipients",
        "invoked_divine_agent",
        "blessing_content_kind",
        "blessing_phrase_form",
        "speech_act"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P5",
        "P6"
      ],
      "note": "P5 also carries grounding_clause_form, prior_hesed_targets, prior_hesed_targets_referential_form (the prior-hesed grounding clause). P6 also carries blessing_locus_distributive_form (the husband's house). Speech_act on both is WISHES_FOR_HEARER per P02-D5."
    },
    {
      "proposition_kind": "KISSED_AND_WEPT_FAREWELL",
      "slot_set": [
        "farewell_components"
      ],
      "component_record_shape": {
        "action": "required — KISSED | WEPT_ALOUD",
        "kisser": "required for KISSED",
        "kissed": "required for KISSED",
        "weepers": "required for WEPT_ALOUD",
        "kiss_form": "conditional",
        "weeping_form": "conditional",
        "speech_act": "required — STATES_AS_TRUE"
      },
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P7"
      ]
    },
    {
      "proposition_kind": "REFUSED_WITH_COUNTER_DECLARATION",
      "slot_set": [
        "refusers",
        "addressee_of_refusal",
        "refusal_target_proposition",
        "counter_action",
        "counter_destination_collective",
        "refusal_phrase_form",
        "speech_act"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P8"
      ]
    },
    {
      "proposition_kind": "SPOKE_DISSUASIVE_APPEAL",
      "slot_set": [
        "speaker",
        "addressees",
        "address_form",
        "appeal_components",
        "dissuasion_target"
      ],
      "component_record_shape": {
        "action": "required — REPEATED_DIRECTIVE | ASKED_DISSUASIVE_QUESTION | STATED_PERSONAL_IMPOSSIBILITY | GRANTED_HYPOTHETICAL_CONCESSION",
        "speech_act": "required — DIRECTS_HEARER_TO_RETURN | ASKS_RHETORICAL_QUESTION_AS_DISSUASION | STATES_AS_TRUE"
      },
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P9"
      ]
    },
    {
      "proposition_kind": "SPOKE_HYPOTHETICAL_DISSUASION",
      "slot_set": [
        "speaker",
        "addressees",
        "address_form",
        "appeal_components"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P10"
      ],
      "note": "Same component shape as SPOKE_DISSUASIVE_APPEAL; second-appeal expanded form."
    },
    {
      "proposition_kind": "ASKED_TWIN_DISSUASIVE_QUESTIONS",
      "slot_set": [
        "speaker",
        "addressees",
        "question_components",
        "dissuasion_target"
      ],
      "component_record_shape": {
        "question_subject": "required",
        "question_form": "required — TH_* form code",
        "list_position": "required — FIRST | SECOND",
        "speech_act": "required — ASKS_RHETORICAL_QUESTION_AS_DISSUASION"
      },
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P11"
      ]
    },
    {
      "proposition_kind": "SPOKE_LAMENT_WITH_DIVINE_ATTRIBUTION",
      "slot_set": [
        "speaker",
        "addressees",
        "address_form",
        "lament_components"
      ],
      "component_record_shape": {
        "action": "required — STATED_BITTERNESS_COMPARISON | ASCRIBED_BITTERNESS_TO_DIVINE_AGENT",
        "agent_named": "required for ASCRIBED_BITTERNESS_TO_DIVINE_AGENT",
        "speech_act": "required — STATES_LAMENT_OBSERVATION | ASCRIBES_AFFLICTION_TO_GOD_IN_LAMENT"
      },
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P12"
      ]
    },
    {
      "proposition_kind": "WEPT_AGAIN",
      "slot_set": [
        "weepers",
        "weeping_form",
        "parallel_with_proposition"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P13"
      ]
    },
    {
      "proposition_kind": "KISSED_AND_DEPARTED",
      "slot_set": [
        "departure_components"
      ],
      "component_record_shape": {
        "action": "required — KISSED | TURNED_BACK",
        "kisser": "required for KISSED",
        "kissed": "required for KISSED",
        "kissed_referential_form": "conditional",
        "kiss_form": "conditional",
        "subject": "required for TURNED_BACK",
        "narrative_status": "conditional",
        "speech_act": "required — STATES_AS_TRUE"
      },
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P14"
      ]
    },
    {
      "proposition_kind": "CLUNG_TO",
      "slot_set": [
        "clinger",
        "clung_to",
        "clinging_verb_form",
        "contrast_with_proposition"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P15"
      ]
    }
  ],
  "high_risk_register_audit": [
    {
      "id": "R1",
      "kind": "STRUCTURAL_DIVINE_AGENCY_FIRST_NAMED",
      "applies_to": "agent_named: B10 on P2 (VISITED_AND_PROVIDED) at 1:6",
      "note": "First non-NONE agent_named in the pilot. Structural inverse of P01's three NONE-agent events (P01 P2 famine, P7 Elimelech's death, P12 sons' deaths). Reconstructor must preserve the divine subject as the agent of bread-provision.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3C Scene 1 Objects (TH_PAQAD_VISITED_VERB; TH_GIVE_BREAD_PROVISION); Section 3E Scene 1 What Happens"
    },
    {
      "id": "R2",
      "kind": "CROSS_PERICOPE_PAIRING_CLOSED_HERE",
      "applies_to": "FIG_0013 BREAD_HOUSE_IN_FAMINE closes at P2",
      "note": "PREFERRED keep-image. The 'house of bread' irony opened at P01 P2 (1:1) closes here: YHWH gives bread to his people. The structural reversal must remain visible — same lechem-key as the 1:1 ra'av frame. Cross-pericope pair verified.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3C Scene 1 Objects (TH_GIVE_BREAD_PROVISION cross-ref to FIG_0013); Section 5B Figure Flags"
    },
    {
      "id": "R3",
      "kind": "STRUCTURAL_DIVINE_ATTRIBUTION_IN_LAMENT",
      "applies_to": "agent_named: B10 inside lament_components on P12 (1:13)",
      "note": "Naomi's lament-frame ascription: 'the hand of YHWH has gone out against me.' Same divine subject as P2, opposite valence in Naomi's perception. Reconstructor must not soften or generalize the attribution; it is Naomi's voice naming YHWH as the agent of her bitterness.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3C Scene 3 Objects (TH_HAND_OF_YHWH_LAMENT_ASCRIPTION); Section 3E Scene 3 What Happens"
    },
    {
      "id": "R4",
      "kind": "STRUCTURAL_CONTRAST",
      "applies_to": "B10 as bread-giver at P2 (1:6) vs. B10 as hand-against-Naomi at P12 (1:13)",
      "note": "Same divine subject named at two valences within the pericope. The structural pairing is the first instance in the book of YHWH-as-provider and YHWH-as-named-agent-of-affliction occurring back-to-back. Reconstructor must allow both framings to remain visible.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 2.4 Communicative Function; Section 3C Scenes 1 and 3 Objects"
    },
    {
      "id": "R5",
      "kind": "WITHHELD_PAIRING_PER_SOURCE_DISCIPLINE",
      "applies_to": "prior_hesed_targets on P5 (B2, B4, B5, B3) without husband-wife pairing",
      "note": "Naomi's hesed-blessing grounding clause references the daughters' prior hesed 'toward the dead and toward me' without disclosing which daughter-in-law's hesed went to which deceased husband. Pairing remains withheld per P01-D2 carry-forward. Disclosure deferred to 4:10.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3C Scene 2 Objects (TH_PRIOR_HESED_GROUNDING_CLAUSE); Section 4 Proposition 4"
    },
    {
      "id": "R6",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0012 CLINGING_DABAQ_IMAGE_RHYME opens at P15 (1:14)",
      "note": "PREFERRED keep-image. First occurrence of the dabaq root in the book. Cross-pericope image-rhyme will close at P07 (2:23). Reconstructor must use a clinging-verb form that can recur at 2:23 with the same root-resonance audible.",
      "required_in_audit": true,
      "carries_forward_to": "P07_audit",
      "source_in_meaning_map": "Section 5B Figure Flags; Section 3C Scene 3 Objects (TH_DAVQAH_CLINGING_VERB)"
    },
    {
      "id": "R7",
      "kind": "NAMING_SHIFT",
      "applies_to": "B8 Orpah at 1:14 — named only as 'her mother-in-law' (kinship form) at her exit; never named again in the book",
      "note": "Narrator uses the kinship form לַחֲמוֹתָהּ (her mother-in-law) at Orpah's exit moment rather than her personal name. After 1:14 Orpah is not named again. The kinship-only reference is the structural marker of her exit. Reconstructor may preserve the kinship form or use Orpah's name; either way, the exit-finality must be visible.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3A Scene 3 (B8 referential_form); Section 3C Scene 3 Objects (TH_ORPAH_KISS_FAREWELL)"
    },
    {
      "id": "R8",
      "kind": "STRUCTURAL_ABSENCE_OF_OFFSPRING",
      "applies_to": "Naomi's womb-rhetorical question at P9 (1:11): 'are there yet sons in my womb?'",
      "note": "Naomi articulates the absence of offspring through her own womb-question, dissuading the daughters by exposing impossibility. Structurally advances T2 (line-of-Elimelech) by Naomi's own negation. Reconstructor must not soften the rhetorical force.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3C Scene 3 Objects (TH_WOMB_RHETORICAL_QUESTION); Section 4 Proposition 8"
    },
    {
      "id": "R9",
      "kind": "DISCOURSE_THREAD_OPENED",
      "applies_to": "T3 OPENED at 1:9; T4 OPENED at 1:8; T6 OPENED at 1:6",
      "note": "Three book-spanning threads open in this pericope. T6 (divine action) at 1:6, T4 (hesed answered with hesed) at 1:8, T3 (rest in a husband's house) at 1:9. Each opens at a verse named by the narrative or Naomi's speech.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 2.4 Communicative Function; tracked in AUDIT registry_additions.to_bcd.discourse_thread_events"
    },
    {
      "id": "R10",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "Blessing form across P5 and P6 (1:8-9)",
      "note": "Naomi's double blessing is the first occurrence of the institutional blessing pattern in the book. CB_0008 first activates here. Other blessing forms recur at 2:4, 2:12, 2:20, 3:10, 4:11-12, 4:14-15 with structural-intertextual freight. The P02 blessings are spoken in INTIMATE register (mother-in-law to daughters-in-law on the road) but carry institutional weight at the form level.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3C Scene 2 Objects (TH_HESED_BLESSING_FORMULA; TH_REST_BLESSING_FORMULA)"
    },
    {
      "id": "R11",
      "kind": "PROVIDENTIAL_ANSWER_RECEIVED",
      "applies_to": "FIG_0013 closure at P2 answers the irony opened at P01 P2",
      "note": "The famine-in-the-bread-house irony at 1:1 receives its providential answer at 1:6 when YHWH gives bread to his people. The cross-pericope arc is closed within P02 by the narrator's report.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 2.4 Communicative Function; Section 3C Scene 1 Objects (TH_GIVE_BREAD_PROVISION)"
    },
    {
      "id": "R12",
      "kind": "CROSS_OCCURRENCE_INTRA_PERICOPE",
      "applies_to": "VOCAL_WEEPING_FORMULA at 1:9 (P7) and 1:14 (P13)",
      "note": "Same weeping formula occurs at both appeals. The second occurrence is marked with 'again' (עוֹד), making the parallel structural. Reconstructor should preserve the parallel form across both verses.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3C Scene 2 Objects (TH_WEEPING_FORMULA_FIRST); Section 3C Scene 3 Objects (TH_WEEPING_FORMULA_AGAIN)"
    },
    {
      "id": "R13",
      "kind": "CROSS_OCCURRENCE_INTRA_PERICOPE",
      "applies_to": "Kissing at 1:9 (P7 — Naomi to daughters) and 1:14 (P14 — Orpah to Naomi)",
      "note": "The kiss as gesture recurs with reversed direction. Naomi's kiss at v.9 marks farewell-as-release; Orpah's kiss at v.14 marks farewell-as-departure. The reversal is part of the structural pairing.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3C Scene 2 Objects (TH_NAOMI_KISS_FAREWELL); Section 3C Scene 3 Objects (TH_ORPAH_KISS_FAREWELL)"
    },
    {
      "id": "R14",
      "kind": "STRUCTURAL_CONTRAST",
      "applies_to": "Orpah's exit (P14) vs. Ruth's clinging (P15) on the single verse 1:14",
      "note": "Two parallel acts on one verse define the divergence of the two daughters' paths. Orpah's act closes her arc in the book; Ruth's act opens the rest of the book's trajectory. The contrast must remain visible in reconstruction.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 3 What Happens; Section 4 Propositions 13 and 14"
    },
    {
      "id": "R15",
      "kind": "REFERENTIAL_FORM_CHANGE",
      "applies_to": "Kallotehah collective form (1:6, 1:7, 1:8) used for B8 and B9 jointly",
      "note": "The collective in-law kinship form is sustained across S1 and into the opening of S2 (Naomi's address). At 1:14 the form differentiates: Orpah is named, Ruth is named, and the kinship form is used for B3 from Orpah's side (לַחֲמוֹתָהּ). The form-tracking matters for the in-law relation across the book.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3C Scene 1 Objects (TH_KALLOTEHAH_COLLECTIVE_FORM)"
    }
  ],
  "cross_pericope_pair_verification": {
    "pairs": [
      {
        "fig_id": "FIG_0013",
        "opens_at": "P01 P2 (1:1)",
        "closes_at": "P02 P2 (1:6)",
        "verification_status": "VERIFIED",
        "note": "Cross-pericope pair now verifiable: the irony of the bread-house in famine opened at P01 P2 closes at P02 P2 with YHWH's gift of bread. Both occurrences use the lechem-key (P01: famine in beit lechem; P02: YHWH gives lechem). Reactivated at P04 (1:22, the return to Bethlehem) pending P04 compilation."
      },
      {
        "fig_id": "FIG_0012",
        "opens_at": "P02 P15 (1:14)",
        "closes_at": "P07 (2:23)",
        "verification_status": "DEFERRED",
        "note": "Ruth's clinging at 1:14 opens the dabaq image-rhyme; will close at 2:23 when the same root tags Ruth's staying-close to Boaz's young women. P07 not yet compiled under Pilot 2."
      },
      {
        "fig_id": "FIG_0001",
        "opens_at": "P01 P10 (1:4)",
        "closes_at": "Recurs at P04 P05 P07 P11 P12",
        "verification_status": "DEFERRED",
        "note": "Carries forward from P01. The Moabite epithet does not surface in narrator voice in P02; CB_0004 active at P8, P14, P15 (refusal, Orpah exit, Ruth cling) marks the ethnic-identity question as still in play."
      }
    ]
  },
  "validation_checklist": {
    "meaning_map_contains_only_story_content": true,
    "meaning_coordinates_contains_only_inference_signal": true,
    "every_proposition_has_cb_flags_and_figure_flags": true,
    "every_being_in_propositions_declared_in_scenes": true,
    "every_place_in_propositions_declared_in_scenes": true,
    "every_object_in_propositions_declared_in_scenes": true,
    "every_time_in_propositions_declared_in_scenes": true,
    "no_grammatical_frame_slot_names": true,
    "speech_act_present_on_all_component_records": true,
    "speech_act_values_used": [
      "STATES_AS_TRUE",
      "DIRECTS_HEARER_TO_RETURN",
      "WISHES_FOR_HEARER",
      "REFUSES_REQUEST_WITH_COUNTER_DECLARATION",
      "ASKS_RHETORICAL_QUESTION_AS_DISSUASION",
      "STATES_LAMENT_OBSERVATION",
      "ASCRIBES_AFFLICTION_TO_GOD_IN_LAMENT"
    ],
    "negation_not_double_encoded": "N/A — no DIRECTS_HEARER_NOT_TO_DO in P02 (no negative directives)",
    "cross_pericope_cross_refs_present_on_correct_propositions": true,
    "empty_slot_rule_applied_to_times_in_scene": true,
    "discourse_threads_tracked_in_audit_only": true,
    "known_limitations_tracked_in_audit_only": true,
    "high_risk_register_complete": true,
    "every_high_risk_entry_traces_to_meaning_map": true,
    "significant_absences_traced_to_meaning_map": true,
    "no_content_added_beyond_meaning_map": true,
    "wife_pairing_withholding_enforced": true,
    "b_codes_match_bcd_version": "All B-codes verified against ruth_pilot_BCD_v0_3 plus new B31 (registered here)",
    "registry_additions_extracted_to_bcd_delta": true,
    "no_reviewer_facing_prompts_in_compilation_log": true
  },
  "known_limitations": [
    "PL_LAND_OF_JUDAH used as a working code pending formal PL-code assignment in BCD v0.4 (parallel to P01's PL_HA_ARETZ pattern).",
    "B31-People-of-YHWH newly registered at P02; the wiki page B31-People-of-YHWH will be created at write-back.",
    "Cross-pericope pair verification for FIG_0012 and FIG_0001 deferred pending later pericope compilations.",
    "Wife pairings from P01 1:4 remain withheld; carried forward at P5 prior-hesed grounding clause. Disclosure deferred to 4:10 (P13 compilation).",
    "Large number of bounded-open vocabulary additions (proposition_kinds, scene_kinds, role-in-scene values, object kinds) reflect this pericope's dialogue density. All will drift-warn against the canonical P01 seed — that is expected for the first dialogue-heavy pericope.",
    "Inter-proposition link from hearing (P1) to visiting (P2) encoded inside event_specific_slots as report_content_link because the inter_proposition_links schema is closed; pattern documented in P02-D10 for future dialogue compilations.",
    "Three working object_kinds added without first being registered as bounded-open enumerations (e.g., BLESSING_FORMULA, RHETORICAL_QUESTION_OF_DISSUASION). Future BCD work may consolidate these.",
    "community_verified and translation_team_verified remain false; this is a pilot compilation."
  ]
}
```

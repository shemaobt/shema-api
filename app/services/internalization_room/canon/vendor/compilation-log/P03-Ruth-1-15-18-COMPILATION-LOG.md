---
type: "sta-compilation-log"
pericope: "P03"
pericope-title: "Naomi's last appeal; Ruth's vow; Naomi's silence"
source-meaning-map: [[P03-Ruth-1-15-18]]
source-meaning-coordinates: [[P03-Ruth-1-15-18-MEANING-COORDINATES]]
related-bcd-delta: [[P03-Ruth-1-15-18-BCD-DELTA]]
status: "valid"
pilot: "pilot-2"
---

# P03 — Ruth 1:15–18 — COMPILATION-LOG

This page renders the COMPILATION-LOG JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder. Registry promotions for this pericope live in the paired BCD-DELTA page.

```json
{
  "sta_id": "ruth_pericope_03_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Ruth 1:15-18",
  "pericope_id": "P03",
  "pericope_title": "Naomi's last appeal; Ruth's vow; Naomi's silence",
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
  "confidence_overall_note": "P03 compiles cleanly with 5 propositions across 3 scenes. The pericope is the first oath-and-vow pericope in the pilot and surfaces the closed-list VOWS_* speech_act family for the first time, with a 1:1 mapping of the six bindings in Ruth's ladder (path / lodging / people / God / death-place / burial-place) to six VOWS_* values plus a separate INVOKES_SELF_CURSE_AS_OATH_ENFORCEMENT for the closing formula. Two scene-level INTIMATE overrides on S1 and S2 (mirroring the P02 S2/S3 pattern). YHWH-naming escalation v.16 unnamed → v.17 named captured across P3 and P4 with separate referential forms. No new B-codes, PL-codes, or TM-codes registered; all new vocabulary is TH_-prefixed structural objects and bounded-open scene_kinds / proposition_kinds / role tokens / referential forms. The expected drift profile is substantial (a dialogue-with-oath pericope built from a new VOWS_* speech-act family) but no closed-list violations. FIG_0072 PREFERRED + FIG_0074 REQUIRED + FIG_0075 REQUIRED open and close within the pericope. CB_0020 cross-pericope pair opens and is DEFERRED pending 3:13 compilation (Boaz's oath). FIG_0001 significantly absent at the moment of Ruth's covenantal binding.",
  "compilation_decisions": [
    {
      "decision_id": "P03-D1",
      "decision": "Pericope-level register set to INFORMAL_CASUAL with two scene-level INTIMATE overrides on S1 and S2.",
      "description": "Per hard rule, biblical narrator voice is INFORMAL_CASUAL at the pericope level. Scenes 1 and 2 carry mother-in-law/daughter-in-law roadside dialogue: Naomi's last appeal (S1) and Ruth's vow (S2). Both fit INTIMATE better than CEREMONIAL despite the institutional weight of the oath formula at v.17b: there is no community audience and no formal covenant venue. The binding-force of the vow is carried by figure flags (FIG_0072 / FIG_0074 / FIG_0075) and by the closed-list VOWS_* speech_act values, not by elevated register. Scene 3 returns to INFORMAL_CASUAL narrator default for the narrator-report of Naomi seeing and ceasing speech. No moment-level overrides."
    },
    {
      "decision_id": "P03-D2",
      "decision": "Meaning-map P3 six-binding ladder compiled as one compound MEANING_COORDINATES proposition with six binding components, not six separate propositions.",
      "description": "The meaning map's P3 holds Ruth's six successive bindings (path / lodging / people / God / death-place / burial-place) as one proposition with twelve Q&A pairs. For MEANING_COORDINATES, the compound option (one UTTERED_COVENANT_BINDING_VOW proposition with vow_components carrying six binding records) was chosen over the alternative of six per-binding propositions. Rationale: the ladder is one continuous speech with one speaker and one addressee; each binding carries its own closed-list speech_act value at component-record level (VOWS_ROAD_BINDING / VOWS_RESIDENCE_BINDING / VOWS_PEOPLE_BINDING / VOWS_GOD_BINDING / VOWS_IDENTITY_BINDING / VOWS_PLACE_OF_BURIAL_BINDING), parallel to P02 P9's SPOKE_DISSUASIVE_APPEAL compound-with-component-speech_act pattern. The six bindings remain structurally distinct via list_position FIRST through SIXTH and via the separate per-component binding_phrase_form."
    },
    {
      "decision_id": "P03-D3",
      "decision": "Death-place binding mapped to VOWS_IDENTITY_BINDING; burial-place binding mapped to VOWS_PLACE_OF_BURIAL_BINDING.",
      "description": "Closed-list speech_act values in validation-rules v0.4 include six VOWS_* tokens that map 1:1 to the six bindings in Ruth's ladder. The mapping is required, not optional: pairing death-place and burial-place under one speech_act would collapse FIG_0074 (the death-and-burial pair) into a single binding and contradict the Step A direction carried through Step C ('do not collapse death and burial into a single binding'). The death-place binding is structurally identity-at-the-limit ('where you die I will die' names no position and binds Ruth's mortality to Naomi's), which fits VOWS_IDENTITY_BINDING; the burial-place binding names a future shared resting-place (\"and there I will be buried\"), which fits VOWS_PLACE_OF_BURIAL_BINDING. — SUPERSEDED by SC-0024 (2026-06-04): the six VOWS_* values are collapsed to a single closed-list VOWS (Thread A nested-slot reduction). P03-D3's stated concern — that collapse would lose FIG_0074 — does NOT apply to this collapse: FIG_0074 (the death-and-burial pair) fires on proposition P3 via figure_flags, a verse-span-keyed layer independent of the speech_act values (verified: FIG_0074 is not referenced inside event_specific_slots and no engine couples figures to speech_act), and the six-way binding distinction is retained by vow_structural_form (SIX_STEP_LADDER_PATH_LODGING_PEOPLE_GOD_DEATH_BURIAL) + per-component list_position (FIRST–SIXTH) + binding_domain. The collapse moves the distinction out of the closed, cross-corpus speech_act layer into the figure/structure layer where it belongs; it is not lost. Original P03-D3 reasoning retained above as provenance. See SPEC_CHANGES SC-0024."
    },
    {
      "decision_id": "P03-D4",
      "decision": "YHWH-naming escalation v.16 → v.17 encoded across P3 and P4 with separate referential forms.",
      "description": "Ruth says 'your God my God' at v.16d-e without naming YHWH; she invokes YHWH by name at v.17b inside the self-curse formula. The escalation from unnamed-God-in-pairing to named-YHWH-in-oath is structurally significant. P3's God-binding component carries invoked_divine_agent: B10 BUT marks referential_form_at_verse: UNNAMED_DEITY; P4's self-curse carries agent_named: B10 with referential_form YHWH. The asymmetry between v.15 ('her gods' unnamed) and v.17 ('YHWH' named) is recorded as a STRUCTURAL_CONTRAST high-risk entry."
    },
    {
      "decision_id": "P03-D5",
      "decision": "'Her people' and 'her gods' of Moab at v.15 encoded as referenced collectives in S1.objects_in_scene, not as B-codes.",
      "description": "Per Agent 1 gate-A direction, no B-code exists for either the Moabite people-collective or the Moabite deities-collective, and none is pre-declared for P03. Both are encoded as content objects in S1's objects_in_scene (TH_MOABITE_PEOPLE_COLLECTIVE_REFERENCED, TH_MOABITE_DEITIES_COLLECTIVE_REFERENCED). The asymmetric naming (Moabite gods unnamed at v.15 vs YHWH named at v.17 on Ruth's lips) is recorded in S1's significant_absence and as a STRUCTURAL_CONTRAST high-risk entry. No new B-codes registered in P03."
    },
    {
      "decision_id": "P03-D6",
      "decision": "Indefinite-place withholding inside Ruth's vow: no PL-codes assigned to the four indefinite-place constructions.",
      "description": "Ruth's vow uses four indefinite-place forms across v.16-17 (where you go / where you lodge / where you die / there I will be buried). Per Agent 1 gate-A direction, none of these takes a PL-code. The indefinite-place construction is encoded structurally as a single abstract object TH_INDEFINITE_PLACE_CONSTRUCTION in S2's objects_in_scene; per-binding indefinite-place tokens (WHERE_YOU_GO, WHERE_YOU_LODGE, WHERE_YOU_DIE) appear as binding_indefinite_place_form values on each binding component. The vow holds the binding open to wherever Naomi goes; the withholding is preserved structurally."
    },
    {
      "decision_id": "P03-D7",
      "decision": "FIG_0001 Ruth-the-Moabitess significantly absent in P03; not activated in MEANING_COORDINATES figure_flags.",
      "description": "The narrator does not label Ruth with the Moabite epithet anywhere in P03. The withholding at the moment of Ruth's covenantal binding is structural — the narrator does not undercut the binding by re-asserting the ethnic boundary. Recorded as a SIGNIFICANT_ABSENCE high-risk entry in COMPILATION-LOG; recorded in S2's significant_absence; NOT flagged in any P03 proposition's figure_flags. Carry-forward through later pericopes will resume FIG_0001 where the narrator returns to the Moabite epithet."
    },
    {
      "decision_id": "P03-D8",
      "decision": "Orpah named only by kinship form yebimtekh; continues P02 R7 NAMING_SHIFT exit-finality.",
      "description": "At v.15 Naomi refers to Orpah as 'your sister-in-law' (יְבִמְתֵּךְ, yebimtekh, levirate-relevant kinship form). Combined with 'her mother-in-law' (לַחֲמוֹתָהּ, the kinship form used at P02 1:14 P15), the kinship-only naming completes Orpah's exit-finality from the book. Orpah is never named again after 1:14, and at 1:15 she appears only via the kinship form. Recorded as a NAMING_SHIFT high-risk entry with carry-forward note to P02 R7."
    },
    {
      "decision_id": "P03-D9",
      "decision": "Self-curse oath conditional with binds-past-death structural force.",
      "description": "The conditional 'if death itself separates between me and you' (כִּי הַמָּוֶת יַפְרִיד בֵּינִי וּבֵינֵךְ) at v.17c-d is structurally unusual: mortality is presumed inevitable, so the condition can only literally fail through death. The oath therefore binds Ruth past her own death. Encoded in P4 as oath_conditional_form TH_OATH_CONDITIONAL_DEATH_AS_SEPARATOR plus oath_conditional_structural_force BINDS_BEYOND_DEATH_VIA_INEVITABLE_CONDITION. Recorded as a SELF_CURSE_OATH high-risk entry; do_not_decide TRUE — reconstructor must preserve the binds-past-death force, not soften."
    },
    {
      "decision_id": "P03-D10",
      "decision": "Naomi's silence at v.18 as STRUCTURAL_ABSENCE_OF_INTERIOR_STATE.",
      "description": "The narrator at v.18 reports Naomi seeing Ruth's determination (with interior access granted to Ruth's resolve via the hithpael participle מִתְאַמֶּצֶת) and Naomi ceasing speech to her, but does not report Naomi's interior response, no agreement, no blessing, no further word from Naomi inside the pericope. The narrator's selective interior-access (to Ruth, not to Naomi) is structurally significant. Recorded as a SIGNIFICANT_ABSENCE / STRUCTURAL_ABSENCE_OF_INTERIOR_STATE high-risk entry; do_not_decide TRUE — reconstructor must not fill the silence with Naomi's interior or with an inferred acceptance."
    },
    {
      "decision_id": "P03-D11",
      "decision": "VOW_AND_RATIFICATION_SCENE used as S2 scene_kind; drift warning expected and accepted.",
      "description": "S2 (Ruth's vow at v.16-17) is the first oath-and-vow scene in Pilot 2. The scene_kind VOW_AND_RATIFICATION_SCENE is bounded-open against the canonical P01 seed (which had only OPENING_CHRONICLE_SCENE, BEREAVEMENT_SCENE, FOREIGN_MARRIAGE_AND_EXTENDED_RESIDENCE_SCENE). Carried forward from Pilot 1 archive vocabulary. A drift warning at Gate F is expected and should be accepted (this is the first vow-scene in the pilot; the value is real, not drift)."
    },
    {
      "decision_id": "P03-D12",
      "decision": "No new B-codes, PL-codes, or TM-codes registered; new vocabulary is concentrated in TH_ objects and bounded-open enumerations.",
      "description": "The pericope is dialogue-heavy and oath-heavy but introduces no new participants (B-codes), no new named places (PL-codes), and no new named times (TM-codes). All new content sits in TH_-prefixed structural objects (the vow's six binding forms, the self-curse formula, the oath conditional, the kinship form yebimtekh, the presentational marker hinneh, the referenced-Moabite-collective forms, the determined hithpael participle, the cessation-of-appeal verb, the directive form, the nominal-equation pair-form, the indefinite-place construction). Bounded-open additions also surface in proposition_kinds (5 new), scene_kinds (3 new — APPEAL_WITH_EXEMPLAR_POINTING_SCENE, VOW_AND_RATIFICATION_SCENE, SEEING_AND_FALLING_SILENT_SCENE), role_in_scene values (~10 new), and referential_forms (YEBIMTEKH, UNNAMED_DEITY, YHWH). All drift-warn against the canonical P01 seed; all are real pericope-specific values; all should be accepted at Gate F."
    }
  ],
  "vocabulary_additions": {
    "action_values": [
      { "value": "CEASED_SPEAKING", "source": "first introduced in P03 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "SAW", "source": "first introduced in P03 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "VOWED", "source": "first introduced in P03 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" }
    ],
    "proposition_kinds": [
      {
        "value": "PERCEIVED",
        "source": "P5 1:18",
        "status": "CONFIRMED"
      },
      {
        "value": "VOW",
        "source": "P3 1:16b-17a",
        "status": "CONFIRMED"
      }
    ],
    "scene_kinds": [
      {
        "value": "RATIFICATION_SCENE",
        "source": "S3 1:18",
        "status": "CONFIRMED"
      },
      {
        "value": "VOW_SCENE",
        "source": "S2 1:16-17",
        "status": "CONFIRMED"
      }
    ],
    "presence_values": [],
    "role_in_scene_beings": [],
    "arc_elements": [
      { "value": "RELEASE_ATTEMPT", "source": "S1 1:15 Naomi's final appeal pointing to Orpah's return", "status": "CONFIRMED" },
      { "value": "REFUSAL_OF_RELEASE", "source": "S2 1:16a Ruth refuses to turn back", "status": "CONFIRMED" },
      { "value": "COVENANT_BINDING_BY_VOW", "source": "S2 1:16b-17a Ruth's covenant-binding vow ladder", "status": "CONFIRMED" },
      { "value": "OATH_SEALING", "source": "S2 1:17b self-curse oath seals the vow", "status": "CONFIRMED" },
      { "value": "SILENCE_AFTER_VOW", "source": "S3 1:18 Naomi sees the resolve and ceases speaking", "status": "CONFIRMED" }
    ],
    "context_elements": [
      { "value": "PRIOR_PERICOPE_CARRY_FORWARD", "source": "return-road setting carried forward from P02", "status": "CONFIRMED" },
      { "value": "TRAJECTORY_CONTEXT_ON_RETURN_ROAD", "source": "the journey toward Judah continues", "status": "CONFIRMED" }
    ],
    "tone_elements": [
      { "value": "INTIMATE", "source": "S2 mother / daughter-in-law vow exchange", "status": "CONFIRMED" },
      { "value": "SLOWED", "source": "deliberate pacing through the vow", "status": "CONFIRMED" },
      { "value": "RISING", "source": "1:16-17 the vow's ascending ladder of bindings", "status": "CONFIRMED" },
      { "value": "UNSETTLED_AT_CLOSE", "source": "1:18 Naomi's withheld interior response", "status": "CONFIRMED" }
    ],
    "pace_elements": [
      { "value": "NARROWS", "source": "tight focus on the two women", "status": "CONFIRMED" },
      { "value": "DELIBERATE", "source": "the vow uttered deliberately", "status": "CONFIRMED" },
      { "value": "PAUSED", "source": "1:18 the pause at Naomi's silence", "status": "CONFIRMED" }
    ],
    "communicative_function_elements": [
      {
        "value": "ADVANCES",
        "source": "level_1 communicative_function_elements",
        "status": "CONFIRMED"
      }
    ],
    "referential_forms": [
      {
        "value": "YEBIMTEKH",
        "source": "B8 at S1 / 1:15 (Orpah named only as 'your sister-in-law' yebimtekh)",
        "status": "PROPOSED",
        "note": "Bounded-open; second kinship-only form for B8 after לַחֲמוֹתָהּ at P02 1:14."
      },
      {
        "value": "UNNAMED_DEITY",
        "source": "B10 at P3 v.16d-e (Ruth says 'your God my God' without naming YHWH)",
        "status": "PROPOSED",
        "note": "Bounded-open; first half of the YHWH-naming escalation."
      },
      {
        "value": "YHWH",
        "source": "B10 at P4 v.17b (Ruth names YHWH inside the self-curse formula)",
        "status": "PROPOSED",
        "note": "Bounded-open; second half of the YHWH-naming escalation; structural-first."
      }
    ],
    "other": [
      {
        "category": "OBJECT_KIND",
        "value": "JOURNEY_LOCUS",
        "source": "TH_THE_RETURN_ROAD continued from P02",
        "status": "CONFIRMED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "PRESENTATIONAL_MARKER",
        "source": "TH_PRESENTATIONAL_MARKER_HINNEH at 1:15",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "KINSHIP_FORM_LEVIRATE_RELEVANT",
        "source": "TH_KINSHIP_FORM_YEBIMTEKH at 1:15",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "REFERENCED_COLLECTIVE_FORM_PEOPLE",
        "source": "TH_MOABITE_PEOPLE_COLLECTIVE_REFERENCED at 1:15",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "REFERENCED_COLLECTIVE_FORM_DEITIES",
        "source": "TH_MOABITE_DEITIES_COLLECTIVE_REFERENCED at 1:15",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "DIRECTIVE_WITH_EXEMPLAR_POINTING",
        "source": "TH_DIRECTIVE_GO_BACK_AFTER_SISTER_IN_LAW at 1:15",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "REFUSAL_OPENING_OF_VOW_FORM",
        "source": "TH_REFUSAL_OPENING_OF_VOW at 1:16a",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "INDEFINITE_PLACE_CONSTRUCTION_FORM",
        "source": "TH_INDEFINITE_PLACE_CONSTRUCTION at 1:16-17",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "VOW_PATH_BINDING_FORM",
        "source": "TH_VOW_PATH_BINDING at 1:16b",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "VOW_LODGING_BINDING_FORM",
        "source": "TH_VOW_LODGING_BINDING at 1:16c",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "NOMINAL_EQUATION_PAIR_FORM",
        "source": "TH_NOMINAL_EQUATION_PEOPLE_AND_GOD_PAIR at 1:16d-e",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "VOW_PEOPLE_BINDING_FORM",
        "source": "TH_VOW_PEOPLE_BINDING at 1:16d",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "VOW_GOD_BINDING_FORM",
        "source": "TH_VOW_GOD_BINDING at 1:16e",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "VOW_DEATH_PLACE_BINDING_FORM",
        "source": "TH_VOW_DEATH_PLACE_BINDING at 1:17a",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "VOW_BURIAL_PLACE_BINDING_FORM",
        "source": "TH_VOW_BURIAL_PLACE_BINDING at 1:17a",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "SELF_CURSE_OATH_FORMULA_FORM",
        "source": "TH_SELF_CURSE_OATH_FORMULA at 1:17b",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "OATH_CONDITIONAL_DEATH_AS_SEPARATOR_FORM",
        "source": "TH_OATH_CONDITIONAL_DEATH_AS_SEPARATOR at 1:17c-d",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "NARRATOR_INTERIOR_ACCESS_HITHPAEL_PARTICIPLE",
        "source": "TH_DETERMINED_HITHPAEL_PARTICIPLE at 1:18",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "CESSATION_OF_APPEAL_VERB",
        "source": "TH_CESSATION_OF_APPEAL at 1:18",
        "status": "PROPOSED"
      }
    ]
  },
  "proposition_kind_slot_sets": [
    {
      "proposition_kind": "SPOKE_DISSUASIVE_APPEAL_WITH_EXEMPLAR",
      "slot_set": [
        "speaker",
        "addressees",
        "appeal_components"
      ],
      "component_record_shape": {
        "action": "required - STATED_EXEMPLAR_RETURN | DIRECTED_HEARER_TO_FOLLOW_EXEMPLAR",
        "speaker": "required",
        "addressee": "conditional",
        "exemplar_party": "required",
        "exemplar_referential_form": "required",
        "speech_act": "required - STATES_AS_TRUE | DIRECTS_HEARER_TO_RETURN"
      },
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P1"
      ]
    },
    {
      "proposition_kind": "REFUSED_DIRECTIVE_AS_OPENING_OF_VOW",
      "slot_set": [
        "refuser",
        "addressee",
        "refused_action",
        "refusal_form",
        "speech_act"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P2"
      ]
    },
    {
      "proposition_kind": "UTTERED_COVENANT_BINDING_VOW",
      "slot_set": [
        "speaker",
        "addressee",
        "vow_structural_form",
        "vow_components"
      ],
      "component_record_shape": {
        "action": "required - VOWED_PATH_BINDING | VOWED_LODGING_BINDING | VOWED_PEOPLE_BINDING | VOWED_GOD_BINDING | VOWED_DEATH_PLACE_BINDING | VOWED_BURIAL_PLACE_BINDING",
        "binder": "required",
        "bound_to_referent": "required",
        "binding_phrase_form": "required",
        "list_position": "required - FIRST through SIXTH",
        "speech_act": "required - VOWS_ROAD_BINDING | VOWS_RESIDENCE_BINDING | VOWS_PEOPLE_BINDING | VOWS_GOD_BINDING | VOWS_IDENTITY_BINDING | VOWS_PLACE_OF_BURIAL_BINDING"
      },
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P3"
      ],
      "note": "Six-binding ladder held in one compound proposition with six component records; each component carries a closed-list VOWS_* speech_act; 1:1 mapping required per P03-D3."
    },
    {
      "proposition_kind": "SEALED_VOW_WITH_SELF_CURSE_OATH",
      "slot_set": [
        "speaker",
        "addressee",
        "agent_named",
        "agent_named_referential_form",
        "oath_formula_form",
        "oath_conditional_form",
        "oath_conditional_structural_force",
        "speech_act"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P4"
      ],
      "note": "Sealing proposition closing the six-binding ladder with the canonical Hebrew self-curse oath formula; conditional binds past Ruth's own death."
    },
    {
      "proposition_kind": "WITNESSED_RESOLVE_AND_CEASED_SPEECH",
      "slot_set": [
        "narrator_report_components"
      ],
      "component_record_shape": {
        "action": "required - SAW_DETERMINED_RESOLVE | CEASED_SPEAKING",
        "perceiver": "conditional",
        "perceived": "conditional",
        "ceaser": "conditional",
        "ceased_speaking_to": "conditional",
        "list_position": "required - FIRST | SECOND",
        "speech_act": "required - STATES_AS_TRUE"
      },
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P5"
      ]
    }
  ],
  "high_risk_register_audit": [
    {
      "id": "R1",
      "kind": "VOW_AND_BINDING_BEYOND_DEATH",
      "applies_to": "Ruth's six-binding ladder + self-curse oath at P3 + P4 (1:16b-17b)",
      "note": "First oath-scene in the pilot. Six successive bindings (path, lodging, people, God, death-place, burial-place) closed by the canonical self-curse oath formula 'may YHWH do thus to me and worse'. The conditional 'if death itself separates between me and you' binds Ruth past her own death — the condition can only fail through death. Reconstructor must preserve the six-step ladder as six bindings (do not collapse 'people'+'God' or 'death'+'burial'), preserve the closing self-curse formula without softening, and preserve the binds-past-death structural force of the conditional.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3C Scene 2 (six binding forms TH_VOW_*_BINDING + TH_SELF_CURSE_OATH_FORMULA + TH_OATH_CONDITIONAL_DEATH_AS_SEPARATOR); Section 4 Propositions 3 and 4"
    },
    {
      "id": "R2",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0072 PAIRED_PATH_LODGING_VOW within-pericope pair at v.16b-c",
      "note": "PREFERRED keep-image. The matched indefinite-place + matched-action parallel structure ('where you go I will go, where you lodge I will lodge') is a strong rhetorical and oral feature. Both halves of the pair must render with parallel structure so the matched-action mirror is audible. Within-pericope pair: opens at v.16b, closes at v.16c.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 5B Figure Flags; Section 3C Scene 2 (TH_VOW_PATH_BINDING + TH_VOW_LODGING_BINDING)"
    },
    {
      "id": "R3",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0074 DEATH_AND_BURIAL_SHARED_PLACE within-pericope pair at v.17a",
      "note": "REQUIRED keep-image. Extends the binding past life; both halves of the death-and-burial commitment must land structurally distinct ('where you die I will die' is one binding; 'and there I will be buried' is a separate binding). The two halves must render as a clear pair, not as a single conflated death-burial binding. Within-pericope pair: opens at v.17a first half, closes at v.17a second half.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 5B Figure Flags; Section 3C Scene 2 (TH_VOW_DEATH_PLACE_BINDING + TH_VOW_BURIAL_PLACE_BINDING)"
    },
    {
      "id": "R4",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0075 SELF_CURSE_OATH_FORMULA at v.17b",
      "note": "REQUIRED keep-image. The canonical Hebrew self-curse oath formula 'may YHWH do thus to me and worse' (כֹּה יַעֲשֶׂה יְהוָה לִי וְכֹה יוֹסִיף). Do not soften. High terminological-consistency requirement across the book (will recur at 3:13 in Boaz's oath at the threshing floor) and across the Hebrew canon (recurs at 1 Sam 3:17; 14:44; 20:13; 2 Sam 3:9; 19:14; 1 Kgs 2:23; 2 Kgs 6:31). Reconstruction must preserve the divine-name invocation and the open-ended 'and more' clause.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 5B Figure Flags; Section 3C Scene 2 (TH_SELF_CURSE_OATH_FORMULA)"
    },
    {
      "id": "R5",
      "kind": "STRUCTURAL_DIVINE_NAMING_FIRST_ON_OUTSIDER_LIPS",
      "applies_to": "B10 YHWH named by B9 Ruth at P4 (1:17b) inside the self-curse oath formula",
      "note": "First time the divine name YHWH appears on Ruth's lips in the book. The named divine subject was last heard in P02 from Naomi's voice (provider at 1:6, hand-against at 1:13); P03 places the name on the Moabite outsider's lips for the first time. Structurally significant for T6 (YHWH-at-work) and T5 (Moabite-outsider-incorporation). Reconstructor must preserve YHWH-named at v.17, not generic-deity.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3A Scene 2 (B10 REFERENCED); Section 3C Scene 2 (TH_SELF_CURSE_OATH_FORMULA); Section 4 Proposition 4"
    },
    {
      "id": "R6",
      "kind": "STRUCTURAL_CONTRAST",
      "applies_to": "Asymmetric naming: 'her gods' of Moab unnamed at v.15 vs YHWH named at v.17",
      "note": "Naomi at v.15 names Orpah's trajectory as toward 'her people and her gods' — Moabite deities are referenced as a collective but no deity-name is uttered. Ruth at v.17 invokes YHWH by name in the self-curse formula. The asymmetric naming is a structural contrast: Moabite gods stay unnamed (no Chemosh), Israel's God is named. Reconstructor must preserve both halves of the contrast — do not name Moabite gods (the text doesn't), do not omit YHWH (the text does).",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3C Scene 1 (TH_MOABITE_DEITIES_COLLECTIVE_REFERENCED); Section 3C Scene 2 (TH_SELF_CURSE_OATH_FORMULA); Section 1 multi-level register paragraph + S1 significant_absence"
    },
    {
      "id": "R7",
      "kind": "SIGNIFICANT_ABSENCE",
      "applies_to": "FIG_0001 Ruth-the-Moabitess withheld at the moment of Ruth's covenantal binding in P03",
      "note": "The narrator does not label Ruth with the Moabite epithet anywhere in P03. At the moment of Ruth's verbal covenant-binding to Naomi's people and God, the narrator does not re-assert the ethnic boundary. The withholding is structurally significant for T5 (Moabite-outsider-incorporation). Reconstructor must not insert the Moabite epithet inside or around the vow; later pericopes (P05, P07, P11, P12) will resume the epithet where the narrator does.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 5B (FIG_0001 deliberately NOT activated); Section 3 Scene 2 significant_absence"
    },
    {
      "id": "R8",
      "kind": "NAMING_SHIFT",
      "applies_to": "B8 Orpah at 1:15 — named only by kinship form יְבִמְתֵּךְ (yebimtekh, 'your sister-in-law'); never named by personal name in P03",
      "note": "Naomi at v.15 names Orpah twice within the verse but uses the levirate-relevant kinship form yebimtekh both times. Combined with the kinship form לַחֲמוֹתָהּ ('her mother-in-law') used at P02 1:14 (P02 R7), Orpah's exit-finality is completed by kinship-only naming across her last two textual appearances. Reconstructor must preserve the kinship-only naming (do not insert Orpah's name at 1:15) so the exit-finality remains structurally visible.",
      "required_in_audit": true,
      "carries_forward_to": "P02_R7",
      "source_in_meaning_map": "Section 3A Scene 1 (B8 REFERENCED with referential_form YEBIMTEKH); Section 3C Scene 1 (TH_KINSHIP_FORM_YEBIMTEKH)"
    },
    {
      "id": "R9",
      "kind": "REFERENTIAL_FORM_CHANGE",
      "applies_to": "B10 YHWH at P3 v.16d-e (unnamed in binding pairing) versus B10 YHWH at P4 v.17b (named in oath)",
      "note": "Ruth's God-binding at v.16e ('your God my God') refers to B10 without uttering the divine name; Ruth's self-curse at v.17b utters the divine name YHWH directly. The escalation from unnamed-God-in-pairing to named-YHWH-in-oath is structurally significant. Recorded via separate referential_form values UNNAMED_DEITY (P3 God-binding) and YHWH (P4 self-curse). Reconstructor must preserve the escalation — do not insert YHWH at v.16, do not omit YHWH at v.17.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3C Scene 2 (TH_VOW_GOD_BINDING and TH_SELF_CURSE_OATH_FORMULA as separate structural objects); Section 4 Propositions 3 and 4"
    },
    {
      "id": "R10",
      "kind": "SIGNIFICANT_ABSENCE",
      "applies_to": "Naomi's interior response withheld at v.18 (P5)",
      "note": "Narrator at v.18 reports Naomi seeing Ruth's determination and ceasing speech to her, but does not report Naomi's interior response. No agreement, no blessing, no acceptance, no rejection, no further word from Naomi inside the pericope. The narrator gives interior access only to Ruth's resolve (via the hithpael participle מִתְאַמֶּצֶת), not to Naomi's response. The withholding is structurally open and load-bearing. Reconstructor must not fill the silence with Naomi's interior, with an inferred acceptance, or with a continuation past v.18.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3C Scene 3 (TH_DETERMINED_HITHPAEL_PARTICIPLE and TH_CESSATION_OF_APPEAL); Section 3 Scene 3 significant_absence"
    },
    {
      "id": "R11",
      "kind": "CROSS_PERICOPE_PAIRING_FIRST_OCCURRENCE",
      "applies_to": "CB_0020 Oath-Formula-Self-curse opens at P03 v.17b; will recur at 3:13 (Boaz's oath at the threshing floor)",
      "note": "First occurrence of the canonical Hebrew self-curse oath formula in the book. The same formula recurs at 3:13 when Boaz swears an oath about redemption to Ruth at the threshing floor. The two oath-occurrences form a cross-pericope pair structurally — Ruth invokes the formula committing herself to Naomi (and to YHWH); Boaz later invokes the same formula committing himself to act for Ruth. Reconstructor must use the same oath-formula form at both occurrences so the cross-pericope rhyme is audible.",
      "required_in_audit": true,
      "carries_forward_to": "P09_compilation_log_or_wherever_3_13_lands",
      "source_in_meaning_map": "Section 5A Concept Bank Flags (CB_0020 active at P4); Section 3C Scene 2 (TH_SELF_CURSE_OATH_FORMULA)"
    },
    {
      "id": "R12",
      "kind": "DISCOURSE_THREAD_ADVANCED_FIRST_MAJOR",
      "applies_to": "T5 Moabite-Outsider-Incorporation MAJOR ADVANCE at P3 (1:16-17) — Ruth's verbal binding to Naomi's people and God",
      "note": "Ruth's people-and-God binding pair at v.16d-e ('your people will be my people, your God will be my God') is the first explicit Moabite-outsider self-incorporation in the book. Structural high point short of the elders' formal incorporation at 4:11-12. Recorded as discourse_thread_event in BCD-DELTA. Reconstructor must preserve the people-binding and God-binding as the structural high point of T5 in chapter 1.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 2.4 Communicative Function; Section 3C Scene 2 (TH_VOW_PEOPLE_BINDING + TH_VOW_GOD_BINDING + TH_NOMINAL_EQUATION_PEOPLE_AND_GOD_PAIR); Section 5A (CB_0021); Section 4 Proposition 3"
    },
    {
      "id": "R13",
      "kind": "DISCOURSE_THREAD_ADVANCED_FIRST_MAJOR",
      "applies_to": "T4 Hesed-Answered-with-Hesed advance at P3 — Ruth's vow enacts hesed beyond duty",
      "note": "Ruth's vow at v.16-17 enacts hesed beyond duty. Naomi has just released the daughters-in-law twice (P02 1:8-9 and 1:11-13) and watched Orpah accept the release; Ruth answers release with binding. T4 (opened by Naomi's speech at P02 1:8 'may YHWH deal hesed with you as you have dealt with the dead and with me') receives its first action-side response at P03. Recorded as discourse_thread_event in BCD-DELTA.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 2.4 Communicative Function; Section 4 Propositions 2 and 3"
    }
  ],
  "cross_pericope_pair_verification": {
    "pairs": [
      {
        "fig_id": "FIG_0072",
        "opens_at": "P3 (1:16b)",
        "closes_at": "P3 (1:16c) — within-pericope pair",
        "verification_status": "VERIFIED",
        "note": "Paired path-lodging vow within-pericope pair completes at P03. The matched indefinite-place + matched-action parallel structure ('where you go I will go, where you lodge I will lodge') is verified within the same proposition (P3) at v.16b-c."
      },
      {
        "fig_id": "FIG_0074",
        "opens_at": "P3 (1:17a first half)",
        "closes_at": "P3 (1:17a second half) — within-pericope pair",
        "verification_status": "VERIFIED",
        "note": "Death-and-burial shared-place within-pericope pair completes at P03. Both halves of the pair ('where you die I will die' and 'and there I will be buried') sit inside the same proposition (P3) at v.17a as the fifth and sixth bindings of the ladder."
      },
      {
        "fig_id": "FIG_0075",
        "opens_at": "P4 (1:17b)",
        "closes_at": "P4 (1:17b) — single-occurrence within-pericope",
        "verification_status": "VERIFIED",
        "note": "Self-curse oath formula at v.17b. Single-occurrence within P03; the cross-canonical recurrences (1 Sam 3:17; 14:44; 20:13; 2 Sam 3:9; 19:14; 1 Kgs 2:23; 2 Kgs 6:31) are outside Ruth and outside the pilot's scope."
      },
      {
        "fig_id": "FIG_0012",
        "opens_at": "P02 P15 (1:14)",
        "closes_at": "P07 (2:23) pending",
        "verification_status": "DEFERRED",
        "note": "Carries forward from P02. Not lexically active in P03 (no dabaq lexeme in the vow). The vow is the structural continuation of Ruth's silent cling but the image-rhyme tracks the dabaq lexeme, which closes at 2:23. P07 not yet compiled."
      },
      {
        "fig_id": "FIG_0001",
        "opens_at": "P01 P10 (1:4)",
        "closes_at": "Recurs at P04 P05 P07 P11 P12",
        "verification_status": "DEFERRED",
        "note": "Significantly absent in P03 per R7 (Ruth's covenantal binding not undercut by ethnic epithet). Carry-forward of the cross-pericope thread continues without P03 activation."
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
      "REFUSES_REQUEST_WITH_COUNTER_DECLARATION",
      "VOWS",
      "INVOKES_SELF_CURSE_AS_OATH_ENFORCEMENT"
    ],
    "negation_not_double_encoded": "N/A — no DIRECTS_HEARER_NOT_TO_DO in P03 (no negative directives)",
    "cross_pericope_cross_refs_present_on_correct_propositions": true,
    "empty_slot_rule_applied_to_times_in_scene": true,
    "discourse_threads_tracked_in_audit_only": true,
    "known_limitations_tracked_in_audit_only": true,
    "high_risk_register_complete": true,
    "every_high_risk_entry_traces_to_meaning_map": true,
    "significant_absences_traced_to_meaning_map": true,
    "no_content_added_beyond_meaning_map": true,
    "wife_pairing_withholding_enforced": true,
    "b_codes_match_bcd_version": "All B-codes verified against ruth_pilot_BCD_v0_3 plus carry-forward B31 from P02. No new B-codes in P03.",
    "registry_additions_extracted_to_bcd_delta": true,
    "no_reviewer_facing_prompts_in_compilation_log": true
  },
  "known_limitations": [
    "Cross-pericope pair verification for CB_0020 / FIG_0075 (self-curse oath formula) is DEFERRED pending compilation of the pericope containing 3:13 (Boaz's oath at the threshing floor).",
    "Cross-pericope pair verification for FIG_0012 (dabaq clinging image-rhyme) remains DEFERRED from P02; closes at 2:23 (P07 not yet compiled).",
    "Substantial bounded-open vocabulary additions (5 new proposition_kinds, 3 new scene_kinds, ~10 new role_in_scene values, 3 new referential_forms, ~18 new object_kinds) reflect this pericope being the first oath-and-vow pericope in the pilot. All drift-warn against the canonical P01 seed; all should be accepted at Gate F as real pericope-specific values.",
    "VOW_AND_RATIFICATION_SCENE scene_kind on S2 is carried forward from Pilot 1 archive vocabulary; a drift warning is expected at Gate F.",
    "PL_LAND_OF_JUDAH (carry-forward from P02 BCD-DELTA) remains a working code pending formal PL-code assignment in BCD v0.4. The road and the indefinite-place constructions inside the vow are encoded as TH_-prefixed structural objects rather than as place-codes.",
    "community_verified and translation_team_verified remain false; this is a pilot compilation."
  ]
}
```

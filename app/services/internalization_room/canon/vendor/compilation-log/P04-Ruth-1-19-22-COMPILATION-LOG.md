---
type: "sta-compilation-log"
pericope: "P04"
pericope-title: "Naomi and Ruth arrive in Bethlehem; the women of the town react; Naomi renames herself Mara"
source-meaning-map: [[P04-Ruth-1-19-22]]
source-meaning-coordinates: [[P04-Ruth-1-19-22-MEANING-COORDINATES]]
related-bcd-delta: [[P04-Ruth-1-19-22-BCD-DELTA]]
status: "valid"
pilot: "pilot-2"
---

# P04 — Ruth 1:19–22 — COMPILATION-LOG

This page renders the COMPILATION-LOG JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder. Registry promotions for this pericope live in the paired BCD-DELTA page.

```json
{
  "sta_id": "ruth_pericope_04_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Ruth 1:19-22",
  "pericope_id": "P04",
  "pericope_title": "Naomi and Ruth arrive in Bethlehem; the women of the town react; Naomi renames herself Mara",
  "compiled_at": "2026-05-25",
  "review_status": {
    "meaning_map_status": "APPROVED",
    "sta_compilation_status": "PILOT_2_COMPILATION",
    "community_verified": false,
    "translation_team_verified": false,
    "consultant_review_required": false,
    "production_use": false
  },
  "confidence_overall": "MEDIUM_HIGH",
  "confidence_overall_note": "P04 compiles cleanly with 6 propositions across 3 scenes. The pericope closes chapter 1's emptying-and-return arc with three major book-level moves landing at v.22: (1) FIG_0001 Ruth-the-Moabitess reactivates in narrator voice after deliberate withholding at P02 and P03 (the structural counterpart to P03 R7 SIGNIFICANT_ABSENCE); (2) FIG_0013 Bread-house-in-Famine reaches its third occurrence and final close as the barley-harvest frame opens (cross-pericope close VERIFIED from P01 1:1 and P02 1:6); (3) T7 Harvest-Provision opens at v.22, structurally answering Naomi's empty lament at v.21 even before Naomi can see the answer. B12 Shaddai is first occurrence in book; B24 Women-of-Bethlehem and B28 The-Whole-City are first occurrences as collective subjects (B28 stirred, B24 spoke — source-text discipline distinguishes broader from speaking subset). Naomi's renaming proposal is encoded structurally without changing B3's underlying being: the narrator returns to 'Naomi' at v.22 in the very verse after her rejection of the name. Working time-code TM_BARLEY_HARVEST_BEGINNING proposed per the P02 PL_LAND_OF_JUDAH precedent. One scene-level INTIMATE override on S2 (mirroring P02-D1 / P03-D1 pattern). Bounded-open drift expected (6 new proposition_kinds for the pericope-specific compound speech and narrator-frame events; 3 new scene_kinds; ~10 new role_in_scene values; ~19 new object_kinds; multiple new referential_forms). No closed-list violations.",
  "compilation_decisions": [
    {
      "decision_id": "P04-D1",
      "decision": "Pericope-level register INFORMAL_CASUAL with scene-level INTIMATE override on S2 only.",
      "description": "Per hard rule, biblical narrator voice is INFORMAL_CASUAL at the pericope level. Scene 2 (Naomi's renaming lament at v.20-21) carries scene-level INTIMATE: Naomi speaks to the women of her own town from her own grief, in close-relational voice even though the setting is public. INTIMATE fits the relational moment better than CEREMONIAL even though the renaming and the divine-name doubling carry institutional weight at the form level; the institutional weight is carried by figure flags (FIG_0082 REQUIRED, FIG_0006 PREFERRED) and downstream STA encoding, not by elevated register. Scene 1 (arrival and recognition-question) and Scene 3 (narrator-frame close) stay at the INFORMAL_CASUAL narrator default. Pattern mirrors P02-D1 / P03-D1 scene-level INTIMATE overrides for relational moments inside narrator-frame pericopes."
    },
    {
      "decision_id": "P04-D2",
      "decision": "Meaning-map P5 lament-account compiled as one compound MEANING_COORDINATES proposition with four lament-components.",
      "description": "The meaning map's P5 holds Naomi's four-part v.21 lament (full-empty antithetical pair + question-recall + YHWH-anah + Shaddai-hera) as one proposition with multiple Q&A. For MEANING_COORDINATES the compound option (one SPOKE_LAMENT_WITH_DOUBLED_DIVINE_ATTRIBUTION proposition with four lament-components) was chosen over the split-into-2-3-propositions alternative. Rationale: the lament is one continuous speech with one speaker and one addressee-collective; the four components are tightly bound rhetorical moves inside a single lament-act; each component carries its own closed-list speech_act value at component-record level. Mirrors P02 P12 SPOKE_LAMENT_WITH_DIVINE_ATTRIBUTION (two components) and P03 P3 UTTERED_COVENANT_BINDING_VOW (six components) compound-speech patterns."
    },
    {
      "decision_id": "P04-D3",
      "decision": "Naomi's renaming proposal compiled as one compound MEANING_COORDINATES proposition with three components, using more-specific closed-list speech_act values.",
      "description": "The renaming proposal at v.20 has three illocutionary moves: refuse own name, propose new name, give reason. Compiled as one REFUSED_OWN_NAME_AND_PROPOSED_RENAMING proposition with three components. Speech_act mapping uses the more-specific closed-list values where they fit: 'Do not call me Naomi' → REFUSES_USE_OF_OWN_NAME (more specific than DIRECTS_HEARER_NOT_TO_DO); 'Call me Mara' → PROPOSES_NEW_NAME_FOR_SELF (more specific than DIRECTS_HEARER_TO_DO); 'for Shaddai has dealt very bitterly with me' → ASCRIBES_AFFLICTION_TO_GOD_IN_LAMENT (same construction as P02 R3 hand-of-YHWH). Using more-specific values where the closed list provides them keeps the no-double-negation rule trivially satisfied: there are no negative directives in the MEANING_COORDINATES output because REFUSES_USE_OF_OWN_NAME carries the refusal-force without a negative directive."
    },
    {
      "decision_id": "P04-D4",
      "decision": "FIG_0001 Ruth-the-Moabitess reactivation at v.22 recorded as a high-risk register entry, not as a new figure addition.",
      "description": "FIG_0001 was first-occurrence-registered at P01 P10 (1:4). The narrator deliberately withheld the epithet through P02 and P03 (recorded as P03 R7 SIGNIFICANT_ABSENCE). At P04 v.22 the narrator returns to the epithet at the public-arrival moment. The structural counterpart to P03 R7 is recorded in this COMPILATION-LOG as a REFERENTIAL_FORM_REACTIVATION_AFTER_WITHHOLDING high-risk entry with carries_forward_to P05. FIG_0001 is flagged in MEANING_COORDINATES P6 figure_flags but is NOT re-added to BCD-DELTA to_figures_registry (already registered at P01). The cross_pericope_pair_verification for FIG_0001 remains DEFERRED — the figure's full arc continues across P04, P05, P07, P11, P12."
    },
    {
      "decision_id": "P04-D5",
      "decision": "FIG_0013 Bread-house-in-Famine final close at v.22. cross_pericope_pair_verification: VERIFIED.",
      "description": "FIG_0013 opened at P01 1:1 (famine in beit-lechem), closed first at P02 1:6 (YHWH gives bread to his people), reaches its third occurrence and final close at P04 v.22 when 'they came to Bethlehem at the beginning of the barley harvest' lands the bread-house name against the harvest-frame opening. The cross-pericope pair verification is marked VERIFIED: the harvest-frame opening at v.22 is the structural answer to the famine opening at 1:1; both the lexical bread-house name and the structural provision-pattern converge here. FIG_0013 flagged in MEANING_COORDINATES at P1, P2, P6 (all three Bethlehem-namings in P04); not re-added to BCD-DELTA to_figures_registry."
    },
    {
      "decision_id": "P04-D6",
      "decision": "Three new B-codes registered at P04 with source-text-distinguished kinds: B12 Shaddai (DIVINE_BEING), B24 Women-of-Bethlehem (FEMALE_COMMUNITY_VOICE), B28 The-Whole-City (COLLECTIVE_COMMUNAL_BODY).",
      "description": "B12 Shaddai is the archaic-poetic divine name; first occurrence in the book. Kind DIVINE_BEING. B24 Women-of-Bethlehem is the female-community speaking voice that asks the recognition-question at v.19 and is the addressee through Naomi's lament; Kind FEMALE_COMMUNITY_VOICE. B28 The-Whole-City is the broader collective subject of 'all the city was stirred about them'; kind COLLECTIVE_COMMUNAL_BODY. Source-text discipline: the women speak (B24); the city stirs (B28). Do not merge them. Both are PRESENT_COLLECTIVE in S1 beings_in_scene with distinct role_in_scene values."
    },
    {
      "decision_id": "P04-D7",
      "decision": "TM_BARLEY_HARVEST_BEGINNING proposed as working time-code per P02 PL_LAND_OF_JUDAH precedent.",
      "description": "No formal TM_ pre-declared in the BCD for the harvest-setting frame. The working code TM_BARLEY_HARVEST_BEGINNING is registered in BCD-DELTA to_bcd.times with kind AGRICULTURAL_SEASON_MARKER, name_hebrew בִּתְחִלַּת קְצִיר שְׂעֹרִים, name_english 'at the beginning of the barley harvest', first_appearance 1:22. Pattern parallels P01's PL_HA_ARETZ and P02's PL_LAND_OF_JUDAH working-code patterns. Recorded in known_limitations for formal TM-code assignment in BCD v0.4."
    },
    {
      "decision_id": "P04-D8",
      "decision": "Naomi's renaming proposal does not take effect; narrator returns to 'Naomi' at v.22; recorded as STRUCTURAL_NON_ADOPTION_OF_PROPOSED_RENAMING.",
      "description": "Naomi proposes 'Mara' at v.20 and reinforces the refusal of 'Naomi' at v.21 ('Why do you call me Naomi'). The narrator immediately uses 'Naomi' again in the v.22 narrator-frame ('So Naomi returned'). The proposal is structurally encoded at MEANING_COORDINATES P4 as a speech-act without changing B3's underlying being. B3's refusal component carries action REFUSED + refused_name Naomi (no referential_form_at_verse); the proposal component carries referential_form_at_verse MARA; at v.22 it returns to NAMED. The reconstructor must encode the proposal as Naomi's speech-act without applying the new name in narrator voice or in later references."
    },
    {
      "decision_id": "P04-D9",
      "decision": "Family-naming silence in Naomi's 'I went out full' preserved structurally.",
      "description": "Naomi's lament at v.21 implicitly references the household she left with (Elimelech, Mahlon, Chilion) through the phrase 'I went out full' but does NOT name any of them. The narrator's v.22 return-frame names only Naomi and Ruth; the dead are not re-named even in the return-summary. Recorded as a STRUCTURAL_ABSENCE_OF_FAMILY_NAMING_IN_LAMENT high-risk entry. Wife-pairing withholding from P01 1:4 carries forward — no Mahlon-Ruth pairing is asserted at P04."
    },
    {
      "decision_id": "P04-D10",
      "decision": "Recognition-failure cause at v.19 not inferred; do_not_decide: true.",
      "description": "The women's question 'Is this Naomi?' implies the women cannot recognize Naomi. The narrator does not say why — grief, age, demeanor, or appearance are all possible causes the narrator withholds. Recorded as a SIGNIFICANT_ABSENCE high-risk entry with do_not_decide: true. The reconstructor must not fill the cause."
    },
    {
      "decision_id": "P04-D11",
      "decision": "T7 Harvest-Provision OPENED at v.22; structural irony with v.21 empty-lament recorded.",
      "description": "T7 is the first book-level discourse thread to OPEN since P02 (T3 at 1:9, T4 at 1:8, T6 at 1:6). It opens at v.22 'at the beginning of the barley harvest' and will close at P07 (2:23, end of barley and wheat harvests). Structural irony: the harvest opens as Naomi declares emptiness at v.21; the narrator stages the answer before Naomi can see it. Recorded as a STRUCTURAL_IRONY_HARVEST_OPENS_AS_LAMENT_ENDS high-risk entry, and as a discourse_thread_event in BCD-DELTA with state OPENED."
    },
    {
      "decision_id": "P04-D12",
      "decision": "Two divine-name doubling pattern (YHWH × 2 + Shaddai × 2 across v.20-21) preserved structurally.",
      "description": "Naomi names Shaddai twice (v.20 hemar-bittering; v.21 hera-evil) and YHWH twice (v.21 brought-back-empty; v.21 anah-bi-testified) — four divine attributions in two verses. The Shaddai-YHWH alternation is structurally significant: Shaddai is the agent of the bittering and the evil-doing; YHWH is the agent of the return-empty and the courtroom testimony. Recorded as a STRUCTURAL_DIVINE_NAME_DOUBLING_PATTERN high-risk entry. Reconstructor must preserve all four; do not collapse to a single divine-name."
    },
    {
      "decision_id": "P04-D13",
      "decision": "CB_0017 Daughter-in-Law-Kallah caught at v.22 during meaning-map drafting (not predicted in Step A).",
      "description": "The Step A prompt for P04 said 'CB_0017 kallah — probably not active in P04'. During meaning-map drafting the lexeme כַלָּתָהּ (kallatah, 'her daughter-in-law') was found at v.22 ('Ruth the Moabitess her daughter-in-law'). CB_0017 carries forward from P02 where it was first-occurrence-registered. Flagged in MEANING_COORDINATES P6 cb_flags with first_occurrence_in_book_here: false. Recorded as a methodology note: future Step A composition should scan source text for lexical occurrences of pre-declared CB lexemes, not only headline rhetorical features."
    },
    {
      "decision_id": "P04-D14",
      "decision": "cross_pericope_pair_verification reserved for figures only; CB cross-pericope status placed in known_limitations.",
      "description": "The Step D prompt (attention points 11-12) instructed CB_0024 + CB_0044 + CB_0026 cross-pericope DEFERRED notes into cross_pericope_pair_verification. The compilation-log.schema.json v0.3 defines cross_pericope_pair.fig_id with the figure_id pattern (^FIG_\\d{4}$), so the schema rejects CB entries there. The Step D instruction was inaccurate; the schema constraint takes precedence. Rerouted CB cross-pericope notes to known_limitations (visible per-entry), keeping the per-pericope cb_flags_active.first_occurrence_in_book_here marker for forward tracking. This is the durable Pilot 2 pattern for CB cross-pericope status: cross_pericope_pair_verification is figures-only; CB status lives in cb_flags_active + known_limitations. Methodology note recorded at _methodology/cross-pericope-pair-verification-figures-only.md for P05+ Step D drafting."
    },
    {
      "decision_id": "P04-D15",
      "decision": "Working TM-code renamed TM_BEGINNING_OF_BARLEY_HARVEST -> TM_BARLEY_HARVEST_BEGINNING at write-back to align with Wave 1 wiki convention.",
      "description": "Agent 3 generated the working time-code as TM_BEGINNING_OF_BARLEY_HARVEST. The Wave 1 wiki migration had pre-created the corresponding TM page under the name TM_BARLEY_HARVEST_BEGINNING (cross-referenced from TM_END_OF_BARLEY_HARVEST.md, _templates/sta-vocabulary.md, and _archive/tripod-sta-vocabulary-v0-2.md). The wiki convention follows the [HARVEST_KIND]_[POSITION] pattern (e.g., TM_END_OF_BARLEY_HARVEST). At P04 write-back the artifact ID was renamed to match the established convention rather than rename the wiki page (which would ripple through three other files). The rename was applied across all P04 working artifacts (step-A, step-B, step-C, step-D, step-E-meaning-coordinates, step-E-bcd-delta, step-E-compilation-log, step-F) by Marcia's explicit instruction at write-back time; the Gate F approval covered the structural decisions, not this naming detail. Recorded here to keep the audit trail explicit."
    }
  ],
  "vocabulary_additions": {
    "action_values": [
      { "value": "PROPOSED", "source": "first introduced in P04 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "REFUSED", "source": "first introduced in P04 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "RETURNED", "source": "first introduced in P04 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" }
    ],
    "proposition_kinds": [
      {
        "value": "CITY_STIRRED",
        "source": "P2 1:19b",
        "status": "CONFIRMED"
      },
      {
        "value": "NARRATOR_FRAME",
        "source": "P6 1:22",
        "status": "CONFIRMED"
      },
      {
        "value": "RENAMING",
        "source": "P4 1:20",
        "status": "CONFIRMED"
      }
    ],
    "scene_kinds": [
      {
        "value": "ARRIVAL_SCENE",
        "source": "S1 1:19",
        "status": "CONFIRMED"
      },
      {
        "value": "LAMENT_SCENE",
        "source": "S2 1:20-21",
        "status": "CONFIRMED"
      },
      {
        "value": "NARRATOR_FRAMING_CLOSE_SCENE",
        "source": "S3 1:22",
        "status": "CONFIRMED"
      }
    ],
    "presence_values": [
      {
        "value": "PRESENT_COLLECTIVE",
        "source": "B28 The-Whole-City and B24 Women-of-Bethlehem at S1; B24 at S2",
        "status": "CONFIRMED",
        "note": "Already in v0.4 canonical seed; confirmed for collective subjects."
      }
    ],
    "role_in_scene_beings": [
      {
        "value": "TOWNSPEOPLE",
        "source": "B28 @S1",
        "status": "CONFIRMED"
      }
    ],
    "referential_forms": [
      {
        "value": "MARA",
        "source": "B3 at P4 v.20 (Naomi proposing 'Mara')",
        "status": "PROPOSED",
        "note": "Bounded-open; specific to the Mara-renaming proposal."
      },
      {
        "value": "NAOMI",
        "source": "B3 at P5 v.21 ('Why do you call me Naomi')",
        "status": "PROPOSED",
        "note": "Bounded-open."
      },
      {
        "value": "RUTH_THE_MOABITESS_HER_DAUGHTER_IN_LAW",
        "source": "B9 at P6 v.22 (narrator returns to Moabite epithet after withholding)",
        "status": "PROPOSED",
        "note": "Bounded-open; specific to the FIG_0001 reactivation pattern."
      },
      {
        "value": "SHADDAI",
        "source": "B12 at P4 v.20 and P5 v.21 (first and second occurrence)",
        "status": "PROPOSED",
        "note": "Bounded-open; the archaic divine name Shaddai."
      }
    ],
    "other": [
      {
        "category": "OBJECT_KIND",
        "value": "BREAD_HOUSE_NAMING_ON_ARRIVAL",
        "source": "TH_BEIT_LECHEM_NAMING_ON_ARRIVAL at 1:19, 1:22",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "ARRIVAL_COMPLETION_VERB",
        "source": "TH_ARRIVAL_COMPLETION_VERB at 1:19a",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "COMMUNAL_STIRRING_VERB",
        "source": "TH_COMMUNAL_STIRRING_VERB at 1:19b",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "RECOGNITION_QUESTION_FORM",
        "source": "TH_RECOGNITION_QUESTION_FORM at 1:19c",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "REFUSAL_OF_OWN_NAME_FORM",
        "source": "TH_REFUSAL_OF_OWN_NAME_FORM at 1:20",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "PROPOSED_RENAMING_FORM",
        "source": "TH_PROPOSED_RENAMING_FORM at 1:20",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "MARA_NAME_FORM",
        "source": "TH_MARA_NAME_FORM at 1:20",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "HEMAR_BITTERING_VERB_WITH_DIVINE_SUBJECT",
        "source": "TH_HEMAR_BITTERING_VERB_WITH_DIVINE_SUBJECT at 1:20",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "ROOT_LEVEL_NAME_AND_VERB_PUN",
        "source": "TH_MARA_HEMAR_ROOT_PUN at 1:20",
        "status": "CONFIRMED",
        "note": "Already in v0.4 THING_KIND."
      },
      {
        "category": "OBJECT_KIND",
        "value": "FULL_STATE_DECLARATION",
        "source": "TH_FULL_STATE_DECLARATION at 1:21",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "RIQAM_EMPTY_LEXEME",
        "source": "TH_RIQAM_EMPTY_LEXEME at 1:21",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "ANTITHETICAL_STATE_WORD_PAIR",
        "source": "TH_FULL_EMPTY_ANTITHETICAL_PAIR at 1:21",
        "status": "CONFIRMED",
        "note": "Already in v0.4 THING_KIND."
      },
      {
        "category": "OBJECT_KIND",
        "value": "RHETORICAL_PROTEST_QUESTION_FORM",
        "source": "TH_RHETORICAL_PROTEST_QUESTION_FORM at 1:21",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "ANAH_BI_COURTROOM_FORM",
        "source": "TH_ANAH_BI_COURTROOM_FORM at 1:21",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "SHADDAI_DID_EVIL_FORM",
        "source": "TH_SHADDAI_DID_EVIL_FORM at 1:21",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "DOUBLED_DIVINE_NAME_LAMENT_PATTERN",
        "source": "TH_DOUBLED_DIVINE_NAME_LAMENT_PATTERN at 1:20-21",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "NARRATOR_SUMMARY_RETURN_VERB",
        "source": "TH_NARRATOR_SUMMARY_RETURN_VERB at 1:22",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "NARRATOR_EPITHET_REASSERTING_FOREIGNER_IDENTITY",
        "source": "TH_RUTH_THE_MOABITESS_NARRATOR_EPITHET at 1:22",
        "status": "PROPOSED",
        "note": "FIG_0001 reactivation in narrator voice after deliberate withholding at P02-P03."
      },
      {
        "category": "OBJECT_KIND",
        "value": "KINSHIP_FORM_KALLAH_SINGULAR",
        "source": "TH_KALLATAH_KINSHIP_FORM at 1:22",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "NARRATOR_SUMMARY_RETURN_FROM_ORIGIN",
        "source": "TH_NARRATOR_SUMMARY_RETURN_FROM_FIELDS_OF_MOAB at 1:22",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "ARRIVAL_AT_HARVEST_OPENING_FORM",
        "source": "TH_ARRIVAL_AT_HARVEST_OPENING_FORM at 1:22",
        "status": "PROPOSED"
      },
      {
        "category": "BEING_KIND",
        "value": "DIVINE_BEING",
        "source": "B12 Shaddai at 1:20",
        "status": "PROPOSED",
        "note": "First DIVINE_BEING kind in P04; carries forward to all divine-name references in later pericopes."
      },
      {
        "category": "BEING_KIND",
        "value": "FEMALE_COMMUNITY_VOICE",
        "source": "B24 Women-of-Bethlehem at 1:19",
        "status": "PROPOSED",
        "note": "Bounded-open; first occurrence."
      },
      {
        "category": "BEING_KIND",
        "value": "COLLECTIVE_COMMUNAL_BODY",
        "source": "B28 The-Whole-City at 1:19",
        "status": "PROPOSED",
        "note": "Bounded-open; first occurrence."
      },
      {
        "category": "TIME_KIND",
        "value": "AGRICULTURAL_SEASON_MARKER",
        "source": "TM_BARLEY_HARVEST_BEGINNING at 1:22",
        "status": "CONFIRMED",
        "note": "Already in v0.4 TIME_KIND."
      }
    ],
    "arc_elements": [
      {
        "value": "COMMUNITY_RECOGNITION_FAILURE",
        "source": "P04 level_1.arc_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      },
      {
        "value": "HARVEST_FRAMING_OPEN",
        "source": "P04 level_1.arc_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      },
      {
        "value": "NARRATOR_FRAMING_CLOSE",
        "source": "P04 level_1.arc_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      },
      {
        "value": "PUBLIC_ARRIVAL",
        "source": "P04 level_1.arc_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      },
      {
        "value": "PUBLIC_LAMENT",
        "source": "P04 level_1.arc_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      },
      {
        "value": "RENAMING_LAMENT",
        "source": "P04 level_1.arc_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      }
    ],
    "context_elements": [
      {
        "value": "DIVINE_CONTEXT",
        "source": "P04 level_1.context_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      },
      {
        "value": "PRIOR_ACTION_CONTEXT",
        "source": "P04 level_1.context_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      }
    ],
    "tone_elements": [
      { "value": "STILLED", "source": "P04 level_1.tone_elements - SC-0021 locus-strip from STILLED_AT_ARRIVAL", "status": "CONFIRMED" },
      { "value": "DECLARATIVE", "source": "P04 level_1.tone_elements convergent value (Gate-F 2026-05-30)", "status": "CONFIRMED" },
      { "value": "UNRESOLVED_AT_CLOSE", "source": "P04 level_1.tone_elements convergent value (Gate-F 2026-05-30)", "status": "CONFIRMED" }
    ],
    "pace_elements": [
      { "value": "RISES", "source": "P04 level_1.pace_elements - SC-0021 locus-strip from RISES_THROUGH_LAMENT", "status": "CONFIRMED" },
      { "value": "SETTLES", "source": "P04 level_1.pace_elements - SC-0021 locus-strip from SETTLES_AT_NARRATOR_FRAME_CLOSE", "status": "CONFIRMED" }
    ],
    "communicative_function_elements": [
      {
        "value": "REACTIVATES",
        "source": "level_1 communicative_function_elements",
        "status": "CONFIRMED"
      },
      {
        "value": "STAGES",
        "source": "level_1 communicative_function_elements",
        "status": "CONFIRMED"
      }
    ]
  },
  "proposition_kind_slot_sets": [
    {
      "proposition_kind": "WALKING_AND_ARRIVAL",
      "slot_set": [
        "walkers",
        "destination",
        "arrival_completion_form",
        "speech_act"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P1"
      ]
    },
    {
      "proposition_kind": "COMMUNAL_STIRRING_AT_ARRIVAL",
      "slot_set": [
        "stirred_collective",
        "about_whom",
        "at_arrival_to",
        "stirring_form",
        "speech_act"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P2"
      ]
    },
    {
      "proposition_kind": "ASKED_RHETORICAL_RECOGNITION_QUESTION",
      "slot_set": [
        "question_speakers",
        "question_addressee_party",
        "question_form",
        "target_being_in_question",
        "speech_act"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P3"
      ]
    },
    {
      "proposition_kind": "REFUSED_OWN_NAME_AND_PROPOSED_RENAMING",
      "slot_set": [
        "speaker",
        "addressees",
        "renaming_components"
      ],
      "component_record_shape": {
        "action": "required - REFUSED_USE_OF_OWN_NAME | PROPOSED_NEW_NAME | STATED_LAMENT_REASON_BITTERED_BY_DIVINE_AGENT",
        "list_position": "required - FIRST | SECOND | THIRD",
        "speech_act": "required - REFUSES_USE_OF_OWN_NAME | PROPOSES_NEW_NAME_FOR_SELF | ASCRIBES_AFFLICTION_TO_GOD_IN_LAMENT"
      },
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P4"
      ],
      "note": "Three-component compound; the more-specific closed-list speech_act values match each component's illocutionary force."
    },
    {
      "proposition_kind": "SPOKE_LAMENT_WITH_DOUBLED_DIVINE_ATTRIBUTION",
      "slot_set": [
        "speaker",
        "addressees",
        "lament_components",
        "doubled_divine_name_pattern_form"
      ],
      "component_record_shape": {
        "action": "required - STATED_FULL_EMPTY_ANTITHESIS | ASKED_RHETORICAL_QUESTION_AS_PROTEST | ASCRIBED_COURTROOM_TESTIMONY_TO_DIVINE_AGENT | ASCRIBED_HARM_TO_DIVINE_AGENT",
        "list_position": "required - FIRST through FOURTH",
        "speech_act": "required - ASCRIBES_AFFLICTION_TO_GOD_IN_LAMENT | ASKS_RHETORICAL_QUESTION_AS_PROTEST"
      },
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P5"
      ],
      "note": "Four-component lament; the YHWH-twice + Shaddai-twice structural doubling captured by doubled_divine_name_pattern_form at the proposition top-level alongside the per-component invoked_divine_agent slot."
    },
    {
      "proposition_kind": "NARRATOR_FRAME_RETURN_AND_ARRIVAL_AT_HARVEST_OPENING",
      "slot_set": [
        "return_components"
      ],
      "component_record_shape": {
        "action": "required - RETURNED | ARRIVED_AT",
        "list_position": "required - FIRST | SECOND",
        "speech_act": "required - STATES_AS_TRUE"
      },
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P6"
      ],
      "note": "Two-component compound narrator-frame; the FIG_0001 reactivation and FIG_0013 final close both land at this proposition."
    }
  ],
  "high_risk_register_audit": [
    {
      "id": "R1",
      "kind": "STRUCTURAL_DIVINE_NAME_FIRST_OCCURRENCE",
      "applies_to": "B12 Shaddai first occurrence in book at P4 (v.20) and P5 (v.21)",
      "note": "The archaic-poetic divine name Shaddai appears for the first time in the book at v.20 ('Shaddai has dealt very bitterly') and again at v.21 ('Shaddai has done evil to me'). Distinct from YHWH; pairs and alternates with YHWH across the two verses. Reconstructor must preserve Shaddai as a distinct divine-name (not flatten to a single divine-name across the four attributions).",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3A Scene 2 (B12 REFERENCED with first-occurrence marker); Section 3C Scene 2 (TH_HEMAR_BITTERING_VERB_WITH_DIVINE_SUBJECT + TH_SHADDAI_DID_EVIL_FORM)"
    },
    {
      "id": "R2",
      "kind": "STRUCTURAL_DIVINE_NAME_DOUBLING_PATTERN",
      "applies_to": "YHWH × 2 + Shaddai × 2 across v.20-21",
      "note": "Naomi names Shaddai twice (v.20 bittering; v.21 evil-doing) and YHWH twice (v.21 brought-back-empty; v.21 testified-against). Four divine attributions in two verses. The Shaddai-YHWH alternation is structurally significant: Shaddai for the bittering and harm; YHWH for the return-empty and the courtroom testimony. Reconstructor must preserve all four; do not collapse to a single divine-name.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3C Scene 2 (TH_DOUBLED_DIVINE_NAME_LAMENT_PATTERN); Section 4 Propositions 4 and 5"
    },
    {
      "id": "R3",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0082 Naomi-Mara-Name-Substitution at P4 (v.20)",
      "note": "REQUIRED keep-image. Naomi refuses her name Naomi (meaning 'sweet') and proposes Mara (meaning 'bitter'). The substitution names her experience and refuses her given identity. The reconstructor must preserve both halves: the refusal and the proposal. The narrator does not adopt the new name (see R9); the proposal stands as Naomi's voice without becoming her actual referential form going forward.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 5B Figure Flags; Section 3C Scene 2 (TH_REFUSAL_OF_OWN_NAME_FORM + TH_PROPOSED_RENAMING_FORM + TH_MARA_NAME_FORM)"
    },
    {
      "id": "R4",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0083 Mara-Hemar-Root-Pun at P4 (v.20)",
      "note": "PREFERRED keep-image. Naomi names herself 'Mara' (bitter, noun-form) using the verb that names her experience: 'hemar' (he-has-bittered). The root mrr unites name and verb. Many target languages cannot carry the pun without paratext. If a target language permits root-level word-play between the proposed name and the verb of cause, prefer it; otherwise the pun is preserved in paratext rather than in the reconstruction.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 5B Figure Flags; Section 3C Scene 2 (TH_MARA_HEMAR_ROOT_PUN)"
    },
    {
      "id": "R5",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0084 Full-and-Empty-Antithesis at P5 (v.21)",
      "note": "REQUIRED keep-image. 'I went out full, and YHWH brought me back empty' — first antithetical state-word pair in the book. The pair is structurally placed across the journey-arc (out = full; back = empty). The Hebrew empty-handed lexeme riqam (רֵיקָם) is specifically the antonym Naomi uses; it recurs at P10 in the structural answer. Reconstructor must preserve both halves of the antithesis and the journey-arc placement.",
      "required_in_audit": true,
      "do_not_decide": true,
      "carries_forward_to": "P10_compilation_log",
      "source_in_meaning_map": "Section 5B Figure Flags; Section 3C Scene 2 (TH_FULL_EMPTY_ANTITHETICAL_PAIR + TH_FULL_STATE_DECLARATION + TH_RIQAM_EMPTY_LEXEME)"
    },
    {
      "id": "R6",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0086 Shaddai-Did-Evil-to-Me at P5 (v.21)",
      "note": "PREFERRED keep-image. Naomi closes her lament with 'Shaddai has done evil to me' — a theological-image figure ascribing harm to the divine. Parallels v.20's 'Shaddai has dealt bitterly' as the bracketing pair around the YHWH attributions in v.21. Reconstructor must preserve Shaddai as the agent of harm in this specific construction.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 5B Figure Flags; Section 3C Scene 2 (TH_SHADDAI_DID_EVIL_FORM)"
    },
    {
      "id": "R7",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0088 Empty-Lament-at-Harvest-Arrival across P5 (v.21) and P6 (v.22); cross-pericope close at P05",
      "note": "PREFERRED keep-image. Structural irony: Naomi declares herself empty at v.21 at the very moment the narrator opens the barley-harvest frame at v.22. The harvest is the answer Naomi's lament does not yet see. Cross-pericope pair: opens at P04; closes at P05 (Boaz's field arrival). Reconstructor must allow the irony to remain visible — do not soften Naomi's empty-lament with hint of the harvest answer, and do not delay the harvest-frame opening.",
      "required_in_audit": true,
      "carries_forward_to": "P05_compilation_log",
      "source_in_meaning_map": "Section 5B Figure Flags; Section 3C Scene 2 + Scene 3 (TH_FULL_EMPTY_ANTITHETICAL_PAIR + TH_ARRIVAL_AT_HARVEST_OPENING_FORM)"
    },
    {
      "id": "R8",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0006 Shaddai-Divine-Name within-pericope pair at P4 (v.20) and P5 (v.21)",
      "note": "PREFERRED keep-image. The archaic-poetic divine name Shaddai is the figure's lexical anchor. Within-pericope pair: opens at v.20, closes at v.21. Reconstructor must preserve the Shaddai form (not substitute YHWH or the generic 'God') both times.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 5B Figure Flags; Section 3A Scene 2 (B12 REFERENCED)"
    },
    {
      "id": "R9",
      "kind": "STRUCTURAL_NON_ADOPTION_OF_PROPOSED_RENAMING",
      "applies_to": "Naomi's 'Mara' proposal at v.20 not adopted by the narrator at v.22",
      "note": "Naomi proposes 'Mara' at v.20 and reinforces the refusal of 'Naomi' at v.21. The narrator immediately uses 'Naomi' again at v.22. The non-adoption is structurally significant: the narrator does not endorse Naomi's self-renaming. Reconstructor must encode the proposal as Naomi's voice without applying the new name in narrator voice or in later references. Naomi continues to be called Naomi for the rest of the book.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3A Scene 3 (B3 referential_form NAMED at v.22 after PROPOSED_NEW_NAME at v.20-21); Section 4 Propositions 4 and 6"
    },
    {
      "id": "R10",
      "kind": "REFERENTIAL_FORM_REACTIVATION_AFTER_WITHHOLDING",
      "applies_to": "FIG_0001 Ruth-the-Moabitess narrator-epithet returns at v.22 after deliberate withholding at P02 and P03",
      "note": "The narrator returns to the Moabite epithet at the public-arrival moment in Bethlehem. The structural counterpart to P03 R7 SIGNIFICANT_ABSENCE (which recorded the withholding at the vow moment). Reconstructor must restore the epithet at v.22 — Ruth publicly enters Israel as the Moabitess. The withholding-and-reactivation pattern is structurally meaningful across the chapter 1 arc.",
      "required_in_audit": true,
      "do_not_decide": true,
      "carries_forward_to": "P05_compilation_log",
      "source_in_meaning_map": "Section 3A Scene 3 (B9 referential_form RUTH_THE_MOABITESS_HER_DAUGHTER_IN_LAW); Section 3C Scene 3 (TH_RUTH_THE_MOABITESS_NARRATOR_EPITHET); Section 5B (FIG_0001 active at P6)"
    },
    {
      "id": "R11",
      "kind": "CROSS_PERICOPE_PAIRING_CLOSED_HERE",
      "applies_to": "FIG_0013 Bread-house-in-Famine third occurrence and final close at v.22",
      "note": "PREFERRED keep-image. Opened P01 1:1 (famine in beit-lechem); closed first at P02 1:6 (YHWH gives bread to his people); reaches third occurrence and final close at P04 v.22 when 'they came to Bethlehem at the beginning of the barley harvest' lands the bread-house name against the harvest-frame opening. Cross-pericope close VERIFIED. Reconstructor must preserve the lexical bread-house name and let the harvest-frame answer land structurally.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 5B Figure Flags; Section 3C Scene 1 (TH_BEIT_LECHEM_NAMING_ON_ARRIVAL) and Scene 3 (TH_ARRIVAL_AT_HARVEST_OPENING_FORM)"
    },
    {
      "id": "R12",
      "kind": "SIGNIFICANT_ABSENCE",
      "applies_to": "Recognition-failure cause not inferred at v.19",
      "note": "The narrator does not say why the women cannot recognize Naomi. Grief, age, demeanor, appearance are all possible; the narrator withholds. Reconstructor must not fill the cause. The recognition-failure stands as is.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3 Scene 1 significant_absence"
    },
    {
      "id": "R13",
      "kind": "STRUCTURAL_ABSENCE_OF_FAMILY_NAMING_IN_LAMENT",
      "applies_to": "Naomi's 'I went out full' at v.21 implies the household she left with but does not name them",
      "note": "Naomi's lament implicitly references Elimelech, Mahlon, Chilion (the household she went out with) through 'I went out full' but does NOT name any of them. The narrator's v.22 return-frame names only Naomi and Ruth. Wife-pairing withholding from P01 1:4 also carries forward. Reconstructor must preserve the family-naming silence — do not insert names of the dead into Naomi's lament or the return-frame.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3 Scene 2 significant_absence; Section 3C Scene 2 (TH_FULL_STATE_DECLARATION 'I went out full')"
    },
    {
      "id": "R14",
      "kind": "STRUCTURAL_IRONY_HARVEST_OPENS_AS_LAMENT_ENDS",
      "applies_to": "v.22 harvest-opening lands one verse after Naomi's empty-lament at v.21",
      "note": "Structural irony: the narrator stages the harvest-frame opening at the verse immediately following Naomi's declaration of emptiness. Naomi cannot see the answer; the narrator places it before the reader. Reconstructor must allow the irony to remain visible — keep the empty-lament intact at v.21 and let the harvest-frame open at v.22 without softening either.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 2.4 Communicative Function; Section 3C Scene 2 + Scene 3 (TH_FULL_EMPTY_ANTITHETICAL_PAIR + TH_ARRIVAL_AT_HARVEST_OPENING_FORM)"
    },
    {
      "id": "R15",
      "kind": "DISCOURSE_THREAD_OPENED",
      "applies_to": "T7 Harvest-Provision opens at v.22",
      "note": "T7 opens at 'the beginning of the barley harvest' and will close at P07 (2:23, end of barley and wheat harvests). First book-level discourse thread to open since P02 (T3, T4, T6). Reconstructor must preserve the barley-harvest frame as the temporal anchor that opens the next pericopes' work.",
      "required_in_audit": true,
      "carries_forward_to": "P05_through_P07_compilation_logs",
      "source_in_meaning_map": "Section 2.4 Communicative Function; Section 3D Scene 3 (TM_BARLEY_HARVEST_BEGINNING); tracked in BCD-DELTA discourse_thread_events"
    },
    {
      "id": "R16",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "v.22 narrator-frame does three structural things at once",
      "note": "v.22 closes the pericope with (1) return-summary that re-establishes the narrator's 'Naomi' over Naomi's self-renaming, (2) reactivation of the Moabite epithet on Ruth after deliberate P02-P03 withholding, and (3) opening of the harvest-frame against which Naomi's lament has just been spoken. All three converge at this one proposition. Reconstructor must preserve all three — the narrator's economy at v.22 is structurally significant.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3 Scene 3 (3C + 3D + 3F); Section 4 Proposition 6"
    }
  ],
  "cross_pericope_pair_verification": {
    "pairs": [
      {
        "fig_id": "FIG_0013",
        "opens_at": "P01 P2 (1:1)",
        "closes_at": "P04 P6 (1:22) — third occurrence and final close",
        "verification_status": "VERIFIED",
        "note": "Final close. Opened at P01 1:1 (famine in beit-lechem); closed first at P02 1:6 (YHWH gives bread to his people); third occurrence and final close at P04 v.22 (bread-house name lands against barley-harvest opening). Both the lexical bread-house name and the structural provision-pattern converge at v.22."
      },
      {
        "fig_id": "FIG_0001",
        "opens_at": "P01 P10 (1:4)",
        "closes_at": "Withheld P02-P03; reactivates P04 P6 (1:22); continues to recur at P05, P07, P11, P12",
        "verification_status": "DEFERRED",
        "note": "FIG_0001 reactivates at P04 v.22 after deliberate P02-P03 withholding (P03 R7 SIGNIFICANT_ABSENCE). The cross-pericope arc continues — figure full close DEFERRED to P12. The P04 reactivation is recorded in high_risk_register_audit R10."
      },
      {
        "fig_id": "FIG_0088",
        "opens_at": "P04 P5-P6 (1:21-22)",
        "closes_at": "P05 (Boaz's field arrival) pending",
        "verification_status": "DEFERRED",
        "note": "Empty-lament-at-harvest-arrival structural irony. Opens here; closes at P05 when Ruth gleans in Boaz's field and the harvest's actual provision begins to land."
      },
      {
        "fig_id": "FIG_0012",
        "opens_at": "P02 P15 (1:14)",
        "closes_at": "P07 (2:23) pending",
        "verification_status": "DEFERRED",
        "note": "Carries forward from P02. Not lexically active in P04. The dabaq image-rhyme tracks the dabaq lexeme, which closes at 2:23."
      },
      {
        "fig_id": "FIG_0006",
        "opens_at": "P04 P4 (1:20)",
        "closes_at": "P04 P5 (1:21) — within-pericope pair",
        "verification_status": "VERIFIED",
        "note": "Within-pericope pair. Shaddai named twice on Naomi's lips at v.20 and v.21."
      },
      {
        "fig_id": "FIG_0082",
        "opens_at": "P04 P4 (1:20)",
        "closes_at": "P04 P4 (1:20) — within-pericope single-occurrence",
        "verification_status": "VERIFIED",
        "note": "Naomi-Mara name substitution; REQUIRED keep-image; non-adoption recorded in high_risk R9."
      },
      {
        "fig_id": "FIG_0083",
        "opens_at": "P04 P4 (1:20)",
        "closes_at": "P04 P4 (1:20) — within-pericope single-occurrence",
        "verification_status": "VERIFIED",
        "note": "Mara-Hemar root-pun; PREFERRED keep-image. Pun is preserved via paratext in most target languages."
      },
      {
        "fig_id": "FIG_0084",
        "opens_at": "P04 P5 (1:21)",
        "closes_at": "P04 P5 (1:21) — within-pericope single-occurrence; concept recurs at P10",
        "verification_status": "VERIFIED",
        "note": "Full-and-empty antithetical state-word pair; REQUIRED keep-image. The concept (CB_0024, CB_0044) recurs at P10 — pair verification deferred until P10 compilation."
      },
      {
        "fig_id": "FIG_0086",
        "opens_at": "P04 P5 (1:21)",
        "closes_at": "P04 P5 (1:21) — within-pericope single-occurrence",
        "verification_status": "VERIFIED",
        "note": "Shaddai-did-evil-to-me theological-image; PREFERRED keep-image."
      },
      {
        "fig_id": "FIG_0072",
        "opens_at": "P03 P3 (1:16b-c)",
        "closes_at": "P03 P3 — within-pericope pair completed at P03",
        "verification_status": "VERIFIED",
        "note": "P03 within-pericope pair; no P04 activity. Recorded for completeness of cross-pericope figure status across the first four pericopes."
      },
      {
        "fig_id": "FIG_0074",
        "opens_at": "P03 P3 (1:17a)",
        "closes_at": "P03 P3 — within-pericope pair completed at P03",
        "verification_status": "VERIFIED",
        "note": "P03 within-pericope pair; no P04 activity."
      },
      {
        "fig_id": "FIG_0075",
        "opens_at": "P03 P4 (1:17b)",
        "closes_at": "P03 P4 — single-occurrence at P03; cross-canonical recurrences outside Ruth",
        "verification_status": "VERIFIED",
        "note": "P03 self-curse oath formula; cross-pericope pair with 3:13 (Boaz's oath) DEFERRED."
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
      "ASKS_RHETORICAL_QUESTION_OF_SURPRISED_RECOGNITION",
      "REFUSES_USE_OF_OWN_NAME",
      "PROPOSES_NEW_NAME_FOR_SELF",
      "ASCRIBES_AFFLICTION_TO_GOD_IN_LAMENT",
      "ASKS_RHETORICAL_QUESTION_AS_PROTEST"
    ],
    "negation_not_double_encoded": "N/A — no DIRECTS_HEARER_NOT_TO_DO in P04 (Naomi's refusal uses REFUSES_USE_OF_OWN_NAME, the more-specific closed-list value, sidestepping the double-negation rule)",
    "cross_pericope_cross_refs_present_on_correct_propositions": true,
    "empty_slot_rule_applied_to_times_in_scene": true,
    "discourse_threads_tracked_in_audit_only": true,
    "known_limitations_tracked_in_audit_only": true,
    "high_risk_register_complete": true,
    "every_high_risk_entry_traces_to_meaning_map": true,
    "significant_absences_traced_to_meaning_map": true,
    "no_content_added_beyond_meaning_map": true,
    "wife_pairing_withholding_enforced": true,
    "b_codes_match_bcd_version": "All B-codes verified against ruth_pilot_BCD_v0_3 plus carry-forwards (B31 from P02; B10 from P02) plus three new at P04 (B12 Shaddai, B24 Women-of-Bethlehem, B28 The-Whole-City).",
    "registry_additions_extracted_to_bcd_delta": true,
    "no_reviewer_facing_prompts_in_compilation_log": true
  },
  "known_limitations": [
    "TM_BARLEY_HARVEST_BEGINNING is a working time-code pending formal TM-code assignment in BCD v0.4. Parallels P01's PL_HA_ARETZ pattern and P02's PL_LAND_OF_JUDAH pattern (working codes for entities not yet in the formal BCD registry). Renamed from TM_BEGINNING_OF_BARLEY_HARVEST to TM_BARLEY_HARVEST_BEGINNING at write-back to align with the Wave 1 wiki convention; see P04-D15.",
    "CB_0017 Daughter-in-Law-Kallah was not predicted in the P04 Step A prompt (Step A said 'probably not active in P04') but was caught during meaning-map drafting via the v.22 kallatah lexeme. Recorded as a lesson for future Step A composition: scan source text for lexical occurrences of pre-declared CB lexemes, not only headline rhetorical features.",
    "FIG_0001 cross-pericope pair verification remains DEFERRED; figure recurs across P04, P05, P07, P11, P12. P04 reactivation after withholding is recorded in high_risk R10 with carries_forward_to P05.",
    "FIG_0088 cross-pericope pair verification DEFERRED to P05 (Boaz's field arrival), when the harvest-provision's structural answer to Naomi's empty-lament begins to land.",
    "CB_0024 Full-and-Empty + CB_0044 Riqam-Empty cross-pericope pair verification DEFERRED to P10 (3:17, Boaz sends Ruth back 'not empty').",
    "CB_0026 Barley-Harvest-Harvest-Frame cross-pericope close DEFERRED to P07 (2:23 end of barley and wheat harvests). Recurs at P10.",
    "Six new proposition_kinds at P04 (WALKING_AND_ARRIVAL, COMMUNAL_STIRRING_AT_ARRIVAL, ASKED_RHETORICAL_RECOGNITION_QUESTION, REFUSED_OWN_NAME_AND_PROPOSED_RENAMING, SPOKE_LAMENT_WITH_DOUBLED_DIVINE_ATTRIBUTION, NARRATOR_FRAME_RETURN_AND_ARRIVAL_AT_HARVEST_OPENING) are bounded-open. Three new scene_kinds (PUBLIC_ARRIVAL_AND_RECOGNITION_SCENE, PUBLIC_LAMENT_AND_RENAMING_SCENE, NARRATOR_FRAMING_CLOSE_SCENE) are bounded-open. Multiple new object_kinds and referential_forms drift-warn against the canonical P01 seed; all expected to be accepted at Gate F.",
    "community_verified and translation_team_verified remain false; this is a pilot compilation."
  ]
}
```

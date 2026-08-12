---
type: "sta-compilation-log"
pericope: "P05"
pericope-title: "Boaz introduced as kinsman; Ruth's gleaning initiative; her chance arrival in Boaz's portion; the foreman's report"
source-meaning-map: [[P05-Ruth-2-1-7]]
source-meaning-coordinates: [[P05-Ruth-2-1-7-MEANING-COORDINATES]]
related-bcd-delta: [[P05-Ruth-2-1-7-BCD-DELTA]]
status: "valid"
pilot: "pilot-2"
---

# P05 — Ruth 2:1–7 — COMPILATION-LOG

This page renders the COMPILATION-LOG JSON as a wiki-addressable artifact. The canonical JSON file lives in the source folder. Registry promotions for this pericope live in the paired BCD-DELTA page.

```json
{
  "sta_id": "ruth_pericope_05_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Ruth 2:1-7",
  "pericope_id": "P05",
  "pericope_title": "Boaz introduced as kinsman; Ruth's gleaning initiative; her chance arrival in Boaz's portion; the foreman's report",
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
  "confidence_overall_note": "P05 compiles cleanly with 9 propositions across 4 scenes. The pericope opens chapter 2 as the first field-scene of the book and surfaces a high-density first-occurrence load: B13 Boaz introduced before he acts (second male protagonist; first occurrence; the v.1 narrator-parenthetical structurally bookends with his named acquisition at 4:9-10); B14 Harvesters + B15 The-Foreman first occurrences (B15 named-by-role only); B29 Clan-of-Elimelech first occurrence with twice-naming bracket at v.1 + v.3; chayil cross-pair opens (CB_0032 + FIG_0090 + FIG_0134; cross-pericope close DEFERRED to P09 3:11); miqreh chance-providence ambiguity preserved at P5 with agent_named: NONE; FIG_0088 empty-lament-at-harvest-arrival cross-pericope close VERIFIED at P5; FIG_0001 reactivation continues — narrator-epithet at P2 v.2 + third-party voice at P9 v.6 (first time a Bethlehemite speaks the Moabite epithet aloud); four new PL working codes (PL5, PL5_BOAZ_PORTION, PL_HA_BAYIT_FIELD_SHELTER textually-disputed, PL_NAOMIS_DWELLING implicit) per P02 PL_LAND_OF_JUDAH precedent. Speech_act mapping uses the more-specific closed-list values: REQUESTS_PERMISSION_TO_DO + GRANTS_PERMISSION_TO_DO for the v.2 initiative-and-release; WISHES_FOR_HEARER × 2 for the v.4 greeting exchange; ASKS_KINSHIP_BELONGING_QUESTION for v.5; REPORTS_PRIOR_SPEECH_REQUEST + nested REQUESTS_PERMISSION_TO_DO for the foreman's quoted-Ruth speech at v.7. Scene-level INTIMATE override on S2 only (mirroring P02-D1 / P03-D1 / P04-D1 pattern). Bounded-open drift expected (9 new proposition_kinds for the introduction-formula + initiative + chance-arrival + greeting-exchange + foreman-report compound events; 4 new scene_kinds; multiple new role_in_scene + object_kind values + 3 new being_kinds (GROUP_OF_WORKERS + NAMED_BY_ROLE_FUNCTIONARY + LEGAL_RELATIONAL_KIN_GROUP — PERSON is canonical from P01 and not counted) + 4 new place_kinds). No closed-list violations. Within-day duration 'from morning until now' at v.7 encoded as 3C content-object per P01 TM_TEN_YEARS precedent; no new TM-code coined.",
  "compilation_decisions": [
    {
      "decision_id": "P05-D1",
      "decision": "Pericope-level register INFORMAL_CASUAL with scene-level INTIMATE override on S2 only.",
      "description": "Per hard rule, biblical narrator voice is INFORMAL_CASUAL at the pericope level. Scene 2 (Ruth-Naomi interior dialogue at v.2) carries scene-level INTIMATE: daughter-in-law and mother-in-law speaking face-to-face inside their dwelling, no community audience and no institutional venue. The relational-close register fits the moment better than INFORMAL_CASUAL even though the speech contains a request-and-release exchange. Scenes 1, 3, 4 stay at INFORMAL_CASUAL narrator default. Pattern mirrors P02-D1 / P03-D1 / P04-D1 scene-level INTIMATE overrides for relational moments inside narrator-frame pericopes. The v.4 greeting exchange holds covenant-blessing weight at the form level; this is carried by figure flags (FIG_0092, FIG_0093) and CB_0008, not by elevated register."
    },
    {
      "decision_id": "P05-D2",
      "decision": "Meaning-map P1 narrator-parenthetical compiled as one compound NARRATOR_INTRODUCES_KINSMAN_BEFORE_ACTION proposition with four introduction-components.",
      "description": "The v.1 narrator-parenthetical does four structural things in one continuous narrator-introduction: (a) positions Boaz through Naomi's kinship-anchor to her dead husband; (b) introduces him as ish gibbor chayil (person of standing); (c) places him in the legal-relational kin-group (clan of Elimelech); (d) names him last (Boaz). Compiled as one compound proposition with four introduction-components rather than four separate propositions. Rationale: the four moves form a single narrator-economical introduction in chronicle pattern (relation → attribute → clan → name). Mirrors P02 P12 / P03 P3 / P04 P5 compound-speech patterns at the structural level (single illocutionary event with multiple sub-actions)."
    },
    {
      "decision_id": "P05-D3",
      "decision": "Meaning-map P7 greeting exchange + P9 foreman report compiled as compound propositions.",
      "description": "P7 (v.4 greeting exchange) compiled as one EXCHANGED_GREETING_AND_RETURN_BLESSING proposition with two greeting-components (Boaz greets + harvesters return-bless); each component carries speech_act WISHES_FOR_HEARER. P9 (v.6-7 foreman report) compiled as one FOREMAN_REPORTED_IDENTITY_AND_WORK_PATTERN proposition with five report-components (identity-by-ethnic-epithet / identity-by-return-with-kinship-anchor / quoted-prior-request / work-pattern-persistence / disputed-shelter-clause); component speech_acts: STATES_AS_TRUE for narrator-reported facts; REPORTS_PRIOR_SPEECH_REQUEST for the quoted-prior-request component (with nested quoted_prior_speech_act REQUESTS_PERMISSION_TO_DO for Ruth's reported request). Compound proposition patterns parallel P02 P12 / P03 P3 / P04 P5 + P4 precedent."
    },
    {
      "decision_id": "P05-D4",
      "decision": "B13 Boaz referential_form at S1 set to NAMED per external reviewer recommendation endorsed at Gate C close.",
      "description": "The Wave 1 B13-Boaz.md page pre-declared three referential_forms: NAMED, NAMED_AT_FIRST_SIGHT_WITH_CHAYIL_ATTRIBUTE, LEGAL_PERFORMATIVE_NAMING. At Gate C close, the external reviewer recommended NAMED for the S1 introduction-frame; the recommendation was endorsed. Rationale: the cleaner two-layer encoding (NAMED + FIG_0090 figure_flag + TH_ISH_GIBBOR_CHAYIL_INTRODUCTION_FORMULA structural object in S1 objects_in_scene) keeps the bounded-open referential_form vocabulary minimal at the MEANING_COORDINATES layer. The chayil-attribute weight is carried by FIG_0090 + CB_0032 + FIG_0134 (chayil cross-pair tracker). Boaz uses NAMED throughout S1-S4."
    },
    {
      "decision_id": "P05-D5",
      "decision": "B9 Ruth referential_form at S2 set to NAMED for consistency with P05-D4 B13 decision; FIG_0001 carries the Moabite-epithet weight.",
      "description": "The narrator at v.2 names Ruth at the speech-event head as 'Ruth the Moabitess.' Two options surfaced at Step D attention point 11: (a) coin a bounded-open referential_form NAMED_WITH_MOABITE_EPITHET_AT_SPEECH_HEAD; (b) use NAMED and let FIG_0001 figure_flag carry the epithet weight. Chose option (b) for consistency with P05-D4 (same two-layer minimal-bounded-open principle). Ruth uses NAMED throughout. FIG_0001 figure_flag on P2 + P9 carries the Moabite-epithet weight across the pericope; the third-party-voice reactivation at P9 v.6 is captured in high_risk_register_audit R10."
    },
    {
      "decision_id": "P05-D6",
      "decision": "B15 The-Foreman referential_form NAAR_NITSAV_AL_HAQOTSRIM used at S4 throughout per pre-declared B15 BCD page.",
      "description": "The Wave 1 B15-The-Foreman.md page pre-declares the single referential_form NAAR_NITSAV_AL_HAQOTSRIM for B15. The foreman is named only by role ('the young man standing over the harvesters') at both v.5 (Boaz's address) and v.6 (the narrator's identifying-clause for the answerer); no personal name is given anywhere in P05. Use this single referential_form throughout S4. The role-only naming is structurally significant; recorded in high_risk_register_audit R14 NAMED_BY_ROLE_ONLY_NO_PERSONAL_NAME."
    },
    {
      "decision_id": "P05-D7",
      "decision": "Four new B-codes registered at P05 with source-text-distinguished kinds: B13 PERSON (Boaz), B14 GROUP_OF_WORKERS (Harvesters), B15 NAMED_BY_ROLE_FUNCTIONARY (The-Foreman), B29 LEGAL_RELATIONAL_KIN_GROUP (Clan-of-Elimelech).",
      "description": "B13 Boaz is the second male protagonist; first occurrence at v.1; PERSON kind with gender MALE, ethnic_identity ISRAELITE, clan_identity EPHRATHITE, home_place PL1, presence_in_book ACTIVE_THROUGH_BOOK. B14 Harvesters is Boaz's working community; first occurrence at v.3 (referenced) and v.4 (interacted with); GROUP_OF_WORKERS kind; presence_in_book ACTIVE_THROUGH_P05_P06. B15 The-Foreman is Boaz's field overseer; first occurrence at v.5; NAMED_BY_ROLE_FUNCTIONARY kind; presence_in_book ACTIVE_AT_P05_ONLY. B29 Clan-of-Elimelech is the legal-relational kin-group that grounds the kinsman-redeemer obligation; first occurrence at v.1; LEGAL_RELATIONAL_KIN_GROUP kind; presence_in_book ACTIVE_THROUGH_BOOK. Source-text discipline: do not merge B14 (the working community) with B15 (the foreman); do not merge B29 (the clan as a relational unit) with B2 (the individual eponym)."
    },
    {
      "decision_id": "P05-D8",
      "decision": "Four new PL working-codes registered at P05 per P02 PL_LAND_OF_JUDAH / P04 TM_BARLEY_HARVEST_BEGINNING working-code pattern: PL5 Field, PL5_BOAZ_PORTION, PL_HA_BAYIT_FIELD_SHELTER, PL_NAOMIS_DWELLING.",
      "description": "PL5 Field — the agricultural field as a place-type; first occurrence at v.2 (Ruth proposes 'to the field') and v.3 (Ruth gleans). PL5_BOAZ_PORTION — sub-place of PL5; Boaz's named portion at v.3; the specific portion Ruth chances upon. PL_HA_BAYIT_FIELD_SHELTER — the shelter at the field; first occurrence at v.7 in the foreman's report; precise referent and Hebrew syntax textually disputed at v.7b across major commentaries (held open in the artifact). PL_NAOMIS_DWELLING — Naomi's dwelling in Bethlehem; PRESENT_IMPLIED at S2 v.2 interior dialogue setting; not lexically named in the source text; working code for the implicit private-household setting that recurs across multiple chapter-2/3/4 interior scenes. All four flagged in known_limitations as working codes pending formal BCD assignment in BCD v0.4."
    },
    {
      "decision_id": "P05-D9",
      "decision": "Zero new TM-codes at P05; within-day duration 'from morning until now' at v.7 encoded as 3C content-object per P01 TM_TEN_YEARS precedent.",
      "description": "TM_BARLEY_HARVEST_BEGINNING carries forward from P04 v.22 as the active temporal frame for P05; not lexically named at P05 surface text; not re-added to BCD-DELTA to_bcd.times. The within-day duration 'from morning until now' at v.7 (inside the foreman's quoted report on Ruth's work-pattern) is encoded as a 3C content-object (TH_WITHIN_DAY_DURATION_FROM_MORNING_UNTIL_NOW) rather than as a scene-setting time frame; this follows the P01 TM_TEN_YEARS precedent (approximate-duration phrase in objects_in_scene rather than times_in_scene). No new TM-code coined at P05."
    },
    {
      "decision_id": "P05-D10",
      "decision": "Miqreh chance-providence frame at P5 v.3 encoded with agent_named: NONE; do_not_decide: true; providence-coincidence ambiguity preserved.",
      "description": "The vayyiqer-miqreha double-cognate construction at v.3 is the narrator's signature providence-without-naming move. Encoded in MEANING_COORDINATES P5 with agent_named: NONE; do not attribute to YHWH. The structural object TH_VAYYIQER_MIQREHA_DOUBLE_COGNATE_CONSTRUCTION captures the construction in S3 objects_in_scene. Recorded as high_risk_register_audit R4 STRUCTURAL_PROVIDENCE_WITHOUT_NAMING_AGENT_WITHHELD with do_not_decide: true. The construction holds ambiguity between coincidence and providence; flattening to plain 'she happened to come' or to plain 'YHWH led her' loses the irony in either direction."
    },
    {
      "decision_id": "P05-D11",
      "decision": "FIG_0088 Empty-Lament-at-Harvest-Arrival cross-pericope close placed at P5 v.3 (chance-arrival in kinsman's portion); verification_status VERIFIED.",
      "description": "FIG_0088 opened at P04 v.21-22 (Naomi's empty-lament at v.21 + the narrator's harvest-frame opening at v.22). The Step D attention point 16 surfaced a question between two candidate close-triggers: P5 v.3 (chance-arrival lands in the kinsman's portion) versus P9 v.7 (foreman's first-recognition of her work-pattern reveals provision-already-flowing). Placed at P5 v.3 — rationale: the structural arrival-in-the-kinsman's-portion is the moment the provision-frame engages structurally, even before any character or narrator observes it; the harvest's actual provision begins to land when Ruth arrives in the field-portion of the kinsman who will redeem the line. P9 v.7 is a later observation of work already in progress; P5 v.3 is the structural arrival-moment. Both readings are defensible; placing at P5 keeps the close at the structural-frame level rather than at the observation level."
    },
    {
      "decision_id": "P05-D12",
      "decision": "B29 Clan-of-Elimelech twice-naming at S1 v.1 + S3 v.3 encoded as deliberate narrator bracketing of Ruth's chance-arrival with the kin-frame.",
      "description": "The narrator names the clan of Elimelech at v.1 (Boaz's introduction-frame) and again at v.3 (immediately after the vayyiqer-miqreha construction — 'who was of the clan of Elimelech'). The twice-naming is structurally significant: the narrator brackets Ruth's chance-arrival with the same kin-frame at both ends, so the audience sees the kin-link the characters do not yet see. Encoded in MEANING_COORDINATES with B29 REFERENCED at S1 + S3 beings_in_scene, the clan-locator phrase as a structural object at S1 (TH_CLAN_OF_ELIMELECH_LOCATOR_PHRASE), and the clan-frame restatement at S3 (TH_CLAN_FRAME_RESTATED_AT_CHANCE_ARRIVAL). Recorded as high_risk_register_audit R2 STRUCTURAL_BRACKETING_CLAN_FRAME."
    },
    {
      "decision_id": "P05-D13",
      "decision": "Foreman omits Ruth's personal name at v.6-7; identification by ethnic-epithet + kin-relation + work-pattern only.",
      "description": "The foreman's report at v.6-7 identifies Ruth as 'a Moabite young woman, the one who returned with Naomi from the fields of Moab,' quotes her gleaning-request, and describes her work-pattern. The name 'Ruth' does not appear in the foreman's voice. The narrator-epithet at v.2 ('Ruth the Moabitess said to Naomi') is in narrator voice; v.6 is the first occurrence of the Moabite epithet in any character's quoted speech in the book. The omission of the personal name in third-party-voice identification is structurally significant — it marks Ruth's social-cover status in the field-community as 'the foreign young woman from Moab' rather than as a named individual. Recorded as high_risk_register_audit R11 STRUCTURAL_ABSENCE_OF_PERSONAL_NAME_IN_FOREMAN_REPORT."
    },
    {
      "decision_id": "P05-D14",
      "decision": "Boaz's interior at v.5 question not given; encoded as significant absence with do_not_decide: true.",
      "description": "The narrator gives Boaz's question to the foreman ('whose young woman is this?') without any interior-state attribution — no surprise, no recognition, no inclination, no marked emotional weight. The narrator does not say what Boaz notices about Ruth, why he asks, or what he is thinking. The reconstructor must not fill the interior. Recorded as high_risk_register_audit R12 STRUCTURAL_ABSENCE_OF_PROTAGONIST_INTERIOR with do_not_decide: true. Pattern is consistent with the narrator's general restraint on interior states in Ruth (cf. P04 R12 narrator silence on women's recognition-failure cause)."
    },
    {
      "decision_id": "P05-D15",
      "decision": "CB cross-pericope status routed to known_limitations per P04-D14 methodology + _methodology/cross-pericope-pair-verification-figures-only.md.",
      "description": "The Step D prompt correctly instructed CB cross-pericope status into known_limitations rather than into cross_pericope_pair_verification, per the methodology established at P04-D14 (cross_pericope_pair.fig_id is figures-only by schema). CB_0032 Chayil (cross-pericope pair with P09 3:11), CB_0034 Leket-Gleaning (cross-pericope continuation to P06 + P07) recorded in known_limitations. The cross_pericope_pair_verification array contains figures only: FIG_0090 (within-pericope VERIFIED), FIG_0015 (DEFERRED to P11), FIG_0092 (within-pericope VERIFIED), FIG_0093 (within-pericope VERIFIED), FIG_0091 (within-pericope VERIFIED), FIG_0094 (DEFERRED to P06), FIG_0134 (DEFERRED to P09), FIG_0088 (VERIFIED close from P04), FIG_0001 (DEFERRED carry-forward arc), and prior-pericope figures (FIG_0012 from P02 still DEFERRED to P07; FIG_0013 not active — closed at P04)."
    }
  ],
  "vocabulary_additions": {
    "action_values": [
      { "value": "BLESSED", "source": "first introduced in P05 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "GREETED", "source": "first introduced in P05 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "IDENTIFIED", "source": "first introduced in P05 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "INTRODUCED", "source": "first introduced in P05 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "NAMED", "source": "first introduced in P05 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "PLACED", "source": "first introduced in P05 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "POSITIONED", "source": "first introduced in P05 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" },
      { "value": "REPORTED", "source": "first introduced in P05 (SC-0025 action-enforcement seed)", "status": "CONFIRMED" }
    ],
    "proposition_kinds": [
      {
        "value": "GLEANED",
        "source": "P4 2:3a",
        "status": "CONFIRMED"
      },
      {
        "value": "NARRATOR_INTRODUCES",
        "source": "P1 2:1",
        "status": "CONFIRMED"
      }
    ],
    "scene_kinds": [
      {
        "value": "INITIATIVE_SCENE",
        "source": "S2 2:2",
        "status": "CONFIRMED"
      },
      {
        "value": "NARRATOR_INTRODUCTION_SCENE",
        "source": "S1 2:1",
        "status": "CONFIRMED"
      },
      {
        "value": "REPORT_SCENE",
        "source": "S4 2:5-7",
        "status": "CONFIRMED"
      }
    ],
    "presence_values": [
      {
        "value": "PRESENT_COLLECTIVE",
        "source": "B14 Harvesters at S3",
        "status": "CONFIRMED",
        "note": "Already in v0.4 canonical seed; confirmed for collective subjects."
      }
    ],
    "role_in_scene_beings": [
      {
        "value": "ANCESTOR",
        "source": "B2 @S1",
        "status": "CONFIRMED"
      },
      {
        "value": "FIELD_OWNER",
        "source": "B13 @S3",
        "status": "CONFIRMED"
      },
      {
        "value": "FOREMAN",
        "source": "B15 @S4",
        "status": "CONFIRMED"
      },
      {
        "value": "GLEANER",
        "source": "B9 @S3",
        "status": "CONFIRMED"
      },
      {
        "value": "HARVESTERS",
        "source": "B14 @S3",
        "status": "CONFIRMED"
      },
      {
        "value": "KINSMAN",
        "source": "B13 @S1",
        "status": "CONFIRMED"
      },
      {
        "value": "REDEEMER_KIN",
        "source": "B29 @S1",
        "status": "CONFIRMED"
      }
    ],
    "referential_forms": [
      {
        "value": "NAAR_NITSAV_AL_HAQOTSRIM",
        "source": "B15 The-Foreman at S4 (v.5 + v.6)",
        "status": "PROPOSED",
        "note": "Bounded-open; pre-declared in Wave 1 B15 BCD page as the single referential_form for the foreman."
      }
    ],
    "other": [
      {
        "category": "BEING_KIND",
        "value": "GROUP_OF_WORKERS",
        "source": "B14 Harvesters at S3",
        "status": "PROPOSED",
        "note": "Bounded-open; first occurrence."
      },
      {
        "category": "BEING_KIND",
        "value": "NAMED_BY_ROLE_FUNCTIONARY",
        "source": "B15 The-Foreman at S4",
        "status": "PROPOSED",
        "note": "Bounded-open; role-only naming without personal name."
      },
      {
        "category": "BEING_KIND",
        "value": "LEGAL_RELATIONAL_KIN_GROUP",
        "source": "B29 Clan-of-Elimelech at S1 + S3",
        "status": "PROPOSED",
        "note": "Bounded-open; first occurrence of the mishpachah kin-group kind."
      },
      {
        "category": "PLACE_KIND",
        "value": "AGRICULTURAL_FIELD",
        "source": "PL5 Field at S2 + S3",
        "status": "PROPOSED",
        "note": "Bounded-open; first occurrence."
      },
      {
        "category": "PLACE_KIND",
        "value": "AGRICULTURAL_FIELD_OWNED_PORTION",
        "source": "PL5_BOAZ_PORTION at S3 + S4",
        "status": "PROPOSED",
        "note": "Bounded-open; sub-place of agricultural field."
      },
      {
        "category": "PLACE_KIND",
        "value": "FIELD_SHELTER",
        "source": "PL_HA_BAYIT_FIELD_SHELTER at S4",
        "status": "PROPOSED",
        "note": "Bounded-open; precise referent textually disputed at v.7b."
      },
      {
        "category": "PLACE_KIND",
        "value": "PRIVATE_HOUSEHOLD_INTERIOR_IMPLICIT",
        "source": "PL_NAOMIS_DWELLING at S2",
        "status": "PROPOSED",
        "note": "Bounded-open; not lexically named in source text; implicit setting working code."
      },
      {
        "category": "OBJECT_KIND",
        "value": "KINSHIP_ANCHOR_THROUGH_HUSBAND_PHRASE",
        "source": "TH_KINSHIP_ANCHOR_THROUGH_HUSBAND_PHRASE at 2:1",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "ISH_GIBBOR_CHAYIL_INTRODUCTION_FORMULA",
        "source": "TH_ISH_GIBBOR_CHAYIL_INTRODUCTION_FORMULA at 2:1",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "CLAN_OF_ELIMELECH_LOCATOR_PHRASE",
        "source": "TH_CLAN_OF_ELIMELECH_LOCATOR_PHRASE at 2:1",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "NARRATOR_NAMING_AT_END_OF_INTRODUCTION",
        "source": "TH_NARRATOR_NAMING_AT_END_OF_INTRODUCTION at 2:1",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "COHORTATIVE_REQUEST_PERMISSION_FORM",
        "source": "TH_COHORTATIVE_REQUEST_PERMISSION_FORM at 2:2",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "GLEAN_AMONG_EARS_OF_GRAIN_FORMULATION",
        "source": "TH_GLEAN_AMONG_EARS_OF_GRAIN_FORMULATION at 2:2",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "FIND_FAVOR_IN_EYES_QUALIFICATION",
        "source": "TH_FIND_FAVOR_IN_EYES_QUALIFICATION at 2:2",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "GRANT_PERMISSION_WITH_DAUGHTER_FORM",
        "source": "TH_GRANT_PERMISSION_WITH_DAUGHTER_FORM at 2:2",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "THREE_VERB_ARRIVAL_AND_GLEANING_CHAIN",
        "source": "TH_THREE_VERB_ARRIVAL_AND_GLEANING_CHAIN at 2:3",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "GLEANING_POSITION_BEHIND_REAPERS_PHRASE",
        "source": "TH_GLEANING_POSITION_BEHIND_REAPERS_PHRASE at 2:3",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "VAYYIQER_MIQREHA_DOUBLE_COGNATE_CONSTRUCTION",
        "source": "TH_VAYYIQER_MIQREHA_DOUBLE_COGNATE_CONSTRUCTION at 2:3",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "CLAN_FRAME_RESTATED_AT_CHANCE_ARRIVAL",
        "source": "TH_CLAN_FRAME_RESTATED_AT_CHANCE_ARRIVAL at 2:3",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "HINNEH_ATTENTION_MARKER_AT_ARRIVAL",
        "source": "TH_HINNEH_ATTENTION_MARKER_AT_ARRIVAL at 2:4",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "YHWH_BE_WITH_YOU_GREETING_FORM",
        "source": "TH_YHWH_BE_WITH_YOU_GREETING_FORM at 2:4",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "YHWH_BLESS_YOU_RETURN_BLESSING_FORM",
        "source": "TH_YHWH_BLESS_YOU_RETURN_BLESSING_FORM at 2:4",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "WHOSE_YOUNG_WOMAN_KINSHIP_BELONGING_QUESTION",
        "source": "TH_WHOSE_YOUNG_WOMAN_KINSHIP_BELONGING_QUESTION at 2:5",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "FOREMAN_ROLE_PHRASE_NITSAV_AL_HAQOTSRIM",
        "source": "TH_FOREMAN_ROLE_PHRASE_NITSAV_AL_HAQOTSRIM at 2:5 + 2:6",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "THIRD_PARTY_MOABITE_EPITHET_NAARA_MOABIYAH",
        "source": "TH_THIRD_PARTY_MOABITE_EPITHET_NAARA_MOABIYAH at 2:6",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "RETURN_WITH_NAOMI_RELATIONAL_IDENTIFICATION",
        "source": "TH_RETURN_WITH_NAOMI_RELATIONAL_IDENTIFICATION at 2:6",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "QUOTED_PRIOR_GLEANING_REQUEST",
        "source": "TH_QUOTED_PRIOR_GLEANING_REQUEST at 2:7",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "WORK_PATTERN_MORNING_UNTIL_NOW_STATEMENT",
        "source": "TH_WORK_PATTERN_MORNING_UNTIL_NOW_STATEMENT at 2:7",
        "status": "PROPOSED"
      },
      {
        "category": "OBJECT_KIND",
        "value": "WITHIN_DAY_DURATION_FROM_MORNING_UNTIL_NOW",
        "source": "TH_WITHIN_DAY_DURATION_FROM_MORNING_UNTIL_NOW at 2:7",
        "status": "PROPOSED",
        "note": "Within-day duration encoded as content-object per P01 TM_TEN_YEARS approximate-duration precedent."
      },
      {
        "category": "OBJECT_KIND",
        "value": "DISPUTED_SHELTER_REST_CLAUSE",
        "source": "TH_DISPUTED_SHELTER_REST_CLAUSE at 2:7b",
        "status": "PROPOSED",
        "note": "Hebrew at v.7b textually disputed across major commentaries; held open with textual_clarity_flag."
      }
    ],
    "arc_elements": [
      {
        "value": "CHANCE_PROVIDENCE_ARRIVAL",
        "source": "P05 level_1.arc_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      },
      {
        "value": "FIELD_COMMUNITY_GREETING",
        "source": "P05 level_1.arc_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      },
      {
        "value": "INITIATIVE_OF_OUTSIDER_DAUGHTER_IN_LAW",
        "source": "P05 level_1.arc_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      },
      {
        "value": "NARRATOR_PARENTHETICAL_INTRODUCTION",
        "source": "P05 level_1.arc_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      },
      {
        "value": "PUBLIC_IDENTIFICATION_OF_OUTSIDER",
        "source": "P05 level_1.arc_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      }
    ],
    "context_elements": [
      {
        "value": "DIVINE_CONTEXT",
        "source": "P05 level_1.context_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      },
      {
        "value": "PRIOR_ACTION_CONTEXT",
        "source": "P05 level_1.context_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      }
    ],
    "tone_elements": [
      {
        "value": "ANTICIPATORY",
        "source": "P05 level_1.tone_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      },
      {
        "value": "ECONOMICAL",
        "source": "P05 level_1.tone_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      },
      {
        "value": "QUIET",
        "source": "P05 level_1.tone_elements — convergent value (Gate-F CONFIRMED 2026-05-30)",
        "status": "CONFIRMED"
      }
    ],
    "pace_elements": [
      { "value": "HOLDS", "source": "P05 level_1.pace_elements - SC-0021 locus-strip from HOLDS_AT_INTERIOR_DIALOGUE", "status": "CONFIRMED" },
      { "value": "WIDENS", "source": "P05 level_1.pace_elements - SC-0021 locus-strip from WIDENS_AT_CHANCE_PROVIDENCE_FRAMING", "status": "CONFIRMED" }
    ],
    "communicative_function_elements": []
  },
  "proposition_kind_slot_sets": [
    {
      "proposition_kind": "NARRATOR_INTRODUCES_KINSMAN_BEFORE_ACTION",
      "slot_set": [
        "introduction_components"
      ],
      "component_record_shape": {
        "action": "required - POSITIONED_THROUGH_KINSHIP_ANCHOR | INTRODUCED_AS_PERSON_OF_STANDING | PLACED_IN_LEGAL_RELATIONAL_KIN_GROUP | NAMED_AT_END_OF_INTRODUCTION",
        "list_position": "required - FIRST | SECOND | THIRD | FOURTH",
        "speech_act": "required - STATES_AS_TRUE"
      },
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P1"
      ],
      "note": "Four-component narrator-economical introduction in chronicle pattern (relation, attribute, clan, name)."
    },
    {
      "proposition_kind": "REQUESTED_PERMISSION_TO_GLEAN",
      "slot_set": [
        "requester",
        "addressee",
        "requested_action",
        "destination",
        "qualification",
        "request_form",
        "gleaning_action_form",
        "favor_qualification_form",
        "speech_act"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P2"
      ]
    },
    {
      "proposition_kind": "GRANTED_PERMISSION_TO_GLEAN",
      "slot_set": [
        "permission_granter",
        "permission_recipient",
        "addressed_form",
        "granted_action",
        "release_form",
        "speech_act"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P3"
      ]
    },
    {
      "proposition_kind": "WENT_AND_GLEANED_BEHIND_HARVESTERS",
      "slot_set": [
        "gleaner",
        "destination",
        "gleaning_position_relation",
        "harvesters_referent",
        "three_verb_chain_form",
        "gleaning_position_form",
        "speech_act"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P4"
      ]
    },
    {
      "proposition_kind": "CHANCE_ARRIVED_AT_KINSMAN_PORTION_WITH_CLAN_FRAME_RESTATED",
      "slot_set": [
        "gleaner",
        "arrived_at_portion",
        "portion_owner",
        "clan_referent_restated",
        "clan_eponym",
        "agent_named",
        "chance_construction_form",
        "clan_frame_restatement_form",
        "speech_act"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P5"
      ],
      "note": "agent_named slot set to NONE per source-text discipline; do not attribute the chance-arrival to YHWH."
    },
    {
      "proposition_kind": "ARRIVED_AT_FIELD_FROM_HOMETOWN",
      "slot_set": [
        "arriver",
        "origin",
        "destination",
        "attention_marker_form",
        "speech_act"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P6"
      ]
    },
    {
      "proposition_kind": "EXCHANGED_GREETING_AND_RETURN_BLESSING",
      "slot_set": [
        "greeting_components"
      ],
      "component_record_shape": {
        "action": "required - GREETED_WITH_DIVINE_INVOCATION | RETURNED_BLESSING_WITH_DIVINE_INVOCATION",
        "list_position": "required - FIRST | SECOND",
        "speech_act": "required - WISHES_FOR_HEARER"
      },
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P7"
      ]
    },
    {
      "proposition_kind": "ASKED_KINSHIP_AND_SOCIAL_COVER_QUESTION",
      "slot_set": [
        "question_asker",
        "question_addressee",
        "question_target_referent",
        "question_form",
        "foreman_role_phrase_form",
        "speech_act"
      ],
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P8"
      ]
    },
    {
      "proposition_kind": "FOREMAN_REPORTED_IDENTITY_AND_WORK_PATTERN",
      "slot_set": [
        "reporter",
        "report_addressee",
        "report_subject_referent",
        "foreman_role_phrase_form",
        "report_components"
      ],
      "component_record_shape": {
        "action": "required - IDENTIFIED_BY_ETHNIC_EPITHET | IDENTIFIED_BY_RETURN_WITH_KINSHIP_ANCHOR | REPORTED_PRIOR_REQUEST_QUOTED_SPEECH | REPORTED_WORK_PATTERN_PERSISTENCE | REPORTED_DISPUTED_SHELTER_REST_CLAUSE",
        "list_position": "required - FIRST through FIFTH",
        "speech_act": "required - STATES_AS_TRUE | REPORTS_PRIOR_SPEECH_REQUEST",
        "quoted_prior_speech_act": "conditional - REQUESTS_PERMISSION_TO_DO when REPORTED_PRIOR_REQUEST_QUOTED_SPEECH",
        "textual_clarity_flag": "conditional - true when REPORTED_DISPUTED_SHELTER_REST_CLAUSE"
      },
      "status": "PROPOSED",
      "occurrences_in_pericope": [
        "P9"
      ],
      "note": "Five-component compound foreman report; the third component carries REPORTS_PRIOR_SPEECH_REQUEST with nested quoted_prior_speech_act REQUESTS_PERMISSION_TO_DO matching Ruth's v.2 cohortative-na request form."
    }
  ],
  "high_risk_register_audit": [
    {
      "id": "R1",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "B13 Boaz introduced at v.1 (P1) with ish-gibbor-chayil attribute (FIG_0090 + CB_0032 + FIG_0134)",
      "note": "PREFERRED keep-image on FIG_0090 (introduction-formula). B13 is the second male protagonist in the book; introduction-before-action narrator-parenthetical names him through Naomi's kinship-anchor and the clan-frame before he enters the storyline. The chayil attribute opens a cross-pericope pair that closes at P09 3:11 (Ruth as eshet chayil). Reconstructor must preserve the introduction-before-action sequence (relation, attribute, clan, name) and the chayil lexeme so the cross-pericope pair lands.",
      "required_in_audit": true,
      "carries_forward_to": "P09_compilation_log",
      "source_in_meaning_map": "Section 5B Figure Flags (FIG_0090); Section 3A Scene 1 (B13 REFERENCED); Section 3C Scene 1 (TH_ISH_GIBBOR_CHAYIL_INTRODUCTION_FORMULA + TH_CLAN_OF_ELIMELECH_LOCATOR_PHRASE)"
    },
    {
      "id": "R2",
      "kind": "STRUCTURAL_BRACKETING_CLAN_FRAME",
      "applies_to": "B29 Clan-of-Elimelech twice-named at S1 v.1 + S3 v.3",
      "note": "The narrator names the clan of Elimelech at v.1 (Boaz's introduction-frame) and again at v.3 (restated immediately after vayyiqer-miqreha). The twice-naming brackets Ruth's chance-arrival with the same kin-frame at both ends; the audience sees the kin-link the characters do not yet see. Reconstructor must preserve both occurrences of the clan-frame; do not collapse to one occurrence.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3A Scene 1 + Scene 3 (B29 REFERENCED at both); Section 3C Scene 1 (TH_CLAN_OF_ELIMELECH_LOCATOR_PHRASE) + Scene 3 (TH_CLAN_FRAME_RESTATED_AT_CHANCE_ARRIVAL); Section 4 Propositions P1 and P5"
    },
    {
      "id": "R3",
      "kind": "STRUCTURAL_AUDIENCE_LEVEL_GAP_AT_S2_DIALOGUE",
      "applies_to": "Narrator names Boaz to audience at v.1; Naomi does not name Boaz to Ruth at v.2",
      "note": "The narrator introduces Boaz to the audience at v.1 in the parenthetical, then immediately moves to Ruth-Naomi interior dialogue at v.2 where Naomi does not name Boaz, does not suggest a kinsman, does not warn or bless. The audience-knows-character-doesn't gap is structurally meaningful — it is the narrator's deliberate setup for the audience to hold the kinship knowledge across the chance-arrival. Reconstructor must not insert Naomi naming or alluding to Boaz at v.2.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3 Scene 2 significant_absence; Section 3 Scene 1 + Scene 2 contrast"
    },
    {
      "id": "R4",
      "kind": "STRUCTURAL_PROVIDENCE_WITHOUT_NAMING_AGENT_WITHHELD",
      "applies_to": "FIG_0015 VAYYIQER_MIQREHA at v.3 (P5) — double-cognate chance-providence construction",
      "note": "REQUIRED keep-image on FIG_0015. The narrator's signature providence-without-naming move: the construction holds ambiguity between coincidence and providence; YHWH is not named as agent. Flattening to plain 'she happened to come' or to plain 'YHWH led her' loses the irony in either direction. Reconstructor must preserve the ambiguity. agent_named: NONE in MEANING_COORDINATES P5; do not infer divine agency.",
      "required_in_audit": true,
      "do_not_decide": true,
      "carries_forward_to": "P11_compilation_log",
      "source_in_meaning_map": "Section 5B Figure Flags (FIG_0015); Section 3C Scene 3 (TH_VAYYIQER_MIQREHA_DOUBLE_COGNATE_CONSTRUCTION); Section 4 Proposition P5"
    },
    {
      "id": "R5",
      "kind": "CROSS_PERICOPE_PAIRING_FIRST_OCCURRENCE",
      "applies_to": "FIG_0015 Vayyiqer-Miqreha opens at P05 v.3; cross-pericope close at P11 4:1 (parallel chance-providence construction at the gate scene)",
      "note": "REQUIRED keep-image. The vayyiqer-miqreha construction recurs at P11 4:1 in a parallel structural moment (Boaz arrives at the gate and 'behold' the nearer redeemer is passing by — chance-providence framing at the gate parallels the chance-providence framing at the field). Reconstructor must preserve the construction at both occurrences so the cross-pericope echo lands.",
      "required_in_audit": true,
      "carries_forward_to": "P11_compilation_log",
      "source_in_meaning_map": "Section 5B Figure Flags (FIG_0015 cross-pericope pair)"
    },
    {
      "id": "R6",
      "kind": "CROSS_PERICOPE_PAIRING_CLOSED_HERE",
      "applies_to": "FIG_0088 Empty-Lament-at-Harvest-Arrival closes at P05 v.3 (P5)",
      "note": "PREFERRED keep-image. Opened P04 v.21-22 (Naomi's empty-lament next to the harvest-frame opening). Closes here when Ruth's chance-arrival lands in the kinsman's portion — the harvest's actual provision begins to land structurally even before Naomi can see the answer. Reconstructor must allow the structural irony to remain visible across P04-P05: keep Naomi's empty-lament intact at P04; let the harvest's provision begin to land at P05 v.3 without flagging or commentary in the meaning-map prose.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 5B Figure Flags (FIG_0088 cross-pericope close); Section 4 Proposition P5"
    },
    {
      "id": "R7",
      "kind": "CROSS_PERICOPE_PAIRING_FIRST_OCCURRENCE",
      "applies_to": "FIG_0134 Chayil-Pair-Completed opens at P05 v.1 (P1) as first half (Boaz ish-gibbor-chayil); cross-pericope close at P09 3:11 (Ruth eshet-chayil)",
      "note": "First half of the chayil cross-pair. The chayil lexeme applied to Boaz at v.1 will pair with the same lexeme applied to Ruth at 3:11 (P09). The pair brackets the field-and-threshing-floor pairing structurally. Reconstructor must preserve the chayil lexeme at both occurrences so the structural echo lands. CB_0032 carries the lexeme-rendering-consistency concern.",
      "required_in_audit": true,
      "carries_forward_to": "P09_compilation_log",
      "source_in_meaning_map": "Section 5B Figure Flags (FIG_0134 cross-pericope pair opens here)"
    },
    {
      "id": "R8",
      "kind": "DISCOURSE_THREAD_ADVANCED_FIRST_MAJOR",
      "applies_to": "T2 Line-and-Inheritance-of-Elimelech major-advanced at audience-level via Boaz-as-kinsman introduction at v.1 (P1) + clan-frame restatement at v.3 (P5)",
      "note": "T2 was opened at P01 1:5 (deaths of both sons) and threatened across P02-P04. The Boaz-as-kinsman introduction at v.1 is the first major-advance toward redemption at the audience level — the kinsman who could redeem the line has been named before the characters meet face-to-face. The twice-naming of the clan-frame at v.1 + v.3 brackets Ruth's chance-arrival inside the redemption-frame the line-of-Elimelech question is asking about.",
      "required_in_audit": true,
      "carries_forward_to": "P09_through_P11_compilation_logs",
      "source_in_meaning_map": "Section 5B Figure Flags + cross-pericope context; Section 4 Propositions P1 and P5; tracked in BCD-DELTA discourse_thread_events"
    },
    {
      "id": "R9",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "FIG_0091 Foreman-Role + FIG_0092 YHWH-Be-with-You-Greeting + FIG_0093 YHWH-Bless-You-Return-Greeting + FIG_0094 Whose-Young-Woman-Belonging-Question",
      "note": "Four field-community first-occurrence figures: FIG_0091 (foreman role-phrase; within-pericope pair at v.5+v.6); FIG_0092 (Boaz's greeting-blessing form at v.4); FIG_0093 (harvesters' return-blessing form at v.4); FIG_0094 (Boaz's kinship-and-social-cover question at v.5; cross-pericope pair forward to P06). All four are field-community figures establishing the covenant-blessing register and the kinship-belonging frame the rest of the field-encounter will work out.",
      "required_in_audit": true,
      "carries_forward_to": "P06_compilation_log",
      "source_in_meaning_map": "Section 5B Figure Flags (FIG_0091, FIG_0092, FIG_0093, FIG_0094); Section 3C Scenes 3 and 4"
    },
    {
      "id": "R10",
      "kind": "REFERENTIAL_FORM_REACTIVATION_IN_THIRD_PARTY_VOICE",
      "applies_to": "FIG_0001 Ruth-the-Moabitess third-party-voice occurrence at v.6 (P9) — first time anyone in Bethlehem speaks the Moabite epithet aloud",
      "note": "The carry-forward arc continues: opened P01 v.4 (narrator) → withheld P02-P03 → narrator-voice reactivation P04 v.22 → narrator-epithet at speech-event head P05 v.2 → third-party-voice at P05 v.6 (foreman's 'a Moabite young woman'). The third-party-voice occurrence is structurally significant — the field-community now identifies Ruth by the ethnic epithet, not by name. Reconstructor must preserve the Moabite epithet on the foreman's lips at v.6; the personal name 'Ruth' must not appear in the foreman's voice.",
      "required_in_audit": true,
      "do_not_decide": true,
      "carries_forward_to": "P06_compilation_log",
      "source_in_meaning_map": "Section 3A Scene 4 (B9 REFERENCED with ethnic-epithet identification); Section 3C Scene 4 (TH_THIRD_PARTY_MOABITE_EPITHET_NAARA_MOABIYAH); Section 5B Figure Flags (FIG_0001 active at P9)"
    },
    {
      "id": "R11",
      "kind": "STRUCTURAL_ABSENCE_OF_PERSONAL_NAME_IN_FOREMAN_REPORT",
      "applies_to": "Foreman omits Ruth's personal name at v.6-7; identification by ethnic-epithet + kin-relation + work-pattern only",
      "note": "The foreman identifies Ruth by ethnic-epithet ('Moabite young woman'), by kin-relation ('the one who returned with Naomi'), by quoted-prior-request, and by work-pattern. The name 'Ruth' does not appear in the foreman's voice. The omission marks Ruth's social-cover status in the field-community as 'the foreign young woman from Moab' rather than as a named individual. Reconstructor must not insert Ruth's name into the foreman's report.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3 Scene 4 significant_absence; Section 4 Proposition P9"
    },
    {
      "id": "R12",
      "kind": "STRUCTURAL_ABSENCE_OF_PROTAGONIST_INTERIOR",
      "applies_to": "Boaz's interior at v.5 question not given",
      "note": "The narrator gives Boaz's question to the foreman without any interior-state attribution — no surprise, no recognition, no inclination, no marked emotional weight. The narrator does not say what Boaz notices about Ruth, why he asks, or what he is thinking. Reconstructor must not fill the interior; the question must stand without surrounding interior commentary.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3 Scene 4 significant_absence; Section 4 Proposition P8"
    },
    {
      "id": "R13",
      "kind": "TEXTUAL_CLARITY_FLAG",
      "applies_to": "PL_HA_BAYIT_FIELD_SHELTER shelter-rest clause at v.7b — Hebrew syntax and precise referent textually disputed across major commentaries",
      "note": "The Hebrew 'זֶה שִׁבְתָּהּ הַבַּיִת מְעָט' is textually disputed; readings range from 'she has rested only a little in the shelter' to 'she has not rested even for a moment.' Encoded in MEANING_COORDINATES P9 fifth component with textual_clarity_flag: true. Reconstructor must hold the ambiguity open; do not resolve. The PL_HA_BAYIT_FIELD_SHELTER place-code is registered in BCD-DELTA with notes on the textual uncertainty; the syntactic uncertainty is at the proposition-level only.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3B Scene 4 (PL_HA_BAYIT_FIELD_SHELTER); Section 3C Scene 4 (TH_DISPUTED_SHELTER_REST_CLAUSE); Section 4 Proposition P9 fifth Q&A"
    },
    {
      "id": "R14",
      "kind": "NAMED_BY_ROLE_ONLY_NO_PERSONAL_NAME",
      "applies_to": "B15 The-Foreman named only by role ('the young man standing over the harvesters') at v.5 + v.6",
      "note": "B15 is identified only by function in the field-organization (nitsav-al-haqotsrim); no personal name is given anywhere in P05. The role-only naming distinguishes the foreman from named protagonists. Reconstructor must use a role-designation form in the target language, not coin a personal name for the foreman.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3A Scene 4 (B15 referential_form NAAR_NITSAV_AL_HAQOTSRIM); Section 3C Scene 4 (TH_FOREMAN_ROLE_PHRASE_NITSAV_AL_HAQOTSRIM)"
    },
    {
      "id": "R15",
      "kind": "RUTH_INITIATIVE_NOT_NAOMI",
      "applies_to": "Ruth proposes the gleaning at v.2; Naomi grants permission — source-text discipline",
      "note": "The verb at v.2 has Ruth as subject; the cohortative-na request form ('let me go, please') is Ruth's; Naomi's response is the release ('go, my daughter'). Speech_act REQUESTS_PERMISSION_TO_DO (Ruth) + GRANTS_PERMISSION_TO_DO (Naomi). Reconstructor must preserve the initiative-by-Ruth direction; Naomi must not appear as the proposer.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3 Scene 2 (Ruth as speaking subject); Section 3C Scene 2 (TH_COHORTATIVE_REQUEST_PERMISSION_FORM + TH_GRANT_PERMISSION_WITH_DAUGHTER_FORM); Section 4 Propositions P2 and P3"
    }
  ],
  "cross_pericope_pair_verification": {
    "pairs": [
      {
        "fig_id": "FIG_0015",
        "opens_at": "P05 P5 (2:3)",
        "closes_at": "P11 (4:1) — parallel vayyiqer construction at the gate scene",
        "verification_status": "DEFERRED",
        "note": "REQUIRED keep-image. The vayyiqer-miqreha construction recurs at P11 4:1 in a parallel structural moment. Cross-pericope pair verification deferred until P11 compilation."
      },
      {
        "fig_id": "FIG_0088",
        "opens_at": "P04 P5-P6 (1:21-22)",
        "closes_at": "P05 P5 (2:3) — chance-arrival in kinsman's portion lands the harvest's actual provision against the empty-lament structurally",
        "verification_status": "VERIFIED",
        "note": "PREFERRED keep-image. Close-trigger at P5 v.3 (chance-arrival in kinsman's portion) rather than at P9 v.7 (foreman's first-recognition of work-pattern); rationale documented in P05-D11. Cross-pericope pair verification COMPLETE."
      },
      {
        "fig_id": "FIG_0134",
        "opens_at": "P05 P1 (2:1) — first half (Boaz ish-gibbor-chayil)",
        "closes_at": "P09 (3:11) — second half (Ruth eshet-chayil)",
        "verification_status": "DEFERRED",
        "note": "Chayil cross-pericope pair tracker. The CB_0032 chayil lexeme must survive rendering at both occurrences so the structural echo lands. Cross-pericope pair verification deferred until P09 compilation."
      },
      {
        "fig_id": "FIG_0001",
        "opens_at": "P01 P10 (1:4)",
        "closes_at": "Carry-forward arc continues: withheld P02-P03; narrator-voice P04 v.22; narrator-epithet P05 v.2; third-party-voice P05 v.6; continues to P06, P07, P11, P12",
        "verification_status": "DEFERRED",
        "note": "REQUIRED keep-image. Book-wide recurrence pattern; cross-pericope pair verification continues to be deferred. Third-party-voice reactivation at P05 v.6 (foreman) recorded in high_risk R10."
      },
      {
        "fig_id": "FIG_0090",
        "opens_at": "P05 P1 (2:1)",
        "closes_at": "P05 P1 (2:1) — within-pericope single-occurrence",
        "verification_status": "VERIFIED",
        "note": "PREFERRED keep-image. Introduction-formula for Boaz; chayil-attribute weight carried by FIG_0090 + CB_0032 + FIG_0134."
      },
      {
        "fig_id": "FIG_0091",
        "opens_at": "P05 P8 (2:5)",
        "closes_at": "P05 P9 (2:6) — within-pericope pair",
        "verification_status": "VERIFIED",
        "note": "PREFERRED keep-image. Foreman role-phrase named at both v.5 (Boaz's address) and v.6 (narrator's identifying-clause)."
      },
      {
        "fig_id": "FIG_0092",
        "opens_at": "P05 P7 (2:4)",
        "closes_at": "P05 P7 (2:4) — within-pericope single-occurrence",
        "verification_status": "VERIFIED",
        "note": "PREFERRED keep-image. Boaz's YHWH-greeting to harvesters."
      },
      {
        "fig_id": "FIG_0093",
        "opens_at": "P05 P7 (2:4)",
        "closes_at": "P05 P7 (2:4) — within-pericope single-occurrence",
        "verification_status": "VERIFIED",
        "note": "PREFERRED keep-image. Harvesters' return-blessing pairs structurally with FIG_0092 across v.4."
      },
      {
        "fig_id": "FIG_0094",
        "opens_at": "P05 P8 (2:5)",
        "closes_at": "P06 (cross-pericope close pending; figure-page appears-in indicates P05 + P06)",
        "verification_status": "DEFERRED",
        "note": "OPTIONAL keep-image. Kinship-and-social-cover question; potential cross-pericope pair with P06 deferred."
      },
      {
        "fig_id": "FIG_0012",
        "opens_at": "P02 P15 (1:14)",
        "closes_at": "P07 (2:23) — pending",
        "verification_status": "DEFERRED",
        "note": "Carry-forward from P02. Not lexically active at P05 (no dabaq lexeme). Cross-pericope close still deferred to P07."
      },
      {
        "fig_id": "FIG_0072",
        "opens_at": "P03 P3 (1:16b-c)",
        "closes_at": "P03 P3 — within-pericope pair completed at P03",
        "verification_status": "VERIFIED",
        "note": "P03 within-pericope pair; no P05 activity. Recorded for completeness of cross-pericope figure status across the first five pericopes."
      },
      {
        "fig_id": "FIG_0074",
        "opens_at": "P03 P3 (1:17a)",
        "closes_at": "P03 P3 — within-pericope pair completed at P03",
        "verification_status": "VERIFIED",
        "note": "P03 within-pericope pair; no P05 activity."
      },
      {
        "fig_id": "FIG_0075",
        "opens_at": "P03 P4 (1:17b)",
        "closes_at": "P03 P4 — single-occurrence at P03; cross-canonical recurrences outside Ruth",
        "verification_status": "VERIFIED",
        "note": "P03 self-curse oath formula; cross-pericope pair with 3:13 (Boaz's oath) DEFERRED. No P05 activity."
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
      "REQUESTS_PERMISSION_TO_DO",
      "GRANTS_PERMISSION_TO_DO",
      "WISHES_FOR_HEARER",
      "ASKS_KINSHIP_BELONGING_QUESTION",
      "REPORTS_PRIOR_SPEECH_REQUEST"
    ],
    "negation_not_double_encoded": "N/A — no DIRECTS_HEARER_NOT_TO_DO at P05; no negative-directive speech_acts used",
    "cross_pericope_cross_refs_present_on_correct_propositions": true,
    "empty_slot_rule_applied_to_times_in_scene": true,
    "discourse_threads_tracked_in_audit_only": true,
    "known_limitations_tracked_in_audit_only": true,
    "high_risk_register_complete": true,
    "every_high_risk_entry_traces_to_meaning_map": true,
    "significant_absences_traced_to_meaning_map": true,
    "no_content_added_beyond_meaning_map": true,
    "wife_pairing_withholding_enforced": true,
    "b_codes_match_bcd_version": "All B-codes verified against ruth_pilot_BCD_v0_3 plus carry-forwards (B2, B3, B9, B10 stable from P01-P04) plus four new at P05 (B13 Boaz PERSON, B14 Harvesters GROUP_OF_WORKERS, B15 The-Foreman NAMED_BY_ROLE_FUNCTIONARY, B29 Clan-of-Elimelech LEGAL_RELATIONAL_KIN_GROUP).",
    "registry_additions_extracted_to_bcd_delta": true,
    "no_reviewer_facing_prompts_in_compilation_log": true
  },
  "known_limitations": [
    "PL5 Field is a working PL-code pending formal PL-code assignment in BCD v0.4. Parallels P01's PL_HA_ARETZ, P02's PL_LAND_OF_JUDAH, P04's TM_BARLEY_HARVEST_BEGINNING working-code patterns.",
    "PL5_BOAZ_PORTION is a working PL-code pending formal PL-code assignment in BCD v0.4. Sub-place of PL5 Field; the specific portion Ruth chances upon.",
    "PL_HA_BAYIT_FIELD_SHELTER is a working PL-code pending formal PL-code assignment in BCD v0.4. The Hebrew at v.7b ('זֶה שִׁבְתָּהּ הַבַּיִת מְעָט') is textually disputed across major commentaries; readings range from 'she has rested only a little in the shelter' to 'she has not rested even for a moment'; the BCD-DELTA entry notes the textual uncertainty without resolving it.",
    "PL_NAOMIS_DWELLING is a working PL-code pending formal PL-code assignment in BCD v0.4. Not lexically named in the source text; PRESENT_IMPLIED at S2 v.2 as the interior dialogue setting. Carry-forward to multiple chapter-2/3/4 interior scenes (P07, P08, P10, P13).",
    "CB_0032 Chayil cross-pericope pair verification DEFERRED to P09 (3:11, Ruth eshet-chayil). Per _methodology/cross-pericope-pair-verification-figures-only.md, CB cross-pericope status lives in known_limitations rather than in cross_pericope_pair_verification; the figure-level pair tracker is FIG_0134.",
    "CB_0034 Leket-Gleaning cross-pericope continuation DEFERRED to P06 + P07. The gleaning institution is the legal-customary frame the whole chapter 2 assumes; lexical recurrence continues at P06 (2:8-23) and P07 (2:18-23).",
    "Nine new proposition_kinds at P05 (NARRATOR_INTRODUCES_KINSMAN_BEFORE_ACTION, REQUESTED_PERMISSION_TO_GLEAN, GRANTED_PERMISSION_TO_GLEAN, WENT_AND_GLEANED_BEHIND_HARVESTERS, CHANCE_ARRIVED_AT_KINSMAN_PORTION_WITH_CLAN_FRAME_RESTATED, ARRIVED_AT_FIELD_FROM_HOMETOWN, EXCHANGED_GREETING_AND_RETURN_BLESSING, ASKED_KINSHIP_AND_SOCIAL_COVER_QUESTION, FOREMAN_REPORTED_IDENTITY_AND_WORK_PATTERN) are bounded-open. Four new scene_kinds are bounded-open. Multiple new object_kinds, referential_forms, being_kinds, and place_kinds drift-warn against the canonical P01 seed; all expected to be accepted at Gate F.",
    "community_verified and translation_team_verified remain false; this is a pilot compilation."
  ]
}
```

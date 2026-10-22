---
type: "sta-compilation-log"
pericope: "P11"
status: "valid"
pilot: "pilot-2"
---

# P11 — Ruth 4:1-8 — COMPILATION-LOG

```json
{
  "sta_id": "ruth_pericope_11_v2_0",
  "tagset_version": "TRIPOD_STA_v2_0",
  "bcv": "Ruth 4:1-8",
  "pericope_id": "P11",
  "pericope_title": "The gate: the non-name, the field before Ruth, and the sandal",
  "compiled_at": "2026-05-29",
  "review_status": {
    "meaning_map_status": "PARSED_BY_COMPILER",
    "sta_compilation_status": "MODEL_DRAFTED_REVIEWER_RULED",
    "community_verified": false,
    "translation_team_verified": false,
    "consultant_review_required": true,
    "production_use": false
  },
  "confidence_overall": "MEDIUM",
  "confidence_overall_note": "Judgment half machine-drafted (SC-0063, patch-only contract) and ruled by Marcia axis-by-axis under SC-0064 (§A–§E + arc_element). The graduated MEANING_COORDINATES validates block-clean with 0 convergent drift and is lint-clean. Mechanized log: vocabulary_additions are this pericope's ruled mints; the high-risk register audit was hand-authored from the corrected P11 map and ruled by Marcia 2026-09-27 under SC-0087 (see P11-D4, P11-D5); point A of 2026-09-28 in P11-D6; the never-rules made do_not_decide after the session in P11-D7.",
  "compilation_decisions": [
    {
      "decision_id": "P11-D1",
      "decision": "Deterministically compiled a MEANING_COORDINATES skeleton from the approved Meaning Map.",
      "description": "Extracted header/classification, scene + entity IDs + presence, verse-ranges, significant_absence, communicative purpose, proposition anchors/scene-links/cross-refs, and Section-5 concept/figure flags. 89 judgment fields left as typed placeholders for Agent 3. No values invented (extract-only)."
    },
    {
      "decision_id": "P11-D2",
      "decision": "Judgment gaps filled by the SC-0063 drafter (Slice 4).",
      "description": "claude-opus-4-8 under the pinned fm-drafter prompt; structured-output fills merged by the patch-only layer. Provenance: _working/P11/drafts/run-2026-06-12T15-18-11-527Z/."
    },
    {
      "decision_id": "P11-D3",
      "decision": "Ruled by Marcia under SC-0064 (the batch ruling), axis by axis.",
      "description": "§A–§E + the five §B axes (action+tone, proposition_kind, role_in_scene_being, scene_kind, arc_element) ruled across 2026-06-12→19; 17 vocabulary addition(s) CONFIRMED for promotion for this pericope (per-axis ruling-logs in _working/P11/P11-SC-0064-*-RULING-LOG.md). Renames/collapses applied to the MEANING_COORDINATES as recorded amendments where ruled."
    },
    {
      "decision_id": "P11-D4",
      "decision": "High-risk register ruled by Marcia under SC-0087 (the P07–P14 register-completion program opened by SC-0085).",
      "description": "Drafted from the corrected P11 map and ruled by Marcia 2026-09-27: nine rulings, her word on each «(a), sim, pode seguir com as recomendações» (the English wording of the entries is the builder's rendering of her Portuguese). 14 entries replace the R1 skeleton, 8 do_not_decide (R1 the order of the telling, R2 the man without a name, R3 the refusal, R4 the redeemer passing at 4:1, R5 the sandal, R6 the gate silences, R7 the wife of the dead, R10 Boaz's conditional promise resolved as told). Kinds: STRUCTURAL_FRAMING_DEVICE, NAMING_SHIFT, WITHHELD_PAIRING_PER_SOURCE_DISCIPLINE, CROSS_PERICOPE_PAIRING_CLOSED_HERE and FIGURE_FIRST_OCCURRENCE from the approved high_risk_register_kind list; SIGNIFICANT_ABSENCE (R4, R6), TEXTUAL_CLARITY_FLAG (R13) and DISCOURSE_THREAD_ADVANCED (R14) as the SC-0087 build spec names them (not on the approved list); R8 NAMING_SHIFT, the kind P07 R7 uses for the same figure. Carried-forward items land: P09 R7 and R15 (carries_forward_to P11_audit), P09 R14, P07 R4/R5/R7/R12, P05 R4/R5/R8, P01 R10, P02 R5, P06 R4. Pair table: FIG_0156, FIG_0112 and FIG_0015 (canon-record link only) VERIFIED here; FIG_0001 DEFERRED to P12; FIG_0110, FIG_0002, FIG_0005, FIG_0003, FIG_0016 and FIG_0014 PENDING. Forward links to P12 and P13 live only in this register (R14) and the pair table, never in the map. The three gate signals (the real audit, high_risk_register_complete, and the map's sta-status) flip together in this change."
    },
    {
      "decision_id": "P11-D5",
      "decision": "Meaning Map + MEANING_COORDINATES corrected under the SC-0087 rulings (2026-09-27); FIG_0015 unflagged at 4:1; B2 removed from S1.",
      "description": "Rulings applied to the map and the MEANING_COORDINATES together: the order of the telling kept as a fact, with no strategy words (ruling 1); Boaz's word 'So-and-so' without 'friend', and no reason given for the non-name (2); the refusal kept as 'I cannot', said twice and not explained (3); 4:1 told only with 'and behold' — FIG_0015 removed from the map's active-figures and Section 5B and from the MC P2 figure_flags, the 2:3 pair kept in the canon record only (R4 and the pair table) (4); the sandal told as the text tells it, O26 'the sign that confirmed the matter (4:7)', CB_0002's slug renamed Widow-Acquired-to-Raise-Up-the-Name-of-the-Dead (5); the gate silences as facts, with the new one on the night at the threshing floor (6); the P09 rulings applied — the gate as the place where the matter is done before everyone, no 'queue', CB_0006 without the 3:11 pointer, forward pointers out, the Jonah aside out (7); minor text points (8). B2 Elimelech removed from the MC S1 beings (he is not in 4:1–2; the map's Scene 1 has no B2 entry). The MC's four scene purposes and significant absences equal the map's 3F and Significant Absence texts word for word. Map frontmatter sta-status set to complete. Register overrides and the arc_element CHANCE_PROVIDENCE_ARRIVAL unchanged (shared with P05; not voiced). Four builder extensions beyond the listed texts, each aligned to a ruled text and named for Marcia's yes/no: Scene 4 O26 'What it is' 'the sandal drawn off' (was 'the sandal drawn off and handed over'; ruling 5, the voice does not add the handing); Scene 4 PL_ISRAEL 'a remembered, shared custom' (was 'law'; ruling 5, no law the story does not cite); Section 5A CB_0002 '(the widow acquired with the field, so that the name of the dead is raised up upon his inheritance)' (was 'so the dead line continues'; the ruled Section 3C text) and CB_0003 'the living man's own inheritance set beside it' (was 'pleaded against it'; ruling 3, the story only sets the two side by side). One wording in the register differs from the build spec's text, also named for Marcia's yes/no: the R1 note gives 4:5 in Boaz's own words to the man, as Section 2.1 does — 'then Boaz adds: on the day you buy the field from Naomi's hand, you also acquire Ruth the Moabite, the wife of the dead, …' (the spec's 'on the day he buys the field … he also acquires Ruth', with Boaz as the subject, reads as if Boaz acquires Ruth at 4:5, which ruling 8 and R10 rule out; the Hebrew is second person, 'your buying' and the qere 'you acquire')."
    },
    {
      "decision_id": "P11-D6",
      "decision": "Point A ruled by Marcia 2026-09-28 under SC-0087: the Scene 4 silence without the handing, R2 and R5 accept without remark, B19 'the nearer redeemer'.",
      "description": "Her word: «(a), sim, pode seguir com o ponto A». Three changes, as in the tested prototype: (1) the handing of the sandal is not a silence — the custom the narrator tells at 4:7 says a man gave his sandal to the other — so the Scene 4 Significant Absence (map and MEANING_COORDINATES S4, word for word) drops 'The narrator tells only that he drew off his sandal; the custom he has just explained says the sandal was given to the other.' and O26's Function in scene now reads 'the sign that confirmed the matter (4:7); by the custom the narrator has just told, a man gave his sandal to the other'; R5's source_in_meaning_map cites that O26 line in place of the old absence; (2) R2's note ends 'The voice accepts such a rendering and does not correct or remark on it.' and R5's note adds 'The voice accepts it and does not correct or remark on it.' after the 'and gave it to Boaz' sentence (ruling 5 stands: the voice tells as the text and does not itself add the handing); (3) B19's Relationship lines in Scenes 2–4 read 'the nearer redeemer', 'the nearer redeemer, now declining', 'the nearer redeemer, withdrawing by the old form' (was 'the nearer kinsman' …)."
    },
    {
      "decision_id": "P11-D7",
      "decision": "After the team's session, Marcia's word of 2026-09-28: the never-rules go to the Validator (do_not_decide), P11's too; R13 flipped whole, R9's never-rules moved into a new do_not_decide entry R15.",
      "description": "Her words (2026-09-28, after the team's session ended), given in answer to a message that said the same gap also affects part of P11: «A sessão acabou. Pode passar as regras do tipo nunca para o validador; pode trocar \"parente\" por \"resgatador\" nas quatro linhas em que Boaz é o resgatador; pode usar os títulos que você escreveu.» The app's Validator reads, from the register, only the id, kind and note of do_not_decide entries, so a never-rule outside do_not_decide reached neither the voice nor the Validator; in the live goldens of 2026-09-28 the voice called the nearer redeemer (B19) 'parente' five to six times in each P11 run while R9's 'never 'kinsman' or 'relative'' was not do_not_decide. In P11: R13 (the minor text points) is now do_not_decide as a whole: every sentence in it is a rule on how the voice says a text point and how a team telling of it is heard ('sold', 'if he will not redeem', 'our kinsman' for Elimelech, 'before the inhabitants' correct; never that Elimelech was the blood brother of both men; never at 4:5 that Boaz acquires Ruth, a team telling that follows such a Bible offered back gently), and the never-rule of point (5) needs the sentences before it. R9 mixed the FIG_0112 keep-image with never-rules, so its three rule sentences — 'The nearness is kinship, not place or friendship (P07 R5, P09 R7). Never call it a queue. The redeemer word stays 'redeemer', never 'kinsman' or 'relative' (P09 R14).' — moved, word for word, into a new entry R15 (CROSS_PERICOPE_PAIRING_CLOSED_HERE, do_not_decide, traced to the P11 map); the first goes with the two because the 'it' of 'Never call it a queue' is the nearness. R9 keeps the keep-image and stays not do_not_decide. R8, R11, R12 and R14 carry no never-rule and are unchanged. Note texts otherwise unchanged. The register now has 15 entries, 10 do_not_decide (R1–R7, R10, R13, R15). The P13 register's references to the redeemer word (R2's note and source, the carried-forward list) now name P11 R15."
    }
  ],
  "vocabulary_additions": {
    "proposition_kinds": [
      {
        "value": "DECLINED",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). MM P11: 'I cannot redeem it for myself, lest I ruin my own inheritance' — the redeemer declines; no approved kind covers a refusal."
      },
      {
        "value": "PASSED_BY",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · bulk-tick by Marcia 2026-06-13 (proposition_kind)",
        "status": "CONFIRMED",
        "note": "Clean event-kind mint (proposition_kind bulk — no cross-axis/collapse/prose issue). MM P2: 'the redeemer of whom Boaz had spoken is passing by' — incidental passage with no approved kind."
      }
    ],
    "scene_kinds": [
      {
        "value": "GATE_COURT_CONVENING_SCENE",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM S1 title and 3F: the court convened in three sittings at the gate; no approved scene_kind covers a legal convening."
      },
      {
        "value": "REDEMPTION_DECLINE_SCENE",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM S3: the second stage springs and the claim reverses into the decline that frees Boaz; no approved scene_kind for the declination."
      },
      {
        "value": "REDEMPTION_OFFER_SCENE",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-13 (scene_kind)",
        "status": "CONFIRMED",
        "note": "Scene-kind (Marcia 2026-06-13 bulk-tick). MM S2: the first stage — the field offered, the confident claim drawn; no approved scene_kind for a redemption offer."
      }
    ],
    "presence_values": [],
    "referential_forms": [],
    "other": [],
    "arc_elements": [
      {
        "value": "ATTESTATION_BY_SANDAL",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM Scene 4: the right transferred and confirmed by the drawn-off sandal, the proceeding's one physical act."
      },
      {
        "value": "GATE_COURT_CONVENED",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1/Scene 1: Boaz takes the gate, seats the redeemer and ten elders — the court is convened; no approved arc token covers a legal convening."
      },
      {
        "value": "REDEMPTION_DECLINED",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM Scene 3: the nearer redeemer reverses his claim and declines; no approved token for a declination."
      },
      {
        "value": "REDEMPTION_OFFER",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM Scene 2: the field-portion laid before the court with first right of redemption offered; no approved token for a redemption offer."
      },
      {
        "value": "STAGED_DISCLOSURE",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-19 (arc_element)",
        "status": "CONFIRMED",
        "note": "arc_element (Marcia 2026-06-19 bulk-tick): clean reusable arc-type. MM 2.1/2.4: the disclosure deliberately staged — field first, Ruth second — the load-bearing shape of the passage."
      }
    ],
    "action_values": [
      {
        "value": "DREW_OFF_SANDAL",
        "source": "P11-MEANING-COORDINATES P15@4:8 · SC-0063 drafter run-2026-06-12T15-18-11-527Z (claude-opus-4-8, request 4196ff4e280a003f…) · declared mint (fills.json) · ruled tick by Marcia 2026-06-12 (SC-0064 §B sitting 1, item 7)",
        "status": "CONFIRMED",
        "note": "The redeemer draws off his sandal as the attestation act (4:8; attestation_token O26). HANDED (an approved proposition_kind) was avoided by the drafter because the MM marks the handing as not narrated — only the drawing-off is."
      }
    ],
    "tone_elements": [
      {
        "value": "PROCEDURAL",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-2026-06-12T15-18-11-527Z (claude-opus-4-8, request 4196ff4e280a003f…) · declared mint (fills.json) · ruled tick by Marcia 2026-06-12 (SC-0064 §B sitting 1, item 10)",
        "status": "CONFIRMED",
        "note": "Brisk, public, and procedural — the opposite key from the night before (MM 2.3); the gate-court's legal-transactional texture has no approved tone token."
      }
    ],
    "role_in_scene_beings": [
      {
        "value": "WITNESSING_ELDERS",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM S1: 'the seated witnesses who make the gate a court'; no approved role for legal witnesses."
      },
      {
        "value": "CONVENER",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM S1: Boaz 'takes the gate, calls the redeemer aside, and seats the elders'; no approved role names a convener of a proceeding."
      },
      {
        "value": "NEARER_REDEEMER",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM S1: 'kinsman of Elimelech's line, nearer in the queue than Boaz (3:12)'; the queue-priority role is distinct from the generic REDEEMER_KIN."
      },
      {
        "value": "REDEMPTION_OFFEROR",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM S2: 'the one who lays out the field-matter before the court'; no approved role for the one tendering a redemption offer."
      },
      {
        "value": "SELLER",
        "source": "P11-MEANING-COORDINATES · SC-0063 drafter run-run-2026-06-12T15-18-11-527Z (claude-opus-4-8, req 4196ff4e280a003f…) · ruled by Marcia 2026-06-13 (role_in_scene_being)",
        "status": "CONFIRMED",
        "note": "Scene role (Principle A, Marcia 2026-06-13). MM S2: 'the seller — the widow whose hand holds Elimelech's portion'; the seller function is not among approved roles."
      }
    ]
  },
  "proposition_kind_slot_sets": [],
  "high_risk_register_audit": [
    {
      "id": "R1",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "the order of the telling at 4:3–6 (P5–P12): the field alone and 'I will redeem' (4:3–4, P5–P8), then Ruth (4:5, P9–P10) and 'I cannot' (4:6, P11–P12); FIG_0165",
      "note": "REQUIRED. Keep the order of the telling: Boaz speaks first of the field alone (4:3–4) and the redeemer says 'I will redeem' (4:4); then Boaz adds: on the day you buy the field from Naomi's hand, you also acquire Ruth the Moabite, the wife of the dead, to raise up the name of the dead upon his inheritance (4:5), and the redeemer says 'I cannot' (4:6). A telling that joins the field and Ruth in one offer loses the man's turn from 'I will redeem' to 'I cannot'; offer it back gently as a missing detail. The narrator does not say why Boaz speaks in this order. Voice and team never say that Boaz planned it, held Ruth back on purpose, wanted the man to refuse, or felt relief or fear; if asked why, the text does not say.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 2.1 ('What weighs on the passage is the order of the telling: Boaz speaks first of the field alone, and the man says I will redeem; then he says that whoever buys the field also acquires Ruth, and the man says I cannot. The narrator does not say why Boaz speaks in this order.'); Section 2.4 ('It keeps the order of the telling — the field first, then Ruth — and the man's two answers.'); Section 5B Figure Flags (FIG_0165 'the order of the telling: the field first, Ruth second; the narrator does not say why'); Section 3F Scene 2 ('Lays the field alone before the court, and the redeemer says: I will redeem.'); Significant Absence in Scene 2 ('Ruth is not mentioned in this first offer; Boaz speaks of the field alone.'); Section 3F Scene 3 ('Boaz adds the second term — whoever buys the field also acquires Ruth, to raise up the name of the dead — and the man who said I will redeem now says I cannot, and gives his right of redemption to Boaz.'); Section 4 Propositions 5, 8, 9 and 11"
    },
    {
      "id": "R2",
      "kind": "NAMING_SHIFT",
      "applies_to": "B19 the nearer redeemer at 4:1 (P3): peloni almoni, 'So-and-so'; FIG_0162, FIG_0163; carried from P09 R7",
      "note": "REQUIRED. Boaz calls him peloni almoni — 'So-and-so', a way of speaking of someone without saying his name (Portuguese 'Fulano'); 'friend' is not in the Hebrew. The narrator calls him only 'the redeemer' and does not give his name. A team rendering with any non-name ('amigo', 'você aí', or the like) is correct. No one gives him a name or a label that judges him; no one says why he is unnamed; no one decides whether Boaz said 'So-and-so' aloud or the narrator left the name out. If asked, the story gives no name and does not say why. The voice accepts such a rendering and does not correct or remark on it.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3A Scene 1 (B19 heading '[[B19-The-Nearer-Redeemer]] — פְּלֹנִי אַלְמֹנִי / \"So-and-so\"'; 'Boaz calls him peloni almoni — So-and-so, without a name; the narrator calls him only \"the redeemer\"'); Section 2.2 ('the narrator does not give his name: Boaz calls him peloni almoni — So-and-so, a way of speaking of someone without saying his name — and the narrator calls him only \"the redeemer\"'); Significant Absence in Scene 1 ('The narrator does not give his name; Boaz calls him So-and-so.'); Section 3E Scene 1 ('turn aside, sit here, So-and-so'); Section 4 Proposition 3 ('So-and-so (without a name)'); Section 5B Figure Flags (FIG_0162 active at Proposition 3; FIG_0163 'the nearer redeemer unnamed; Boaz calls him So-and-so'); carried forward from P09 R7"
    },
    {
      "id": "R3",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "the refusal at 4:6 (P11, P12): 'I cannot', said twice; FIG_0166, FIG_0168; CB_0003",
      "note": "REQUIRED keep: his own words — 'I cannot redeem it for myself, lest I ruin my own inheritance … for I cannot redeem' — 'I cannot', said twice. A team telling 'he did not want to' is offered back gently: he said 'I cannot'. He does not explain why it would ruin his inheritance. Voice and team give no reason beyond his own (no money, no wife or children, not Ruth being a Moabite), and neither judge him (selfish, coward, greedy) nor praise him (prudent). If asked, the voice says he does not explain; the story only sets side by side Boaz's 'to raise up the name of the dead upon his inheritance' and the man's 'lest I ruin my own inheritance'.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 3 ('And the redeemer says: I cannot redeem it for myself, lest I ruin my own inheritance. You — redeem my right of redemption for yourself, for I cannot redeem.'); Significant Absence in Scene 3 ('Why it would ruin the man's inheritance is never explained; he says only \"I cannot\", twice.'); Section 3C Scene 3 (CB_0003 'set side by side: Boaz's \"to raise up the name of the dead upon his inheritance\" and the man's \"lest I ruin my own inheritance\"; he does not explain how it would ruin his own'); Section 2.3 ('the answer turns into I cannot, said twice'); Section 5B Figure Flags (FIG_0166 'the stated reason, kept verbatim'; FIG_0168 active at Proposition 11); Section 4 Propositions 11 and 12"
    },
    {
      "id": "R4",
      "kind": "SIGNIFICANT_ABSENCE",
      "applies_to": "the redeemer passing at 4:1 (P2): 'and behold' only (FIG_0160); the 2:3 pair (FIG_0015, P05 R4–R5) in the canon record only",
      "note": "At 4:1 the text says only 'and behold, the redeemer of whom Boaz had spoken was passing by' (FIG_0160). There is no word of chance and no word of God. The voice tells only that and adds no 'by chance', no 'coincidence', no 'God made him pass', and no comment; the narrator does not say why he passes at that moment. A team telling 'by chance' or 'God made him pass' is offered back gently: the story says only 'and behold'. The canon record pairs 4:1 with 2:3 (FIG_0015, P05 R4–R5); 4:1 does not repeat the words of 2:3, the figure is not flagged at 4:1, and the link is not part of P11's telling.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 1 ('and behold, the redeemer of whom Boaz had spoken is passing by'); Section 2.2 ('Boaz sits down at the gate, and behold, the redeemer of whom he had spoken passes by; the narrator does not say why he passes at that moment.'); Section 3F Scene 1 ('The redeemer is passing just then, and the narrator does not say why.'); Significant Absence in Scene 1 ('The narrator does not say why he passes at that moment.'); Section 5B Figure Flags (FIG_0160 'the narrator's \"and behold\"; optional keep'); Section 4 Proposition 2; FIG_0015 is in neither the map's active-figures nor Section 5B (removed under SC-0087); carried forward from P05 R4 and R5"
    },
    {
      "id": "R5",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "the sandal at 4:7–8 (P13–P15): the narrator's aside on the old custom, then the sandal drawn off; FIG_0005, CB_0007, O26",
      "note": "REQUIRED keep: the narrator stops to explain to the listeners a custom of former times in Israel — for redeeming and for exchanging, to confirm every matter, a man drew off his sandal and gave it to his fellow; this was the attestation (4:7) — then the redeemer says 'buy it for yourself' and draws off his sandal (4:8). The voice tells as the text and does not itself add the handing: the narrator tells only that he drew off his sandal, and the custom he has just explained says the sandal was given to the other. A team telling 'and gave it to Boaz' is correct, not an addition. The voice accepts it and does not correct or remark on it. Voice and team bring in no law the story does not cite (the levirate law, the ceremony of Deuteronomy 25), never say the sandal was a shame, and never say Ruth took part.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 4 ('Now this was formerly in Israel, for the redeeming and for the exchanging, to confirm every matter: a man drew off his sandal and gave it to his fellow — this was the attestation in Israel.'; 'buy it for yourself — and he draws off his sandal'); Section 3F Scene 4 ('First the narrator stops to explain the old custom; then the sandal comes off'); Section 3C Scene 4 (O26 'the sign that confirmed the matter (4:7); by the custom the narrator has just told, a man gave his sandal to the other'; CB_0007 'the old confirming-custom — for redeeming and for exchanging, a man drew off his sandal and gave it to his fellow'); Section 1 Metadata multi-level register tagging ('The narrator's aside at v.7, explaining the old custom to the listeners, stays the narrator's own plain voice inside the formal scene.'); Section 5B Figure Flags (FIG_0005 'the custom the narrator explains, and the sandal drawn off'); Section 4 Propositions 13, 14 and 15"
    },
    {
      "id": "R6",
      "kind": "SIGNIFICANT_ABSENCE",
      "applies_to": "Ruth and Naomi absent from the gate (FIG_0016; P5, P9); the night at the threshing floor not spoken of; the name of God not spoken (FIG_0014; P13)",
      "note": "Three silences kept as facts: Ruth and Naomi are not at the gate, and neither of them speaks; at the gate no one speaks of the night at the threshing floor (3:14); no one says the name of God in the proceeding. Voice and team do not bring the women to the gate or give them words or feelings during the scene (for example, 'Ruth was waiting anxiously'), make no comment on whether it was fair, have no one at the gate speak of the night, and put no prayer or 'thank God' in the characters' mouths.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 2.2 ('Through all eight verses Ruth and Naomi are not at the gate, and neither of them speaks; at the gate no one speaks of the night at the threshing floor; and no one says the name of God.'); Section 2.4 ('Ruth and Naomi stay offstage, no one at the gate speaks of the night, and the name of God is not spoken.'); Significant Absence in Scene 1 ('Ruth and Naomi are not present, and will not be, through the whole proceeding.'); Significant Absence in Scene 3 ('Ruth and Naomi are not at the gate; neither of them speaks. At the gate no one speaks of the night at the threshing floor.'); Significant Absence in Scene 4 ('In the whole proceeding no one says the name of God.'); Section 5B Figure Flags (FIG_0016 'Ruth and Naomi are not at the gate'; FIG_0014 'the name of God is not spoken in the whole proceeding')"
    },
    {
      "id": "R7",
      "kind": "WITHHELD_PAIRING_PER_SOURCE_DISCIPLINE",
      "applies_to": "Ruth 'the wife of the dead' at 4:5 (P9, P10); the dead husband B? (THE_DEAD_UNNAMED); carried from P01 R10, P02 R5, P06 R4",
      "note": "Ruth is 'the wife of the dead'; the dead husband is not named here. Never say or suggest which of Naomi's sons was Ruth's husband; the pairing is disclosed only at 4:10.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3A Scene 3 (B9 '\"the Moabite\" and \"the wife of the dead\" — the foreigner-marker, spoken by Boaz in the terms; her husband still unnamed'; the dead 'Ruth's late husband; his name is not said here'); Significant Absence in Scene 3 ('The dead husband is \"the dead\"; his name is not said here.'); Section 2.2 ('Ruth is named \"the Moabite, the wife of the dead\": her husband still goes unnamed.'); Significant Absence in Scene 2 ('his sons are not named'); Section 4 Proposition 9 ('the wife of the dead'); MEANING_COORDINATES S3 B? (THE_DEAD_UNNAMED), P9 deceased_husband B?, P10 name_borne_by B?; carried forward from P01 R10, P02 R5, P06 R4"
    },
    {
      "id": "R8",
      "kind": "NAMING_SHIFT",
      "applies_to": "Ruth the Moabite at 4:5 (P9), in Boaz's terms; FIG_0001, CB_0004; carried from P07 R7",
      "note": "REQUIRED keep-image. In Boaz's terms Ruth is 'Ruth the Moabite, the wife of the dead'. Keep 'the Moabite' in the line. It is no reason for the refusal (R3).",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 3E Scene 3 ('you also acquire [[B9-Ruth]] Ruth the Moabite, the wife of the dead'); Section 3A Scene 3 (B9 '\"the Moabite\" and \"the wife of the dead\" — the foreigner-marker, spoken by Boaz in the terms'); Section 3C Scene 3 (CB_0004 'the foreigner-marker, spoken by Boaz in the terms'); Section 2.4 ('Ruth is named again as the Moabite'); Section 4 Proposition 9 ('Ruth the Moabite'); Section 5B Figure Flags (FIG_0001 'the foreigner-marker, in Boaz's terms'); carried forward from P07 R7"
    },
    {
      "id": "R9",
      "kind": "CROSS_PERICOPE_PAIRING_CLOSED_HERE",
      "applies_to": "FIG_0112 Close-to-Us at 4:1 (P2) — CLOSES here; opened at P07 P12 (2:20), middle station at P09 P17 (3:12); CB_0045; its never-rules are R15",
      "note": "PREFERRED keep-image. The nearness word of 2:20 ('near to us, one of our redeemers') and 3:12 ('a redeemer nearer than I') reaches its answer here: there is a redeemer nearer than Boaz, who comes first because he is nearer, and Boaz says it in his own words — 'there is no one besides you to redeem, and I am after you' (4:4).",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 5B Figure Flags (FIG_0112 'the nearness word of 2:20 and 3:12: the nearer redeemer comes first — \"there is no one besides you to redeem, and I am after you\" (4:4)'); Section 3A Scene 1 (B19 'a redeemer nearer than Boaz, who comes first because he is nearer (3:12)'); Section 3C Scene 1 (CB_0045 'the redeemer nearer than Boaz, who comes first because he is nearer'; 'the redeemer Boaz spoke of at 3:12; he answers first'); Section 3E Scene 2 ('for there is no one besides you to redeem, and I am after you'); Section 3A Scene 2 (B13 'after the nearer redeemer — \"I am after you\" (4:4)'); Section 2.4 ('there is no one besides the nearer man to redeem, and Boaz is after him (4:4)'); carried forward from P07 R5 and P09 R7"
    },
    {
      "id": "R10",
      "kind": "WITHHELD_PAIRING_PER_SOURCE_DISCIPLINE",
      "applies_to": "Boaz's conditional promise of 3:13 (P09 R15) resolved as told at 4:6–8 (P11, P12, P15); the marriage is not told here",
      "note": "At 3:13 Boaz bound his promise to the order of redeemers (P09 R15). Here it is resolved only as the text tells it: the nearer redeemer says he cannot redeem, gives his right of redemption to Boaz (4:6), and draws off his sandal (4:8). The marriage is not told here: never say that Boaz married Ruth or will marry her in this passage.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 2.4 ('This passage settles the matter Boaz bound to the order of redeemers at 3:12–13: there is no one besides the nearer man to redeem, and Boaz is after him (4:4); the nearer man says he cannot redeem, and the right of redemption passes to Boaz, with a sandal for the attestation.'); Section 3A Scene 1 (B13 'the redeemer who promised under oath at 3:13 to redeem if the nearer redeemer would not'); Section 3F Scene 3 ('the man who said I will redeem now says I cannot, and gives his right of redemption to Boaz'); Section 3A Scene 4 (B13 'the one the right of redemption passes to'; 'the redeemer who now holds the right of redemption'); Section 3E Scene 4 ('and he draws off his sandal'); Section 4 Propositions 11, 12 and 15; carried forward from P09 R15"
    },
    {
      "id": "R11",
      "kind": "FIGURE_FIRST_OCCURRENCE",
      "applies_to": "single keep-images: FIG_0164 (P3, P4), FIG_0167 (P6), FIG_0002 + CB_0005 (P10), FIG_0110 + CB_0039 (P10), FIG_0156 (P1)",
      "note": "PREFERRED (FIG_0164): Boaz sits, the redeemer sits, the ten elders sit; 'sit here' is said twice. OPTIONAL (FIG_0167): 'I will uncover your ear' means 'I resolved to tell you'; the voice may explain the idiom; the plain form is correct. REQUIRED (FIG_0002, CB_0005): Boaz's stated purpose — 'to raise up the name of the dead upon his inheritance' — kept in its words. FIG_0110 / CB_0039: 4:5 says only 'the dead'; 'the living and the dead' of 2:20 is not repeated here, and 2:20 is not brought into 4:5 (P07 R4 corrected under SC-0087). FIG_0156: Naomi's word of 3:18 — the man will not rest until he has finished the matter today — and here Boaz goes up to the gate.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 5B Figure Flags (FIG_0164 'sit-here to the redeemer; sit-here to the ten; the session seated'; FIG_0167 'an idiom for \"I resolved to tell you\"; optional keep'; FIG_0002 'the purpose Boaz states for acquiring Ruth'; FIG_0110 'the dead kept in the reckoning — only \"the dead\" is said here'; FIG_0156 'opened at 3:18 in Naomi's words — the man will not rest until he has finished the matter today; here Boaz goes up to the gate'); Section 3F Scene 1 ('Boaz sits, the redeemer sits, the ten elders sit'); Section 3E Scene 1 ('turn aside, sit here, So-and-so'; 'and says: sit here — and they sit'); Section 3E Scene 2 ('I will uncover your ear — I resolved to tell you'); Section 3C Scene 3 (CB_0005 'the stated purpose of acquiring Ruth: to raise up the name of the dead upon his inheritance'; CB_0039 'the dead man kept in the family's reckoning: \"the dead\"'); Section 5A Concept Flags (CB_0039 'the dead kept in the family's reckoning — only \"the dead\" is said'); Section 2.2 ('the man will not rest unless he has finished the matter today (3:18)'); Section 4 Propositions 1, 3, 4, 6 and 10"
    },
    {
      "id": "R12",
      "kind": "STRUCTURAL_FRAMING_DEVICE",
      "applies_to": "register: Scene 1 INFORMAL_CASUAL; Scenes 2–4 FORMAL_OFFICIAL at scene level (S2, S3, S4); 4:7 moment-level INFORMAL_CASUAL",
      "note": "The whole passage sits in INFORMAL_CASUAL. Scenes 2 through 4 carry FORMAL_OFFICIAL at scene level: from the moment the ten elders are seated, the talk is a legal proceeding at the town gate — offer, terms, refusal, and the attestation act, all spoken before witnesses. Scene 1 stays in the plain narrative key: the convening — Boaz sitting down, the redeemer passing, 'turn aside, sit here' — is brisk, not yet the proceeding. The narrator's aside at 4:7, explaining the old custom to the listeners, stays the narrator's own plain voice inside the formal scene (moment-level INFORMAL_CASUAL).",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 1 Metadata multi-level register tagging ('The whole passage sits in INFORMAL_CASUAL.'; 'Scenes 2 through 4 shift to FORMAL_OFFICIAL at scene level: from the moment the ten elders are seated, the talk is a legal proceeding at the town gate — offer, terms, refusal, and the attestation act, all spoken before witnesses.'; 'Scene 1 stays in the plain narrative key'; 'The narrator's aside at v.7, explaining the old custom to the listeners, stays the narrator's own plain voice inside the formal scene.'); MEANING_COORDINATES register_overrides (scene_level S2, S3, S4 FORMAL_OFFICIAL; moment_level 4:7 INFORMAL_CASUAL)"
    },
    {
      "id": "R13",
      "kind": "TEXTUAL_CLARITY_FLAG",
      "applies_to": "minor text points at 4:3 (P5), 4:4 (P6, P7) and 4:5 (P9)",
      "note": "Minor text points. (1) 4:3: the voice says Naomi 'is selling' the field; a team telling 'sold' is correct (the Hebrew verb allows both). (2) 4:4: the Hebrew has 'if he will not redeem' where 'you' is expected; the map line and the voice say 'if you will not redeem, tell me'; both forms are correct in a team telling. (3) 'Our brother Elimelech' means a kinsman: 'our brother' and 'our kinsman' are both correct; never say that he was the blood brother of both men. (4) 4:4: 'before those seated' and 'before the inhabitants' are both correct. (5) 4:5 keeps the reading Marcia ruled on 2026-06-11 (SC-0057, the qere): whoever buys the field also acquires Ruth. The written text (ketiv) reads 'I acquire', and some Bibles read 'also from the hand of Ruth' (e.g. the ARA). The voice follows the map, does not teach the variants, and never says at 4:5 that Boaz acquires Ruth; a team telling that follows such a Bible is offered back gently with the map's reading.",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3E Scene 2 ('Naomi, who returned from the fields of Moab, is selling it'; 'buy it before those seated and before the elders of my people'; 'and if you will not redeem, tell me, that I may know'); Section 2.1 ('the portion of our brother Elimelech, which Naomi, back from the fields of Moab, is selling'; 'then he says that whoever buys the field also acquires Ruth'); Section 3A Scene 2 (B2 '\"our brother\" — kin to both men at the gate'); Section 3F Scene 3 ('whoever buys the field also acquires Ruth'); Section 4 Propositions 5, 6, 7 and 9"
    },
    {
      "id": "R14",
      "kind": "DISCOURSE_THREAD_ADVANCED",
      "applies_to": "T2 line-and-redemption thread: the right of redemption passes to Boaz at 4:6–8 (P12, P15); canon-record forward links to P12 and P13",
      "note": "T2 (line and redemption; P05 R8, P07 R12, P09 R14): the right of redemption passes to Boaz at the gate, with the sandal for the attestation. In the canon record the thread continues to 4:9–10 (P12), where the purchase is declared and Ruth acquired as wife; FIG_0002, FIG_0110, FIG_0005, FIG_0003 and FIG_0014 continue to P12 and FIG_0016 to P13. These links stay here only and are not part of P11's telling.",
      "required_in_audit": true,
      "source_in_meaning_map": "Section 2.4 ('the nearer man says he cannot redeem, and the right of redemption passes to Boaz, with a sandal for the attestation'); Section 3A Scene 4 (B13 'the one the right of redemption passes to'; 'the redeemer who now holds the right of redemption'); Section 3F Scene 4 ('the right is Boaz's, attested in the old form'); Section 3E Scene 3 ('You — redeem my right of redemption for yourself, for I cannot redeem.'); Section 4 Propositions 12 and 15; the forward links to P12 and P13 are recorded only here and in cross_pericope_pair_verification — the map carries none (SC-0087); carried forward from P05 R8, P07 R12, P09 R14"
    },
    {
      "id": "R15",
      "kind": "CROSS_PERICOPE_PAIRING_CLOSED_HERE",
      "applies_to": "the nearness word (FIG_0112, CB_0045) at 4:1 (P2) and the redeemer word for B19 (R9): kinship, not a queue; never 'kinsman' or 'relative'; carried from P07 R5, P09 R7, P09 R14 (moved out of R9, 2026-09-28)",
      "note": "The nearness is kinship, not place or friendship (P07 R5, P09 R7). Never call it a queue. The redeemer word stays 'redeemer', never 'kinsman' or 'relative' (P09 R14).",
      "required_in_audit": true,
      "do_not_decide": true,
      "source_in_meaning_map": "Section 3A Scene 1 (B19 'a redeemer nearer than Boaz, who comes first because he is nearer (3:12)'; 'the narrator calls him only \"the redeemer\"'); Section 3A Scenes 2–4 (B19 Relationship 'the nearer redeemer'); Section 5B Figure Flags (FIG_0112 'the nearness word of 2:20 and 3:12: the nearer redeemer comes first'); carried forward from P07 R5, P09 R7 and P09 R14"
    }
  ],
  "cross_pericope_pair_verification": {
    "pairs": [
      {
        "fig_id": "FIG_0156",
        "opens_at": "P10 P13 (3:18 'the man will not rest unless he has finished the matter today')",
        "closes_at": "P11 P1 (4:1 Boaz goes up to the gate)",
        "verification_status": "VERIFIED",
        "note": "Pair closed at this register (R11), on the two MEANING_COORDINATES: the P10 MC flags FIG_0156 at P13 (3:18b), the P11 MC at P1 (4:1a). Registry frontmatter (vault note) confirms opens-at P10 / closes-at P11. P10's own register is still the skeleton, so the opening half has no P10 entry yet."
      },
      {
        "fig_id": "FIG_0112",
        "opens_at": "P07 P12 (2:20 close to us)",
        "closes_at": "P11 P2 (4:1-4 'there is no one besides you to redeem, and I am after you'); middle station at P09 P17 (3:12 'a redeemer nearer than I')",
        "verification_status": "VERIFIED",
        "note": "Pair closed at this register (R9). P07 opened it (P07 R5) and left its row PENDING; the middle station was verified at P09 (P09 R7: the P09 MC flags FIG_0112 at P17). It lands at P11 P2, where the P11 MC flags FIG_0112 with CB_0045. Registry frontmatter (vault note) confirms opens-at P07 / closes-at P11."
      },
      {
        "fig_id": "FIG_0015",
        "opens_at": "P05 P5 (2:3 vayyiqer miqreha)",
        "closes_at": "P11 (4:1) — canon-record link only; not flagged at 4:1, which has only 'and behold' (FIG_0160)",
        "verification_status": "VERIFIED",
        "note": "Canon-record link only (R4; SC-0087). 4:1 does not repeat the words of 2:3: the text says only 'and behold, the redeemer of whom Boaz had spoken was passing by' (FIG_0160). FIG_0015 is removed from the P11 map (active-figures and Section 5B) and from the P11 MC P2 figure_flags; the P05 MC flags it at P5 (2:3b). The link is not part of P11's telling. P05 R4 is unchanged; P05 R5 and the P05 pair row carry the correction."
      },
      {
        "fig_id": "FIG_0110",
        "opens_at": "P07 P11 (2:20 the living and the dead)",
        "closes_at": "P12 (4:10); at P11 P10 (4:5) only 'the dead' is said",
        "verification_status": "PENDING",
        "note": "At P11 P10 (4:5) the P11 MC flags FIG_0110 with CB_0039: 4:5 says only 'the dead' — the 2:20 phrase 'the living and the dead' is not repeated there, and 2:20 is not brought into 4:5 (P07 R4, corrected under SC-0087; R11). The P12 MC flags FIG_0110 at P5 (4:10c); full verification at P12's register (registry closes-at P12)."
      },
      {
        "fig_id": "FIG_0001",
        "opens_at": "P01 P10 (1:4; book-wide arc 1:4, 1:22, 2:2, 2:6, 2:21)",
        "closes_at": "P12 P3 (4:10); at P11 P9 (4:5) in Boaz's terms",
        "verification_status": "DEFERRED",
        "note": "Book-wide arc (P07 R7, R8). At P11 P9 (4:5) the P11 MC flags FIG_0001 with CB_0004: in Boaz's terms Ruth is 'Ruth the Moabite, the wife of the dead'. The P12 MC flags it at P3 (4:10a); verification deferred to P12's register (registry closes-at P12)."
      },
      {
        "fig_id": "FIG_0002",
        "opens_at": "P11 P10 (4:5 'to raise up the name of the dead upon his inheritance')",
        "closes_at": "P12 (4:10)",
        "verification_status": "PENDING",
        "note": "Opens here (R11): the P11 MC flags FIG_0002 at P10 with CB_0005 and CB_0002. The P12 MC flags it at P4 (4:10b); verification at P12's register (registry opens-at P11 / closes-at P12). Canon-record link only, not part of P11's telling (R14)."
      },
      {
        "fig_id": "FIG_0005",
        "opens_at": "P11 P14-P15 (4:7-8 the custom told, the sandal drawn off)",
        "closes_at": "P12 (4:9)",
        "verification_status": "PENDING",
        "note": "Opens here (R5): the P11 MC flags FIG_0005 at P14 and P15. The P12 MC flags it at P1 (4:9a); verification at P12's register (registry opens-at P11 / closes-at P12). Canon-record link only, not part of P11's telling (R14)."
      },
      {
        "fig_id": "FIG_0003",
        "opens_at": "P11 P1 (4:1 the gate)",
        "closes_at": "P12 (4:10-11)",
        "verification_status": "PENDING",
        "note": "Opens here: the P11 MC flags FIG_0003 at P1 with CB_0006. The registry (vault note) lists opens-at P11 / closes-at P12, but neither the P12 map nor the P12 MC flags FIG_0003 yet; the close is for P12's register to settle. Canon-record link only, not part of P11's telling (R14)."
      },
      {
        "fig_id": "FIG_0016",
        "opens_at": "P11 P5, P9 (4:3, 4:5 Ruth and Naomi not at the gate)",
        "closes_at": "P13 (4:16)",
        "verification_status": "PENDING",
        "note": "Opens here (R6): the P11 MC flags FIG_0016 at P5 and P9. The P13 MC flags it at P8 (4:16a); registry opens-at P11 / closes-at P13 (its appears-in also lists P12, whose map and MC do not flag it). Canon-record link only, not part of P11's telling (R14)."
      },
      {
        "fig_id": "FIG_0014",
        "opens_at": "P11 P13 (4:7; no one says the name of God in the proceeding)",
        "closes_at": "P12 (4:11)",
        "verification_status": "PENDING",
        "note": "Opens here (R6): the P11 MC flags FIG_0014 at P13. The P12 MC flags it at P8 (4:11b), where the P12 map says the pair closes; the P13 MC flags it again at P4 (4:14a), and the registry (vault note) lists closes-at P13 — for the P12 and P13 registers to settle. Canon-record link only, not part of P11's telling (R14)."
      }
    ]
  },
  "validation_checklist": {
    "meaning_map_contains_only_story_content": true,
    "meaning_coordinates_contains_only_inference_signal": true,
    "every_proposition_has_cb_flags_and_figure_flags": true,
    "no_grammatical_frame_slot_names": true,
    "speech_act_present_on_all_component_records": true,
    "speech_act_values_used": [
      "DIRECTS_HEARER_TO_DO",
      "GRANTS_PERMISSION_TO_DO",
      "REFUSES_REQUEST_WITH_COUNTER_DECLARATION",
      "STATES_AS_TRUE"
    ],
    "discourse_threads_tracked_in_audit_only": true,
    "known_limitations_tracked_in_audit_only": true,
    "high_risk_register_complete": true,
    "every_high_risk_entry_traces_to_meaning_map": true,
    "no_content_added_beyond_meaning_map": true,
    "registry_additions_extracted_to_bcd_delta": true,
    "no_reviewer_facing_prompts_in_compilation_log": true
  },
  "known_limitations": [
    "Mechanized ruled log (SC-0064 close part 2): the judgment half was machine-drafted (SC-0063) and reviewer-ruled; vocabulary_additions are assembled from this pericope's per-axis ruling-logs.",
    "The high-risk register audit was hand-authored from the corrected P11 map and ruled by Marcia 2026-09-27 under SC-0087: 15 entries (10 do_not_decide: R1–R7, R10, R13, R15 — R13 and R15 since Marcia's word of 2026-09-28 after the session, P11-D7), each traced to the P11 map; the carried-forward items (P01 R10, P02 R5, P05 R4/R5/R8, P06 R4, P07 R4/R5/R7/R12, P09 R7/R14/R15) also cite their source registers (P11-D4).",
    "Propositions stay at meaning-map granularity; multi-event propositions decompose in-slot per the granularity contract.",
    "Forward links out of P11 (FIG_0002, FIG_0110, FIG_0005, FIG_0003, FIG_0014 and FIG_0001 to P12; FIG_0016 to P13; the T2 thread to 4:9–10) live only in this register (R14) and the pair table; the map carries none. The P12 and P13 registers are still skeletons, so those rows stay PENDING or DEFERRED.",
    "Pair data to settle at P12/P13: FIG_0003 — the registry (vault note) lists closes-at P12, but neither the P12 map nor the P12 MEANING_COORDINATES flags it; FIG_0014 — the P12 map says the pair closes at 4:11, while the vault note lists closes-at P13 and the P13 MEANING_COORDINATES flags it again at 4:14a.",
    "FIG_0015 is no longer flagged at 4:1 (SC-0087, R4); the vault FIG_0015 note still lists appears-in [P05, P11] and closes-at P11 (P11:4:1). The pair is kept in the canon record as the FIG_0015 row of the pair table.",
    "Three kinds in this register are not on the approved high_risk_register_kind list — SIGNIFICANT_ABSENCE (R4, R6), TEXTUAL_CLARITY_FLAG (R13) and DISCOURSE_THREAD_ADVANCED (R14); the first two are already used, unpromoted, in P03–P05. They are used as the SC-0087 build spec names them and are not promoted here.",
    "The MEANING_COORDINATES keep arc_element CHANCE_PROVIDENCE_ARRIVAL and STAGED_DISCLOSURE and communicative_function STAGES (ruled SC-0064 values, unchanged by SC-0087, not voiced); what the passage keeps at 4:1 is 'and behold' only (R4), and the order of the telling is kept as a fact without a reason (R1)."
  ]
}
```

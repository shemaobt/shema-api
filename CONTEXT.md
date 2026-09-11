# Internalization Room (server)

The server side of the Room: it keeps what the team records, runs the back-translation, calls the analyst to check what was told against the Meaning Map, settles every finding at an address, and decides how the verdict speech ends. The tablet app and the Desk are its clients.

This glossary covers the Internalization Room. Other subsystems of this server are named
only where a decision record needs their words.

## Language

### Voices and roles

**Guide**:
The persona that leads the conversation with the team throughout the session, outside the back-translation verdict.
_Avoid_: narrator, conductor, Guia

**Speaker**:
The persona that says the back-translation verdict to the team, warmer than the analyst. A single role.
_Avoid_: voice (alternative internal name, and this server's word for the synthesized voice id — see Voice), spoken narrator, TTS, Falante

**Voice** (`voice_id`):
The synthesized voice a line is spoken with, one per language the Room speaks.
_Avoid_: Speaker (the persona spoken by it), narrator, Voz

**Analyst**:
The entity that reads only the told stretches and the Meaning Map, never speaks to the team, and returns findings as JSON and nothing else.
_Avoid_: checker, reviewer, classifier, Analista

**Validator**:
The entity that checks the Guide's or the Speaker's draft speech before audio synthesis and can refuse it, triggering the safety speech.
_Avoid_: analyst (it judges content, not speech), Validador

**Correction check** (`verify_correction`):
The call that checks whether a correction answered the finding, counting the elements the stretch carried, those still told, and those the new telling brought back. Resolved and broken are independent answers.
_Avoid_: analyst (it reads a whole scope; this answers one finding), validator (it judges speech, not content), Verificador de correção

**Team** (`project`):
The group of translators that owns the work. In the schema the column is called `project_id`; the Desk and the backlog say team.
_Avoid_: project (in prose; it is the schema's word for the same entity), user, Equipe

**Desk**:
The facilitator's web app, consumer of the routes for questions, halts and sessions by team.
_Avoid_: panel, dashboard, Mesa

**Room**:
The whole system as the team sees it: the composition of Guide, Speaker, Analyst and Validator. A product metaphor, not a class.
_Avoid_: bot, assistant, Sala

### Units of text and audio

**Pericope**:
The identifier of the biblical passage, the unit of work of a session.
_Avoid_: passage (that is what the id names, not the id itself), text, Perícope

**Scope**:
The slice of the passage checked in one reading by the analyst, which can be smaller than the pericope.
_Avoid_: stretch (the persistent object; a scope is one reading's slice of the passage), trecho, window, Escopo

**Take**:
An audio file recorded by the team, of one of two kinds: rehearsal (`ensaio`, the whole passage in the mother tongue) or back-translation (`retro`, a stretch told in the bridge language).
_Avoid_: recording, audio

**Mother tongue**:
The team's language, the one the rehearsal is recorded in and that nobody on the server understands.
_Avoid_: native, L1, Língua materna

**Bridge language**:
The language the team tells back in, and which the analyst reads.
_Avoid_: L2, Portuguese, Língua-ponte

**Stretch** (`segment`; frase, in Marcia's method and her prompts):
The persistent, addressable object of one told slice of the passage: a slice of a rehearsal take, the matching back-translation take, the transcript, the order and the pass. A correction is a new row that supersedes the previous one, never an edit.
_Avoid_: segment (in prose; it is the wire and table name), Segmento, trecho, chunk (the ephemeral position in one reading, not this object)

**Chunk**:
The numbered position of a stretch in the list the analyst receives in one reading, the frase number of the prompts. The server turns the number back into a stretch, and a **Finding** keeps the number it was given beside the stretch it resolved to. The two are not one answer: a **Missing with an address** placed *after* frase N resolves to stretch N+1, so an addition and a missing element are one swap of one frase when they share the number and not when they share the stretch.
_Avoid_: stretch (the persistent object a chunk points to), segment (that object's wire and table name), chunk_index (the takes column is `ordinal`)

**Pass** (`pass_number`):
How many times a stretch has been told: one on the first telling, two when told again after a finding.
_Avoid_: attempt, version, Passe, tellings (the count of every telling of the stretch, kept on the row)

**Telling back**:
The act of saying, in the bridge language, what a stretch of the mother tongue holds. The Portuguese the room writes and speaks for it is *traduzir / tradução*, and its English and Spanish room literals say *translated* / *traducido*; *contar* belongs to the Conversation with the Guide alone, and *recontar* to the External Check.
_Avoid_: translating (in English prose; the room's own English literal does say translated), transcribing, Contar de volta, Contado de volta, Reconto, Recontar

**Untold**:
A stretch recorded in the mother tongue that has not been told back yet. It is not a finding: it is only waiting to be told, and the analyst is not called.
_Avoid_: missing, pending, Não contado

**Rehearsal** (`ensaio`):
The recording of the whole passage in the mother tongue, and the station where it happens. It is where the team returns when something is missing beyond everything already told.
_Avoid_: recording, `ensaio` (in prose; it is the stored take kind)

**Part**:
One rehearsal take of a passage: the unit the team listens to, tells stretches from and records again. A rehearsal told whole has one part.
_Avoid_: clip (Marcia's word for it), chunk, segment, Parte

**Meaning Map**:
The canonical content of the pericope that the analyst compares against, including preservation rules and the marked silence that is never revealed.
_Avoid_: answer key, base text, Mapa de Sentido

**Necklace** and **bead** (`element`):
The coverage of the passage seen as a string of beads, each bead an element of the Map that travels through not encountered, surfaced, partially engaged and engaged.
_Avoid_: progress, checklist, Colar, conta, Sound Necklace (a different product in this repository)

**Panorama**:
The overview of the book spoken before the first passage; a session records that it followed the panorama, so that the Guide does not introduce itself twice.
_Avoid_: introduction

**Address**:
Where a stretch sits: the take it belongs to, and its start and end in milliseconds inside
that one file.
_Avoid_: range, offset, position, Endereço

**Divided stretch** (`parent_id`, `ordinal`):
A stretch cut out of another one, numbered among its own siblings rather than among the
session's stretches.
_Avoid_: child, split, subsegment, Trecho dividido

**Element kind**:
What a bead of the Meaning Map is: scene, being, place, object, time, absence or preserved.
_Avoid_: type, category, Tipo de elemento

**Coverage event** (`ir_coverage_events`):
One recorded movement of a bead from one coverage state to the next.
_Avoid_: log, history, audit, Evento de cobertura

### Findings

**Finding**:
The analyst's answer about a told stretch: a kind, a note, the **Chunk** it named and, when there is one, a stretch. The kinds, in Marcia's words: missing, addition, unclear.
_Avoid_: error, problem, Achado, the retired kinds meaning change, wrong relation, reordered event and preservation violation (all read as addition), insufficient evidence (retired; it is no finding)

**Missing with an address** (`missing` with `where` before, inside, or after on any chunk but the last):
An element of the Map that is absent and whose place fits an existing chunk: before it, inside it, or after it when a later chunk exists. The team records that stretch again and tells it again.
_Avoid_: internal missing, Falta com endereço

**Missing without an address** (`missing` with `where` after on the last chunk):
An element that is absent and sits after everything that was told. The stretch is null and the speech sends the team to record more and go back to the rehearsal, erasing nothing.
_Avoid_: external missing, missing null, Falta sem endereço

**Where**:
The field of a missing finding that says whether the absent content sits before, inside or after the chunk it cites.
_Avoid_: position, offset, Onde

**Swap** (`current_findings`; *relação trocada*, in Marcia's words):
An addition and a missing element the analyst reported on the same **Chunk**: the telling put one relation in and dropped the one the story tells in its place. One thing for the team — one thing said, one stretch recorded again, one **Correction check** answering both — and never two. Both halves must point at a stretch, so a **Missing without an address** is never half of one. The addition leads it, whichever half the analyst listed first.
_Avoid_: pair (it says there are two things), swapped relation (Marcia's phrase for the mistake, not for what the room carries), troca

**Priority**:
The order in which the room raises one reading's findings: an addition that fills a marked silence, then any other addition, then a missing element, then an unclear frase. A **Swap** ranks by its addition, a finding the **Correction check** put at the front keeps the front for the round that follows, and within one tier the analyst's order holds. The stored list is never reordered; only the pick is.
_Avoid_: severity, ranking, sorting (the stored list keeps the analyst's order), Prioridade

**Filled silence** (`fills_silence`):
An addition the analyst reported under the wire kind `silence`: the telling says something the passage keeps quiet on purpose. It stays an addition for the app, the packet, the golden scripts and the Speaker, and decides only the **Priority**.
_Avoid_: fourth kind, silence kind (the wire name only), Silêncio preenchido

**Points at a stretch** (`points_at_a_stretch`):
The property of a finding that puts one specific stretch on screen with the two microphones. It decides the closing of the verdict.
_Avoid_: has an address, Aponta um trecho

### Correction and verification

**Correction**:
The retaking of exactly one stretch, at the place the current finding points to, to answer it. Detected because only one position of the list changed.
_Avoid_: mend (the app's word for the same gesture), fix, retell (the count of tellings, not this gesture), Correção

**Retell**:
Each new telling of the same stretch after a finding; in the room's Portuguese, *traduzir de novo*. The third telling of a stretch makes it a hard stretch: a warning, never a cap.
_Avoid_: attempt, retry, Reconto, Recontar

**Hard stretch**:
A stretch the team told three times. The room asks for a person once when it happens, and the fact is kept for the consultant, cleared by nothing that follows.
_Avoid_: warning (the halt it raises), retell budget, notice, Frase difícil

**Superseded**:
An attempt at telling back that was replaced by a new recording. Its findings become marked history; they never vanish.
_Avoid_: erased, discarded, Substituída

**Checked**:
The state in which the passage has been told and one whole reading of the analyst returned no finding, so it leaves the rotation for good. Spot correction checks never produce it, and thin evidence about a legible stretch does not prevent it.
_Avoid_: complete, done, Conferida

**Heard the rehearsal** (`playback_confirms_rehearsal`):
The evidence that the team listened to every current part of the rehearsal, each in its own milliseconds, before closing; a part recorded again is unheard until it is played through again.
_Avoid_: complete playback, Ouviu o ensaio

**Abandoned**:
A superseded stretch that never got a replacement, which is what starting a telling-back
over leaves behind on every stretch of a session at once.
_Avoid_: erased, discarded, cancelled, Abandonada

**Rebuild**:
A new passage take assembled around a stretch that was recorded again, which every stretch
of the recording it replaces is then re-pointed at.
_Avoid_: version, merge, recomposition, Reconstrução

### Verdict closings

**Closing**:
How the Speaker ends the verdict turn: handing the choice back to the screen, with a question, without a question because the passage is checked, asking for a spoken answer, or sending the team to record more and go back to the rehearsal.
_Avoid_: ending, other, Fechamento

### Session states

**Session**:
The work of one team on one pericope, with status in progress, done or needs a person.
_Avoid_: passage, round, Sessão

**Needs a person** (`needs_person`):
A halt, not an end: it travels beside the status, never inside it, with the kind blocking or warning.
_Avoid_: error, failure, status, Precisa de pessoa

**Halt**:
The reason the room stopped for a person: blocking or warning. A halt from before the distinction reads as blocking.
_Avoid_: blockage, lockup, Parada

**Halt kind** (`halt_kind`):
Whether a halt stops the room or only calls somebody over: blocking, or warning.
_Avoid_: severity, level, status, Tipo de parada

**Refine**:
The later product stage that receives the packet. It does not live on this server.
_Avoid_: review, refinement

### Release

**Release** (`ir_releases`):
The record that the team approved the passage as its final draft: one numbered row per approval per pericope per project, carrying the packet as approved beside its hash. An approval that changes nothing returns the release that already exists. It is refused while the telling-back carries an open finding or a part of the rehearsal is unheard, and the team's approval records the device that approved.
_Avoid_: approval (the gesture, not the record), finalization, export, snapshot, Liberação

**Version**:
The number of a release within its pericope and project, from one, never reused.
_Avoid_: revision, pass (the count of tellings of a stretch), rebuild (a new passage take), v-number

**Packet**:
The file a release hands to Refine: the rehearsal, the telling-back with its findings and history, the questions, and its own hash as a fingerprint of the content.
_Avoid_: package, artifact (the code's older name), manifest, handoff, Pacote

**Forced release** (`forced_by`, `forced_at`, `forced_open_findings`):
A **Release** a facilitator minted over an open finding or an unheard part, recorded with who forced it, when, and the findings open at that moment. The team can never force one, and no other blocker yields to the force: consent, coverage, audio, a telling-back and its reading are material, not a dispute.
_Avoid_: override, bypass, forced approval, Aprovação forçada

### Test seams

**Text seam** (`text-seam`):
A door that takes as text what the team would have spoken and runs the real Guide, Analyst, Speaker and Validator, so that Marcia's golden scripts judge the room by measurement. It exists only where the runner key is set, answers 404 without it, and never reaches a tablet.
_Avoid_: test mode, mock, stub, simulator, Entrada de texto

### Other subsystems

**Sound Necklace**:
The interview product of this server, whose answer path has had no caller since the
2026-09-01 scope cut.
_Avoid_: Necklace (the Room's bead metaphor), Colar de Sons

**Transcription**:
The first model step of the Sound Necklace answer path, which writes down what was said and
cleans nothing.
_Avoid_: STT, speech recognition, Transcrição

**Disfluency cleanup**:
The model step that takes hesitations out of a transcript, after transcription and before
the facilitator confirms it on screen.
_Avoid_: editing, polishing, correction, Limpeza

**Verbatim**:
The property of a transcript that carries what was said without cleanup, completion or
summary.
_Avoid_: literal, raw, Literal

**App** (`apps`):
One application this server serves, holding the roles that access to it is granted through.
_Avoid_: product, tenant, client, Aplicativo

**Grant**:
One person's role on one app, without which they reach nothing of it.
_Avoid_: permission, membership, access, Concessão

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
The language the team tells back in, and which the analyst reads. `bridge_mode` is the calibration state of that language.
_Avoid_: L2, Portuguese, Língua-ponte

**Stretch** (`segment`; frase, in Marcia's method and her prompts):
The persistent, addressable object of one told slice of the passage: a slice of a rehearsal take, the matching back-translation take, the transcript, the order and the pass. A correction is a new row that supersedes the previous one, never an edit.
_Avoid_: segment (in prose; it is the wire and table name), Segmento, trecho, chunk (the ephemeral position in one reading, not this object)

**Chunk**:
The numbered position of a stretch in the list the analyst receives in one reading, the frase number of the prompts. It exists only for the length of the call; the server turns the number back into a stretch.
_Avoid_: stretch (the persistent object a chunk points to), segment (that object's wire and table name)

**Pass** (`pass_number`):
How many times a stretch has been told: one on the first telling, two when told again after a finding.
_Avoid_: attempt, version, Passe

**Telling back**:
The act of saying, in the bridge language, what a stretch of the mother tongue holds. The Portuguese the room writes and speaks for it is *traduzir / tradução*; *contar* belongs to the Conversation with the Guide alone, and *recontar* to the External Check.
_Avoid_: translating (in English prose), transcribing, Contar de volta, Contado de volta, Reconto, Recontar

**Untold**:
A stretch recorded in the mother tongue that has not been told back yet. It is not a finding: it is only waiting to be told, and the analyst is not called.
_Avoid_: missing, pending, Não contado

**Rehearsal** (`ensaio`):
The recording of the whole passage in the mother tongue, and the station where it happens. It is where the team returns when something is missing beyond everything already told.
_Avoid_: recording, `ensaio` (in prose; it is the stored take kind)

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
The analyst's answer about a told stretch: a kind, a note and, when there is one, a stretch. The kinds, in Marcia's words: missing, addition, unclear.
_Avoid_: error, problem, Achado, the retired kinds meaning change, wrong relation, reordered event and preservation violation (all read as addition), insufficient evidence (retired; it is no finding)

**Missing with an address** (`missing` with `where` before or inside):
An element of the Map that is absent and whose place fits inside an existing chunk. The team records that stretch again and tells it again.
_Avoid_: internal missing, Falta com endereço

**Missing without an address** (`missing` with `where` after on the last chunk):
An element that is absent and sits after everything that was told. The stretch is null and the speech sends the team to record more and go back to the rehearsal, erasing nothing.
_Avoid_: external missing, missing null, Falta sem endereço

**Where**:
The field of a missing finding that says whether the absent content sits before, inside or after the chunk it cites.
_Avoid_: position, offset, Onde

**Points at a stretch** (`points_at_a_stretch`):
The property of a finding that puts one specific stretch on screen with the two microphones. It decides the closing of the verdict.
_Avoid_: has an address, Aponta um trecho

### Correction and verification

**Correction**:
The retaking of exactly one stretch, at the place the current finding points to, to answer it. Detected because only one position of the list changed.
_Avoid_: mend (the app's word for the same gesture), fix, retell (the count of tellings, not this gesture), Correção

**Retell**:
Each new telling of the same stretch after a finding; in the room's Portuguese, *traduzir de novo*. On the third retell the room asks for a person: a warning, never a cap.
_Avoid_: attempt, retry, Reconto, Recontar

**Superseded**:
An attempt at telling back that was replaced by a new recording. Its findings become marked history; they never vanish.
_Avoid_: erased, discarded, Substituída

**Checked**:
The state in which the passage has been told and one whole reading of the analyst returned no finding, so it leaves the rotation for good. Spot correction checks never produce it, and thin evidence about a legible stretch does not prevent it.
_Avoid_: complete, done, Conferida

**Heard the rehearsal** (`playback_confirms_rehearsal`):
The evidence that the team listened to the whole rehearsal, on the current take, before closing.
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
The later product stage that receives the back-translation artifact. It does not live on this server.
_Avoid_: review, refinement

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

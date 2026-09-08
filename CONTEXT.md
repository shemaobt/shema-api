# Internalization Room (server)

The server side of the Room: it keeps what the team records, runs the back-translation, calls the analyst to check what was told against the Meaning Map, settles every finding at an address, and decides how the verdict speech ends. The tablet app and the Desk are its clients.

## Language

### Voices and roles

**Guide**:
The persona that leads the conversation with the team throughout the session, outside the back-translation verdict.
_Avoid_: narrator, conductor, Guia

**Speaker**:
The persona that says the back-translation verdict to the team, warmer than the analyst. A single role.
_Avoid_: voice (alternative internal name), spoken narrator, TTS, Falante

**Analyst**:
The entity that reads only the told stretches and the Meaning Map, never speaks to the team, and returns findings as JSON and nothing else.
_Avoid_: checker, reviewer, classifier, Analista

**Validator**:
The entity that checks the Guide's or the Speaker's draft speech before audio synthesis and can refuse it, triggering the safety speech.
_Avoid_: analyst (it judges content, not speech), Validador

**Correction check** (`verify_correction`):
The call that checks whether a correction answered the finding, counting the elements the stretch carried, those still told, and those the new telling brought back. Resolved and broken are independent answers.
_Avoid_: analyst, validator, Verificador de correção

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
_Avoid_: window, stretch, trecho, Escopo

**Take**:
An audio file recorded by the team, of one of two kinds: rehearsal (`ensaio`, the whole passage in the mother tongue) or back-translation (`retro`, a stretch told in the bridge language).
_Avoid_: recording, audio

**Mother tongue**:
The team's language, the one the rehearsal is recorded in and that nobody on the server understands.
_Avoid_: native, L1, Língua materna

**Bridge language**:
The language the team tells back in, and which the analyst reads. `bridge_mode` is the calibration state of that language.
_Avoid_: L2, Portuguese, Língua-ponte

**Stretch** (`segment`):
The persistent, addressable object of one told slice of the passage: a slice of a rehearsal take, the matching back-translation take, the transcript, the order and the pass. A correction is a new row that supersedes the previous one, never an edit.
_Avoid_: segment (in prose; it is the wire and table name), Segmento, trecho, chunk

**Chunk**:
The numbered position of a stretch in the list the analyst receives in one reading. It exists only for the length of the call; the server turns the number back into a stretch.
_Avoid_: stretch, segment

**Pass** (`pass_number`):
How many times a stretch has been told: one on the first telling, two when told again after a finding.
_Avoid_: attempt, version, Passe

**Telling back**:
The act of saying, in the bridge language, what a stretch of the mother tongue holds.
_Avoid_: translating, transcribing, Contar de volta

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

### Findings

**Finding**:
The analyst's answer about a told stretch: a kind, a note and, when there is one, a stretch. The kinds: missing, addition, meaning change, wrong relation, reordered event, preservation violation, insufficient evidence, unclear.
_Avoid_: error, problem, Achado

**Missing with an address** (`missing` with `where` before or inside):
An element of the Map that is absent and whose place fits inside an existing chunk. The team records that stretch again and tells it again.
_Avoid_: internal missing, Falta com endereço

**Missing without an address** (`missing` with `where` after on the last chunk):
An element that is absent and sits after everything that was told. The stretch is null and the speech sends the team to record more and go back to the rehearsal, erasing nothing.
_Avoid_: external missing, missing null, Falta sem endereço

**Where**:
The field of a missing finding that says whether the absent content sits before, inside or after the chunk it cites.
_Avoid_: position, offset, Onde

**Sufficient evidence** (`evidence_sufficient`):
The distinction between "no difference appeared" and "too little was told to check". When it is false, there is always an insufficient evidence or unclear finding naming the limit.
_Avoid_: confidence, score, Evidência suficiente

**Points at a stretch**:
The property of a finding that puts one specific stretch on screen with the two microphones. It decides the closing of the verdict.
_Avoid_: has an address, Aponta um trecho

### Correction and verification

**Correction**:
The retaking of exactly one stretch, at the place the current finding points to, to answer it. Detected because only one position of the list changed.
_Avoid_: mend (the app's word for the same gesture), fix, retell (the count of tellings, not this gesture), Correção

**Retell**:
Each new telling of the same stretch after a finding. On the third retell the room asks for a person: a warning, never a cap.
_Avoid_: attempt, retry, Reconto

**Superseded**:
An attempt at telling back that was replaced by a new recording. Its findings become marked history; they never vanish.
_Avoid_: erased, discarded, Substituída

**Checked**:
The state in which the passage has been told and verified by one whole reading of the analyst and leaves the rotation for good. Spot correction checks never produce it.
_Avoid_: complete, done, Conferida

**Heard the rehearsal** (`playback_confirms_rehearsal`):
The evidence that the team listened to the whole rehearsal, on the current take, before closing.
_Avoid_: complete playback, Ouviu o ensaio

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

**Refine**:
The later product stage that receives the back-translation artifact. It does not live on this server.
_Avoid_: review, refinement

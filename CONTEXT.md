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
The synthesized voice a line is spoken with: Mariana's for every language the Room speaks, unless a deployment configures an English voice.
_Avoid_: Speaker (the persona spoken by it), narrator, Voz

**Analyst**:
The entity that reads only the told stretches and the Meaning Map, never speaks to the team, and returns findings as JSON and nothing else.
_Avoid_: checker, reviewer, classifier, Analista

**Validator**:
The entity that checks the Guide's or the Speaker's draft speech before audio synthesis and can refuse it, triggering the safety speech.
_Avoid_: analyst (it judges content, not speech), Validador

**Team** (`project`):
The group of translators that owns the work. In the schema the column is called `project_id`; the Desk and the backlog say team.
_Avoid_: project (in prose; it is the schema's word for the same entity), user, Equipe

**Desk**:
The facilitator's web app, consumer of the routes for questions, halts and sessions by team, and of a session's conversation and retroverification file.
_Avoid_: panel, dashboard, Mesa

**Consultant**:
A reader of every team's work in the Desk, who arrives after the fact to judge a passage: a platform role on the internalization-room app, not a link to a team, admitted to every read door and refused at every write (ADR 0058). A facilitator can hold it too and still acts only on the teams they facilitate.
_Avoid_: observer, auditor, read-only facilitator, Consultor

**Reader**:
Whoever may open the Desk's read doors: a facilitator or a consultant. A reader reads the teams their scope opens — a facilitator their own, a consultant every team — and reading changes nothing.
_Avoid_: viewer, observer, user (in prose), Leitor

**Nudge**:
A message on a team's stream from the server to the Desk saying that something the Desk shows changed — sessions, hands, halts, takes, stretches, verdict or release — naming what and carrying no data. The Desk reads that thing again through its routes.
_Avoid_: event, notification, push, update, Aviso (a Warning), Cutucada

**Attention** (*Atendimento*):
What waits for an action of the facilitator in one team, shown as a band on the pericope's line of that team's Desk: the halted rooms, the rooms under a warning and the halted tablets, each with its reason and since when; the team's card carries the count, hands included. A raised hand is answered in the Internalization phase, where it was raised; a finished passage waits for nobody there.
_Avoid_: inbox, queue (the server's word for the halted-rooms listing), dashboard, Pendências

**Reply** (*resposta*):
The facilitator's voice answer to a team's raised-hand question. It belongs to the team: it shows on every tablet of the team, and counts as heard for all of them once one of them played it to the end. A question that names no team is reached by no tablet.
_Avoid_: answer (in prose), heard the rehearsal (a different listening)

**Phase** (*fase*):
One of the four stretches of the team's work on a pericope as the Desk shows them, in order: Internalization (the conversation with the Guide and the necklace), Rehearsal, Telling back (said *Tradução*) and Retroverification (the verdicts, the findings, the corrections and the release). A phase is the Desk's reading of the Stations: the Conversation is the Internalization, the findings and the approval are the Retroverification.
_Avoid_: step (the tablet's substate of a station), stage, tab, Etapa

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
An audio file recorded by the team, of one of three kinds: a conversation turn's speech (what the room hears and measures against the **Mother-tongue floor**, kept with the turn), a rehearsal (`ensaio`, one **Part** of the passage in the mother tongue, or the whole passage told as one part) or a back-translation (`retro`, a stretch told in the bridge language). The newest rehearsal take under a part's number is that part; the earlier ones stay as history.
_Avoid_: recording, audio, clip, scope (a part is named by its number, and the text seam declares every part under the pericope)

**Recording time** (`recorded_at`):
When a take was recorded. A take recorded on the tablet keeps the tablet's own clock, sent with it, however late the upload lands; a joined or spliced part, and a take sent with no time, keep the server's clock at the moment it arrived. Set once when the take is stored and never moved. Takes stored before ENG-1273 carry their upload time.
_Avoid_: upload time, created_at (when the upload landed), timestamp

**Clock offset** (`device_clock_offset_ms`):
How far the tablet's clock was from the server's when it sent a joined part, in milliseconds, negative when behind. Kept only at five minutes or more; the consultant reads it as one line, the team never sees it and the packet never carries it.
_Avoid_: skew, drift

**Mother tongue**:
The team's language, the one the rehearsal is recorded in and that nobody on the server understands.
_Avoid_: native, L1, Língua materna

**Mother-tongue floor** (`internalization_room_mother_tongue_floor`):
The language-detection probability under which a take heard in the session's language counts as the mother tongue: 0.35 by default, a deployment setting, never a session's. A take in another language, or one with no words that lasts twenty seconds or more, is the mother tongue whatever the probability (ENG-1193).
_Avoid_: confidence threshold, STT_SAME_LANGUAGE_MIN_PROB (her name), uncertain

**Bridge language**:
The language the team tells back in, and which the analyst reads.
_Avoid_: L2, Portuguese, Língua-ponte

**Stretch** (`segment`; frase, in Marcia's method and her prompts):
The persistent, addressable object of one told slice of the passage: a slice of a rehearsal take, the matching back-translation take, the transcript, the order and the pass. A correction is a new row that supersedes the previous one, never an edit. A telling with no words is refused, never a stretch.
_Avoid_: segment (in prose; it is the wire and table name), Segmento, trecho, chunk (the ephemeral position in one reading, not this object)

**Chunk**:
The numbered position of a stretch in the list the analyst receives in one reading, the frase number of the prompts. The server turns the number back into a stretch, and a **Finding** keeps the number it was given beside the stretch it resolved to. The two are not one answer: a **Missing with an address** placed *after* frase N resolves to stretch N+1, so an addition and a missing element are one swap of one frase when they share the number and not when they share the stretch.
_Avoid_: stretch (the persistent object a chunk points to), segment (that object's wire and table name), chunk_index (the takes column is `ordinal`)

**Pass** (`pass_number`):
Which side of a check a stretch was told on: one before the analyst has read the telling-back, two for anything told after it, a first telling of a new stretch included.
_Avoid_: attempt, version, Passe, tellings (the count of every telling of the stretch, kept on the row)

**Telling back**:
The act of saying, in the bridge language, what a stretch of the mother tongue holds. The Portuguese the room writes and speaks for it is *traduzir / tradução*, and its English room literal says *translated*; *contar* belongs to the Conversation with the Guide alone, and *recontar* to the External Check.
_Avoid_: translating (in English prose; the room's own English literal does say translated), transcribing, Contar de volta, Contado de volta, Reconto, Recontar

**Untold**:
A stretch recorded in the mother tongue that has not been told back yet. It is not a finding: it is only waiting to be told, and the analyst is not called; *terminei* answers `FRASE_AWAITING`. A current **Part** with no standing stretch refuses nothing: the check runs with it once it has been heard, and her analyst names what is missing.
_Avoid_: missing, pending, Não contado

**Rehearsal** (`ensaio`):
The recording of the whole passage in the mother tongue, and the station where it happens. It is where the team returns when something is missing beyond everything already told.
_Avoid_: recording, `ensaio` (in prose; it is the stored take kind)

**Part**:
One rehearsal take of a passage: the unit the team listens to, tells stretches from and records again. A rehearsal told whole has one part, until the team records by scene: then the whole is history, kept but no longer a part. **The number the voice says is the part's position among the session's current parts**, never the number as stored: the tablet numbers its parts from one and the text seam from zero, and both mean the same first part. The voice adds the scene's own title only when the rehearsal has as many current parts as the passage has scenes and the catalogue holds that title in the session's language.
_Avoid_: clip (Marcia's word for it), chunk, segment, Parte

**Part key** (`key`):
The name a **Part** goes by in a file name and in what Refine receives: `whole` for the rehearsal told whole, `S<n>` for the part in position n among the session's current parts (Marcia's scene key; part n is scene n), with no cap at the passage's scene count. A superseded take keeps the key of the part it was. A pinned take in the **Packet** carries it as `key`; a frase, and a **Finding** or **Nuance** in the **Check block**, carry the key of the part they stand on as `scene`.
_Avoid_: clip key, scope (the tablet's `parte-N`), chunk_index, ordinal (the number as stored)

**Superseded take** (`superseded_takes`, `superseded_at`):
A rehearsal take that a later take under the same part's number replaced. It is kept, listed apart from the current parts, and downloads as `<release>-<key>-substituida-<take id>.<ext>`; its time is when the take that replaced it reached the server.
_Avoid_: kept take (kept names a telling kept for the team), replaced take, old take, Substituída (in prose); **Superseded** alone is a telling-back attempt

**Recording grain** (`recording_grain`):
Whether the rehearsal reaching Refine was told whole or in parts, read off the current parts' numbers.
_Avoid_: granularity, mode, shape, Granularidade

**Joined recording** (`origin`):
A rehearsal with at least one current **Part** the tablet laid in from a **Scene rehearsal**, which the part's `origin` names. On it a part no translated frase stands on refuses *terminei* as `STRETCH_UNTRANSLATED`, and the full listen of one translated through is checked once with no tap. A recording no join touched is checked exactly as any other.
_Avoid_: assembled recording (the server's old composed takes), merged, Junção (in prose)

**Canon code**:
The identifier the Meaning Map gives a being, figure, object, thread or scene (`B3`, `FIG_0013`, `PL_ISRAEL`, `S2`), alone or inside a link in double square brackets. It is never voiced: the room removes it from the text before the Voice speaks it, and the stored line keeps it.
_Avoid_: id, tag, link, slug

**Speakable text**:
The voiced text: a line as the Voice receives it, with its formatting marks and canon codes gone, each folded question standing as its own sentence and the divine name in its spoken form. Words are never added, dropped or reordered, and the stored line keeps the Guide's own form.
_Avoid_: TTS text, clean text, sanitized text

**Meaning Map**:
The canonical content of the pericope that the analyst compares against, including preservation rules and the marked silence that is never revealed.
_Avoid_: answer key, base text, Mapa de Sentido

**Necklace**, **bead** and **element**:
The necklace is the passage's coverage as the tablet draws it: her twelve beads (`beads_total`), whatever the passage's number of elements, of which `beads_filled` are lit, the elements engaged over all the elements times twelve, rounded half up. Underneath, each **element** of the Map travels through not encountered, surfaced, partially engaged and engaged. A **bead** is one of the twelve; an **element** is one of the Map's.
_Avoid_: bead for an element of the Map, progress, checklist, Colar, conta, Sound Necklace (a different product in this repository)

**Panorama**:
The overview of the book spoken before the first passage; a session records that it followed the panorama, so that the Guide does not introduce itself twice. The seven doors that record, tell back or check refuse a panorama with one code; the conversation's turns door does not, because the panorama is a conversation, and neither do the release doors. Each **Served book** has its own (`OV-Esther`, `OV-Jonah`, `OV-Ruth`), first in that book's list. `OV` and `panorama` alone still name Ruth's, for tablets that do not name a book.
_Avoid_: introduction

**Served book** (`SERVED_BOOKS`):
A book of her pinned canon that the room vendors and offers whole: Esther, Jonah and Ruth at the pin 5b5c8d2, listed in the order of their passage ids. Every published passage of a served book is offered and opens. No readiness test holds one back, and each served book has its own **Panorama** (`OV-<Book>`).
_Avoid_: walkable book, enabled book, published book (her word for what the compiler publishes, which may hold books the room does not serve)

**Prepared opening**:
The passage's first Guide line, written and voiced in the background on the Panorama before the team opens its passage.
_Avoid_: ready line, prepared line

**Hand-over**:
The move of a Prepared opening from the Panorama onto the session of the passage the team opens, once and only to the passage and language it was written for.
_Avoid_: handing off, transfer

**Book material**:
What the Panorama voice reads as its standard of truth for one book: the digest of every published passage in story order, then the **Preservation notes**. Built from the vendored canon at its pin, never written by hand.
_Avoid_: book context, overview prompt, summary

**Preservation notes**:
The union of a book's withholdings, listed under the book material's header sentence («The team has not yet lived any passage…»): what no passage may state, pair, name or attribute before its moment. A book with none reads «- (none recorded)». Ruth has 99 at the pin 5b5c8d2; Esther and Jonah have none, so their Panoramas read «- (none recorded)».
_Avoid_: do_not_decide (the canon's field name), spoilers, constraints

**Address**:
Where a stretch sits: the take it belongs to, and its start and end in milliseconds inside
that one file.
_Avoid_: range, offset, position, Endereço

**Frase number** (`frase`):
The 1-based number a stretch had in the reading the team heard, the one the voice says; frozen per **Version** beside the stretch id (`segment_id` in the packet, `idx` in the **Check block**, `stretchId` in the text seam); the number itself is `index` in the **Check block**'s findings and nuances. A cut or a fresh telling after the approval changes nothing in that version. Freezing is what a **Version** does to the number, not a property of the number itself: where no version exists — the verdict, as the round is being decided — it is the stretch's position in the reading the analyst was just given, which is the one the team just heard. The entry names the concept and the spellings it carries on the wire; the word a team hears for it follows the session's language (*frase* in Portuguese, *sentence* in English). The tablet reads it from the room and never counts: `frase` on every stretch of the session read and of the answers of a cut, a replacement and a restart, and on the telling answer for the stretch just told, is its position among the told stretches now, null on a piece nobody has told (ADR 0067). A **Finding** keeps the number the voice spoke, and the session read and the check's answer serve it as the stretch it named is numbered now, null once that stretch is no longer told (ENG-1681).
_Avoid_: ordinal (per sibling group, never per passage), position, index (in prose; `index` is only the **Check block**'s wire key), n (her listener number), Número da frase

**Divided stretch** (`parent_id`, `ordinal`):
A stretch cut out of another one, numbered among its own siblings rather than among the
session's stretches.
_Avoid_: child, split, subsegment, Trecho dividido

**Element kind**:
What an element of the Meaning Map is. Six kinds sit in a scene of the passage — scene, being, place, object, time, absence; a preserved rule and the four Level-1 axes — arc, context, tone, function — belong to the passage and to none of its scenes.
_Avoid_: type, category, Tipo de elemento

**Scene pointer** (`current_scene_id`):
The scene the ledger last places the team in: the first scene whose elements are not all engaged, once the team has spoken, and none at all before that. It is information — a turn's record keeps it; the Guide's ledger block stopped carrying it in ENG-1358, as her live ledger never prints it — and never a scope on what a turn may move.
_Avoid_: current scene (the retired heading of the ledger's scene line, which the ledger no longer prints; the term is the pointer), eligibility, scope, progress, Ponteiro de cena

**Coverage event** (`ir_coverage_events`):
One recorded movement of an element from one coverage state to the next.
_Avoid_: log, history, audit, Evento de cobertura

### Findings

**Finding**:
The analyst's answer about a told stretch: a kind, a note, the **Chunk** it named and, when there is one, a stretch. The kinds, in Marcia's words: missing, addition, unclear. An addition or an unclear always names its **Chunk**; one that names none, or names one outside this reading, is not raised — it is dropped with a log line, the way the retired kind is, and a reply left with no finding at all once every one of them is dropped this way is refused, not read as a clean telling-back.
_Avoid_: error, problem, Achado, the retired kinds meaning change, wrong relation, reordered event and preservation violation (all read as addition), insufficient evidence (retired; it is no finding)

**Nuance** (`nuances`):
A detail the analyst found in a told frase that the story tells another way, and that never blocks. It is never a **Finding**: it is never counted open, and a check whose only findings are nuances is **Checked**. The voice names one at a time, at most once. Each **Check round** keeps the nuances it stood on, with `voiced`: `now` when that round's verdict named it, `before` when an earlier round had, absent when no verdict has. The **Check block** carries the nuances standing at the approval as kind and address with `voiced`, never the quote, the story or the note; the **Retroverification file** keeps the quote and the story.
_Avoid_: detail, soft finding, nuança (in prose)

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
An addition and a missing element the analyst reported on the same **Chunk**: the telling put one relation in and dropped the one the story tells in its place. One thing for the team — one thing said, one stretch recorded again — and never two. Both halves must point at a stretch, so a **Missing without an address** is never half of one. The addition leads it, whichever half the analyst listed first.
_Avoid_: pair (it says there are two things), swapped relation (Marcia's phrase for the mistake, not for what the room carries), troca

**Priority**:
The order in which the room raises one reading's findings: an addition that fills a marked silence, then any other addition, then a missing element, then an unclear frase. A **Swap** ranks by its addition, and within one tier the analyst's order holds. The stored list is never reordered; only the pick is.
_Avoid_: severity, ranking, sorting (the stored list keeps the analyst's order), Prioridade

**Filled silence** (`fills_silence`):
An addition the analyst reported under the wire kind `silence`: the telling says something the passage keeps quiet on purpose. It stays an addition for the app, the packet, the golden scripts and the Speaker, and decides only the **Priority**.
_Avoid_: fourth kind, silence kind (the wire name only), Silêncio preenchido

**Points at a stretch** (`points_at_a_stretch`):
The property of a finding that puts one specific stretch on screen with the two microphones. It decides the closing of the verdict.
_Avoid_: has an address, Aponta um trecho

### Correction and verification

**Correction**:
The retelling of exactly one stretch, in the bridge language and over the recording it already sits in, at the place the current finding points to. Detected because only one position of the list changed; it always carries audio, and no rule counts how many a stretch may have.
_Avoid_: mend (the app's word for the same gesture), fix, retell (the count of tellings, not this gesture), Correção, mother-tongue correction (retired: a recording error is answered by recording the **Part** again), rebuild (retired: the passage the server assembled around a correction)

**Retell**:
Each new telling of the same stretch after a finding; in the room's Portuguese, *traduzir de novo*. The third telling of a stretch makes it a hard stretch: a warning, never a cap.
_Avoid_: attempt, retry, Reconto, Recontar

**Idempotency key** (`Idempotency-Key`):
The tablet's one name for one telling sent to the chunk door, or for one **Correction**, carried unchanged on every resend of it. A resend under the same key is answered with the answer the first one settled and is never counted again; a key is forgotten after a day.
_Avoid_: request id, retry token, turn id (a turn's own name, not this)

**Hard stretch**:
A stretch the team told three times. The room asks for a person once when it happens, and the fact is kept for the consultant, cleared by nothing that follows.
_Avoid_: warning (the halt it raises), retell budget, notice, Frase difícil

**Superseded**:
An attempt at telling back that was replaced by a new recording. Its findings become marked history; they never vanish.
_Avoid_: erased, discarded, Substituída

**Checked**:
The state in which the passage has been told, one whole reading of the analyst returned no finding, and the verdict spoken on it was validated, so it leaves the rotation for good. A verdict that fell to a fail-safe line confers nothing, however clean the reading. Thin evidence about a legible stretch does not prevent it. A reply that named findings and lost every one to an unreadable **Chunk** is not a reading that returned no finding: it is refused, and confers nothing.
_Avoid_: complete, done, Conferida (in prose; `conferida` is the wire spelling in the **Check block** and the text seam)

**Check round** (`checks`):
One reading of the telling-back and the verdict spoken on it, kept in the passage's history with its time, its findings with the analyst's notes, the words spoken, the outcome and whether it conferred. Rounds are unlimited, and a later round never overwrites an earlier one.
_Avoid_: attempt (a **Superseded** recording), Rodada

**Heard the rehearsal** (`unheard_parts`):
The evidence that the team listened to every current part of the rehearsal, each in its own milliseconds and per take, before closing. Played stretches 0.25 s or less apart count as one; a part, and a sentence laid into one, is heard when what is left unplayed adds up to at most 0.75 s and never more than half of it. It is an absolute allowance, never a percentage. Listening reports add up per take, so a later report never takes away a part an earlier one heard; a part recorded again is a new take and unheard until it is played (ADR 0017, ADR 0069, ADR 0074).
_Avoid_: complete playback, Ouviu o ensaio, coverage with tolerance

**Unheard part** (`unheard_take_ids`):
A current **Part** of the rehearsal the team's listening reports do not cover under the rule of **Heard the rehearsal**, named by its take in the refusal the check answers with before the analyst runs, and on every answer of the listen door. A part recorded again is unheard until it is played; a part with a sentence laid in, until that sentence is.
_Avoid_: unplayed clip, untold stretch (a stretch never told; this is a part never heard), Parte não ouvida

**Abandoned**:
A superseded stretch that never got a replacement: what recording a **Part** again leaves
behind on that part's stretches, and what «recomeçar a tradução» on a session told back
(`/back-translation/restart`) leaves behind on every current stretch, while the findings and kept
check rounds are archived with the attempt it ends.
_Avoid_: erased, discarded, cancelled, Abandonada, restart (a **Scene rehearsal**'s, not this)

### Verdict closings

**Closing**:
How the Speaker ends the verdict turn: handing the choice back to the screen, with a question, inviting the last listening and the approval because the passage is checked, asking for a spoken answer, or sending the team to record more and go back to the rehearsal.
_Avoid_: ending, other, Fechamento

### Session states

**Session** (*sessão*):
The work of one team on one pericope in one language, with status in progress, done or needs a
person. A session nobody entered — no turn, no take and no halt — is not yet a room of the team:
the Desk's column and the team's last activity ignore it. The Desk uses the same word.
_Avoid_: passage, round, visit, visita, attempt

**Approved passage** (*passagem aprovada*):
A passage of a team that has a release. The count the Desk shows a team is of approved passages; a finished session without a release approves nothing.
_Avoid_: closed passage (a session done, which may hold no release), fechada, complete

**Draft** (*rascunho*):
The team's recording of a passage with its frases and telling-back, kept across openings: the live **Session** of that pericope and language holds it, and an approval leaves it open under its version until a new or dropped take un-approves it (ADR 0071). A Zerar archives it, and the next opening starts a new one.
_Avoid_: rascunho final (the approved version's words on the screen), release (the record of an approval), session (what holds the draft, not the draft)

**Inactive team** (*equipe inativa*):
A team with no activity for 21 days, the «Inativas» of the Desk's team list. Inactive means the work stopped, not that the team is quiet: a team that closed every passage of the book is never inactive, however long ago it finished, and neither is a team that has never met. Not a halt: an inactive team's room is not stopped, and a halted room's team is not inactive.
_Avoid_: stalled, parada, idle, dormant

**Opening a session**:
A tablet asking the room for its team's session of a pericope and language: the latest live one is returned whatever its state, and one is created only when none exists. An archived session is never returned.
_Avoid_: creating a session, starting a session, Abrir a passagem

**Opening** (the session's first line):
The Guide's first line of a session, spoken before the team has said anything, drafted once whatever number of tablets ask for it. Not to be confused with **Opening a session**, the open door.
_Avoid_: kickoff, abertura, first turn

**Opened** (`opened`):
A session that holds a Guide line, its **Opening** at least. A room note or a team entry alone does not open it. The session state says so, and every reader on the server, the turn door, the Opening's wait and its write, asks this same question; the tablet asks a session's Opening only while it is not opened. Not to be confused with **Opening a session**, the open door.
_Avoid_: started, begun, aberta

**Turn claim** (`opening_claim_turn_id`, `opening_claimed_at`, `claimed_for_the_opening`; the first two keep the opening's names):
The mark on a session that one request is answering a turn of it, naming the turn id its answer will be stored under. Every turn that writes the conversation takes it, whether the **Opening**, a **Team turn** or a scene rehearsal's «terminei»; asking for the last line again takes none. A team turn or a «terminei» that finds it held waits for that answer and runs after it. One still waiting 90 s after the claim is refused `TURN_COLLISION`, with nothing stored and nothing voiced, unless what it waits on is the **Opening**: then it runs on the conversation as it stands. Another request for the opening answers with the holder's, and the same turn id sent again joins the answer stored under it. A claim older than the turn bound plus thirty seconds, or whose answer is already stored, counts as none (ADR 0053, ADR 0079).
_Avoid_: lease, lock, kickoff lease, opening claim

**Team turn**:
A turn that carries the team's recording: what they said goes in, the Guide's next line comes out. A team turn sent while another turn of the session is being answered waits for it (the **Turn claim**).
_Avoid_: audio turn, retell turn

**Attempt**:
One draft of the Guide's or the Speaker's on a turn and what the Validator did with it: its verdict, its issues, the correction when it mended the draft, and the attempt note when something went wrong. A turn keeps every attempt, oldest first. Not a Session.
_Avoid_: try, round, redraft (the count of drafts after the first), Tentativa

**Attempt note**:
What the room itself says about an attempt when something in it went wrong: the Validator's reply could not be read. Written by the room, never by the Validator, and absent on an ordinary attempt. Not a **Room note**, which is handed to the Guide.
_Avoid_: Validator's note, comment, Nota da tentativa

**Closed passage**:
A session whose passage was closed: done, with its end stamped. It never blocks again, though a warning may still stand on it.
_Avoid_: finished session, ended room, Passagem fechada

**Zerar**:
The facilitator's act of giving a team a clean pericope: it creates an **Archive** and the team's next open mints a new session. Marcia's word; the door is `archive`.
_Avoid_: reset, zero, clear, wipe

**Archive** (`ir_archives`, `archive_id`):
What Zerar leaves behind: one row per reset of a pericope, every language at once, and a stamp on every row of that pericope's work, its **Scene rehearsals**, their frases and their **Restarts** included. The team's doors answer an archived session as gone, and the doors that pick or list a team's work leave archived rows out, while the facilitator still reads an archived session by its id. No release is minted on an archived session, by the team or by a facilitator's force. Nothing moves and nothing is deleted; the raised-hand questions are never stamped (ADRs 0047 and 0052). A resend under a turn id the session already answered replays that answer even on an archived session, because the replay is read before the session is resolved (ADR 0043); a new turn or a look at a turn is refused.
_Avoid_: soft delete, trash, backup, Arquivo

**Needs a person** (`needs_person`):
A blocking halt, not an end: it travels beside the status, never inside it. It is lifted only by the team's own return: a turn that lands, or a tablet opening the session.
_Avoid_: error, failure, status, Precisa de pessoa

**Halt**:
The reason the room stopped for a person: blocking or warning. A halt from before the distinction reads as blocking.
_Avoid_: blockage, lockup, Parada

**Halt kind** (`halt_kind`):
Whether a halt stops the room or only calls somebody over: blocking, or warning.
_Avoid_: severity, level, status, Tipo de parada

**Halt reason** (`halt_reason`):
Why the room asked for a person, in one of five families the tablet names when it asks: the device was refused, the server kept failing, the sound or the recorder failed, the session was lost, or the room and the server disagree. A warning's reason is the hard stretch. A halt that names none reads as "the room stopped".
_Avoid_: cause, error, message, detail, Motivo da parada

**Warning**:
The halt kind that only calls somebody over: the session goes on while it stands, a landing turn never ends it, and only a Visit does. The telling-back answers still name the moment one is raised `needs_person`, the older wire name.
_Avoid_: needs a person, notice, alert, Aviso

**Visit** (`attended_at`):
A facilitator's mark on the Desk that somebody went to a room. It is a record: it writes nothing on the session's status and lifts no blocking halt. A halted room with a visit leaves the queue, and undoing the visit puts it back. It is the only end of a Warning. A new halt clears it.
_Avoid_: attend lifts, resolve, Atendido

**Station**:
The stop of the room a session is in, derived at read time for the Desk from what the session holds — conversation, rehearsal, telling back, findings, approved — never stored and never sent by the tablet. A session the team left keeps the station it stopped in.
_Avoid_: stage, phase, status (the session's own three states), Estação

**Conversation**:
The Internalization's lines between the team and the Guide, as the Desk reads them: ordered turns of the team, the Guide and the room's own notes, each with its moment and, when the Guide gave way to a fixed line, the fail-safe's category.
_Avoid_: transcript, chat, history

**Turns** (of a session):
The Conversation read as pairs, oldest first: the team's side (how the take was heard, whether it cut the voice off, and what the Guide received of it) and the voice's side (how containment ended, the attempts, the times, the model, the line voiced and its clip). The opening has no team side; the telling-back round is not part of it.
_Avoid_: transcript, timeline, Transcrição ao vivo

**Boundary turn**:
A voice turn that fell to a fail-safe, or that, past the opening, hands the question to the team's own facilitator or says the passage does not tell. Derived when the turns are read, never stored.
_Avoid_: fronteira, edge turn

**Refine**:
The later product stage that receives the packet. It does not live on this server.
_Avoid_: review, refinement

### Release

**Release** (`ir_releases`):
The record that the team approved the passage as its final draft: one numbered row per approval per pericope per project, carrying the packet as approved beside its hash. The packet names it `internalize-<slug of the mother tongue>-<pericope>-v<version>` (ADR 0048), a name two teams can share; the row's own id stays a uuid. An approval that changes nothing returns the release that already exists. The team's approval is refused while any **Blocker** stands, an open finding or an unheard part among them, and records the device that approved; a facilitator's **Forced release** passes them.
_Avoid_: approval (the gesture, not the record), finalization, export, snapshot, Liberação

**Version**:
The number of a release within its pericope and project, from one, never reused.
_Avoid_: revision, pass (the count of tellings of a stretch), v-number

**Packet**:
The file a release hands to Refine: the rehearsal, the telling-back with its findings and history, the questions, and its own hash as a fingerprint of the content. Beside the hash, and outside it, it states the team's mother tongue, the language the room spoke to it and whether every rehearsal part is WAV. Its findings travel as a kind and an address, never the analyst's note, which lives in the **Retroverification file** alone. Its frases and pinned takes name their **Part key**.
_Avoid_: package, artifact (the code's older name), manifest, handoff, Pacote

**Blocker**:
One of the codes a refused approval names, one string each: the gate's eight plus `no_project` (the conversation's coverage floor is a fact of the ledger, never a blocker). A blocker says which hole stands; the room's answer at *terminei* and the tablet's doors say where to go.
_Avoid_: reason, error code, bloqueio, refusal (the answer that carries them)

**Forced release** (`forced_by`, `forced_at`, `forced_open_findings`, `forced_blockers`):
A **Release** a facilitator minted past the gate, addressed to the passage: every **Blocker** yields to the force but a passage with no rehearsal take, and the row records who forced it, when, the findings open at that moment and the blockers it passed (ADR 0075). The team can never force one. Its **Check block** reads `forcada` when the check was not clean, and `conferida` with `forced` true when only the listening was passed over.
_Avoid_: override, bypass, forced approval, Aprovação forçada

**Check block** (`check`):
The summary of a **Release**'s check that the **Packet** carries beside its **Version**, outside its hash and in Marcia's names: whether the check happened (`conferida`, `forcada`, `sem_conferencia`), whether every part was heard, when the verdict was reached, the open findings as kind and address with the frase's `index` and its **Part key**, the **Nuances** standing at the approval with whether the voice said them, and where the retroverification file is. Beside `forced`, and in our names rather than hers, a **Forced release** says who forced it (`forcedBy`), when (`forcedAt`) and the blockers it passed (`forcedBlockers`), each null when nobody forced. Never the analyst's note.
_Avoid_: check state, manifest check, conferência

**Retroverification file** (`retroverificacao`):
The facilitator's and the consultant's record of everything the check learned about a session: every release and who forced it, the stretches with their frozen numbers, every telling including the superseded ones, the findings with the analyst's notes, the listening report, the hard stretches and a link to every take. Served only to a facilitator of that team or a consultant; the analyst's note lives here and nowhere else.
_Avoid_: export (banned for a release too), dossier (Marcia's other artifact), consultant's file, retroverificacao.json in prose

### Process lines

**Process line**:
One of Marcia's fixed lines for a step of the telling-back (P: start, tell, unheard, approved) or of the external check (X: open, retell, whole, frases, thanks), copied verbatim from her file, read by position in the session language and never rotated. It is not a fail-safe: a fail-safe answers a failure and rotates, a process line marks a step and is always the same one. No model sits on its path.
_Avoid_: fail-safe (A to I), prompt, canned line, Linha de processo

### Test seams

**Text seam** (`text-seam`):
A door that takes as text what the team would have spoken and runs the real Guide, Analyst, Speaker and Validator, so that Marcia's golden scripts judge the room by measurement. Its conversation doors are her **Golden doors**; what remains under this name is the back-translation's. It exists only where the runner key is set, answers 404 without it, and never reaches a tablet.
_Avoid_: test mode, mock, stub, simulator, Entrada de texto

**Golden doors** (`/golden/session`, `/golden/turn`):
The two doors Marcia's own runner calls, opening a session and playing a turn, with her field names and her meaning, so that her runner judges our room unchanged. They read the runner key as a bearer credential, never refuse a field they do not know, and answer 404 while the key is unset.
_Avoid_: text seam (for these two doors), golden API, test endpoints

**Golden script**:
One of Marcia's JSON scripts under her `golden/`: a declared draft of clips and the rounds of
frases told back over it, with what each round is expected to produce. A runner plays one
against a stack and judges it with her own checks. Read verbatim, never forked.
_Avoid_: fixture, scenario, test case, roteiro

**Room note**:
A fact about the room the app hands the Guide in place of the team's words, bracketed and in the session's language: the session has just started, the team spoke in the mother tongue for about so many seconds, the team cut the Guide's previous reply short, or the team rehearsed a scene and translated it frase by frase. Never words the team said: in a **Rehearsal turn** their words follow it.
_Avoid_: system message, prompt, instruction, Nota da sala

**Earlier passages**:
This team's status on each earlier passage of the book (approved, started, or not worked yet), stamped when the session is created and read again after a turn once it is five minutes old, kept on the session and handed to the Guide as a fact, complete or not at all.
_Avoid_: history, progress, story so far (the digests of those passages, not the team's status on them), Passagens anteriores

**Scene rehearsals**:
The scenes whose recorded and translated scene rehearsal has reached the Guide as of a turn, the whole list each time; an empty list is the fact that none has. Counted from each **Rehearsal turn**'s scene label as it stood at sending: a rehearsal sent with no label, with one the passage lacks, or labelled only after sending counts for no scene.
_Avoid_: rehearsal (the whole passage's recording), practised scenes, Ensaios de cena

**Scene rehearsal** (`ir_scene_rehearsals`; ensaio da cena):
One scene recorded whole in the mother tongue, with its record: the recording as sent, its **Scene frases**, when it was sent and the turn that answered it, the team's scene label and whether it was said at the recording or later, a label the passage lacks kept apart as the team sent it, and the classifier's guess kept apart from that label. Numbered per session, listed per passage, frozen once sent but for its scene label, never heard by the recognizer or the voice.
_Avoid_: Part (a take of the whole passage), take, scene take, Ensaio

**Rehearsal turn** («terminei»):
The turn a sent **Scene rehearsal** makes: the **Room note** on it, then the words of its live **Scene frases** in recording order, handed to the Guide with no recording and no recognizer. The scene label is kept on the record as it stood at sending and reaches the Guide only as a scene id in **Scene rehearsals**.
_Avoid_: checking turn, Team turn

**Scene frase** (`ir_scene_frases`):
One piece of a **Scene rehearsal** told in the bridge language, with its place in the scene recording. A replaced frase stays, marked by the one that replaced it; a frase with no words is refused and is no frase, and so is a frase whose span strictly overlaps a current frase of its attempt unless it replaces that frase (touching edges stand).
_Avoid_: Stretch (a slice of a rehearsal take of the passage), chunk, segment

**Moved pause**:
A **Scene frase** that replaces the last frase of its attempt from the same start to a new end. It is refused when the frase it names is not that last frase, when it starts elsewhere or would be shorter than 0.2 s, when its new end passes the scene recording, or when the frase was replaced since the tablet read it. A frase over the place of the newest version of the frase it names is that frase translated again, never a moved pause.
_Avoid_: move-end, cut, split, resize

**Restart** (`ir_scene_restarts`; «recomeçar a tradução»):
A numbered mark beside a **Scene rehearsal** that sets its frases so far aside, keeping a copy of the record as it was. The rehearsal then has no current frases; a frase recorded before it and sent after it is set aside with the rest. Nothing is deleted.
_Avoid_: reset, Zerar (the facilitator's, over the whole pericope), Recomeço

**Runner key** (`internalization_room_runner_key`, header `X-Access-Code`):
The secret that opens the **Text seam**. Empty in production, where the seam answers 404 to
every door behind it.
_Avoid_: api key, token, password, Chave do runner

### Build

**Claim code**:
The code the server mints for one tablet before it belongs to any team; a facilitator spends it once from the Desk to link that tablet to a team. The doors that mint it, tell the tablet it was spent and hand over the credential open to anyone, because the code is only worth what a facilitator spends on it, or the demo page while a **Demo team** is configured.
_Avoid_: código, pairing code, device code, credential

**Demo team** (`is_demo_team`):
The team a store reviewer's tablet joins through the demo page, so a reviewer alone reaches a passage. Configuration names it by its team id, never by its name, and opens the page; the first time the page serves it, the team is marked for good. A marked team never calls a person (the server stamps a visit on its halts at once, and again when a facilitator undoes one, so none reaches the queue) and never releases to Refine, with or without the configuration.
_Avoid_: test team, sandbox, reviewer team, equipe demo

**Device credential** (`X-Device-Credential`):
The token one tablet collects once after its claim code was spent and sends on every request to the room; the server keeps only its hash and compares it on every request, so unlinking the tablet from the Desk locks it out at its next request. It is the only thing that opens a team door.
_Avoid_: room key, api key, token, session

**Build**:
The image a deploy runs, named by its git SHA (the build id); answered at `/api/version`.
_Avoid_: version (a pericope's release), revision

**Minimum build** (`minimum_app`):
The oldest app build (the app's Store build) the room accepts, per platform: the iOS build number and the Android version code, the `+N` of `pubspec.yaml` (one number on both platforms, ADR 0110 of the app), served on `/api/version` as `minimum_app: {ios, android}`. 0 means no minimum. It is raised by hand, in the production deploy file, at a release. A tablet whose own build number is below it shows the app's Update screen. A build that carries no number (0, a laptop build) is never below it.
_Avoid_: minimum version (the `x.y.z` is not compared), app version, forced update

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

**Pending object** (`pending_blob_name`):
The Oral Collector object name handed out for an upload of a recording that confirm-upload
has not yet accepted.
_Avoid_: staged blob, temporary upload, draft audio

**App** (`apps`):
One application this server serves, holding the roles that access to it is granted through.
_Avoid_: product, tenant, client, Aplicativo

**Grant**:
One person's role on one app, without which they reach nothing of it.
_Avoid_: permission, membership, access, Concessão

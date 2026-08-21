from pydantic import BaseModel, Field

MAX_TTS_CHARS = 3000


class FacilitatorSpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TTS_CHARS)


class FacilitatorSpeakResponse(BaseModel):
    audio_base64: str
    mime_type: str = "audio/mpeg"
    etag: str
    cached: bool = False


class CoverageView(BaseModel):
    engaged: int
    surfaced: int
    total: int
    absence_index: int


class CreateSessionRequest(BaseModel):
    pericope: str | None = Field(default=None, max_length=120)
    after_panorama: bool = False
    #: Which panorama session preceded this one, so its prepared opening can be handed over.
    after_session: str | None = Field(default=None, max_length=36)


class BackTranslationProgress(BaseModel):
    """Where a telling-back stopped, so a tablet can be handed it back.

    The app keeps none of this across a restart — `session_id` lives only in memory — so a
    team that left a passage part-way lost the whole retro. Everything here is already
    stored on the session; it simply had no way out.
    """

    scope: str = ""
    #: One entry per stretch already told, in order, with the pass it was told on. The app
    #: draws one bead per entry.
    passes: list[int] = Field(default_factory=list)
    #: Where each stretch sits in the rehearsal, so the room can play one back.
    spans: list[list[int]] = Field(default_factory=list)
    retells: int = 0
    checked: bool = False
    finding_chunk: int | None = None
    finding_kind: str | None = None


class SessionStateResponse(BaseModel):
    session_id: str
    pericope: str
    status: str
    coverage: CoverageView
    done: bool
    back_translation: BackTranslationProgress = Field(default_factory=BackTranslationProgress)


class TurnResponse(BaseModel):
    session_id: str
    #: Where to fetch the one line the team hears this turn, empty when `fixed_line`
    #: names it instead. One voice, never a list — a turn that could carry several clips
    #: is a turn someone would eventually splice, and spliced speech is audibly sewn.
    audio_url: str = ""
    #: A pre-approved line the app already holds as audio. Never set together with a url.
    fixed_line: str = ""
    mime_type: str = "audio/mpeg"
    transcript: str
    peer_cue: bool = False
    used_fail_safe: bool = False
    coverage: CoverageView
    done: bool


class PassageView(BaseModel):
    pericope: str
    #: Where to fetch the line that names this passage aloud. There is no text field: the
    #: team does not read, so a passage the room cannot say is a passage it cannot offer.
    audio_url: str


class BookPassagesResponse(BaseModel):
    book: str
    passages: list[PassageView]


class BackTranslationChunkResponse(BaseModel):
    session_id: str
    chunks: int
    captured: bool
    #: 1 for the first telling of a stretch, 2 when it was told again after a finding. The
    #: evidence packet that travels to Refine carries pass-1/pass-2 labels, and the app has
    #: no business deciding which one a chunk is.
    pass_number: int = 1
    #: True when the retells ran out. The room stops instead of buying another round.
    needs_person: bool = False


class BackTranslationVerdictResponse(BaseModel):
    session_id: str
    audio_url: str = ""
    fixed_line: str = ""
    mime_type: str = "audio/mpeg"
    checked: bool
    finding_kind: str | None = None
    #: Which told-back piece the finding lands on, so the room can take the team straight to
    #: that stretch of their recording instead of starting the whole passage over.
    finding_chunk: int | None = None
    findings_remaining: int = 0
    used_fail_safe: bool = False


class BackTranslationRestartResponse(BaseModel):
    session_id: str
    chunks: int
    needs_person: bool


class NeedsPersonResponse(BaseModel):
    session_id: str
    needs_person: bool


class QuestionRaisedResponse(BaseModel):
    question_id: str
    status: str


class HandReplyView(BaseModel):
    """One answer waiting for the team, addressed by the audio route rather than inlined."""

    question_id: str
    audio_url: str
    pericope: str


class HandRepliesResponse(BaseModel):
    replies: list[HandReplyView]


class InboxQuestionView(BaseModel):
    """One card of the facilitator's inbox.

    ``status`` is on the card because the page carries all three states at once and the
    reader has to be able to tell the queue from the record. ``team_id`` is on it because the
    inbox can be read across teams, and a question that does not say whose it is puts the
    facilitator's next move back on them.

    ``team_id`` is not nullable even though the column is. Every shape the inbox restriction
    takes — ``= team_id``, ``IN (ids)``, ``IS NOT NULL`` — drops a row that names no team, so
    a card that reaches this response always has one. Typing it nullable would ask the Desk
    to draw a case this route cannot produce.

    ``element_key``, ``duration_ms`` and ``transcript`` are all nullable, and the Desk has to
    draw a card without each of them. An element is missing on every question raised before
    ENG-456 ships the app's half; a duration or a transcript is missing when the machine that
    produces it failed, and the card still carries audio a facilitator can answer by playing.

    **``transcript`` appears on this response and on no response the room app can read.**
    Transcribing the team's voice *for the team* is out of scope for v1; this is the
    facilitator's reading of a question, and it stays on their side of the wall. That is held
    by `tests/test_ir_transcript_stays_with_the_facilitator.py`, over the set of room routes
    rather than over any one of them.
    """

    question_id: str
    team_id: str
    device_id: str
    pericope: str
    element_key: str | None
    status: str
    audio_url: str
    duration_ms: int | None
    transcript: str | None
    asked_at: str


class QuestionInboxResponse(BaseModel):
    """A page, the count it was cut out of, and where to resume.

    ``open_total`` counts the open hands in the scope that was asked about — not the ones on
    this page, and not what the ``status`` filter let through. **It is allowed to be larger
    than ``questions``, and when the two disagree the count is the true one.** That is the
    point of serving it: a client that counts the array it received reads one number inside
    the Desk and a larger one on the team list, and nothing about either looks broken.

    ``next_cursor`` is null on the last page. It is opaque on purpose — it stands for a place
    in this route's order, and a caller that took it apart would be depending on that order
    never changing.
    """

    questions: list[InboxQuestionView]
    open_total: int
    next_cursor: str | None


class TakeResponse(BaseModel):
    take_id: str
    session_id: str
    kind: str
    scope: str
    sha256: str
    size_bytes: int
    verified: bool = False
    #: Which stretch of the telling-back this is, and which pass over it. Both are stored
    #: on the row and neither was exposed, so a reviewer opening a session saw N
    #: indistinguishable `retro` takes: no way to tell stretch three from stretch seven,
    #: and no way to tell a first telling from its correction. The labels are what travels
    #: to Refine.
    chunk_index: int | None = None
    pass_number: int | None = None
    pericope: str = ""
    recorded_at: str = ""


class TakesResponse(BaseModel):
    session_id: str
    takes: list[TakeResponse]


class QuestionAudioResponse(BaseModel):
    """Where a facilitator's browser can fetch a question's recording, and for how long.

    The address is a signed URL that authenticates itself, which is what lets an
    ``<audio>`` element — an element that sends no headers — reach the bytes at all. It is
    returned rather than redirected to, because the redirect happened after a gate the
    element could not pass.

    ``expires_at`` is here so the Desk can ask for a fresh address instead of finding out
    with a play that does nothing, which on that screen is indistinguishable from a
    recording that was never made.
    """

    url: str
    #: ISO-8601 with an offset, like every other instant this module serves. A bare local
    #: time here would be a promise nobody can compare against their own clock.
    expires_at: str

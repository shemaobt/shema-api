from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.core.room_enums import CoverageStatus, ElementKind

MAX_TTS_CHARS = 3000


class FacilitatorSpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TTS_CHARS)


class FacilitatorSpeakResponse(BaseModel):
    audio_base64: str
    mime_type: str = "audio/mpeg"
    etag: str
    cached: bool = False


class LabelledElement(BaseModel):
    """One bead, named in each language the Desk offers.

    `key` is unique only within its pericope: `scene:1` is a different scene in every
    passage, so a label is identified by `(pericope_num, key)` and never by `key` alone.

    The three languages are named fields because that is the shape the Desk was promised, so
    a fourth costs a field here as well as a catalogue entry — three files, not every call
    site. `extra="forbid"` is what makes that cost visible: the loader builds this by
    spreading `LANGUAGES`, and pydantic drops an unknown keyword by default, so without it a
    fourth language would be demanded of the catalogue and then thrown away in silence.

    **`label_pt` and `label_es` are nullable and `label_en` is not**, which is the shape that
    promise actually names: the Desk's own `CoverageLabels` is
    `{ pt: string | null, en: string, es: string | null }`, because English comes almost free
    from the canon and the other two are translation work. This model cited that promise and
    contradicted its text, and nobody had noticed because the four translated passages are
    complete in all three. The canon serves fourteen and D-03 walks every team through them.
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    kind: ElementKind
    scene: int | None = None
    label_pt: str | None
    label_en: str
    label_es: str | None


class CoverageLegend(BaseModel):
    """The names of the coverage states and the element kinds, once per response.

    Each entry maps a language code to the text. Unlike `LabelledElement` above, whose three
    fields the Desk was promised by name, nothing was promised about this shape — so here a
    fourth language is a catalogue change and nothing else.
    """

    model_config = ConfigDict(extra="forbid")

    coverage_status: dict[str, dict[str, str]]
    element_kind: dict[str, dict[str, str]]


class LegendName(BaseModel):
    """One value of a closed set, named for a facilitator rather than for the database.

    `value` is the enum's string and is typed `str` rather than `CoverageStatus` or
    `ElementKind`. A legend **is** the closed set, written out — so unlike a field that
    carries one value out of a set the response never shows, there is nothing here the schema
    has to promise that the body does not already say. And `legend()` resolves every entry by
    walking the enum, so an enum type would re-refuse what is true by construction: it can
    only reject what the loader has just accepted.

    **The three labels are not nullable, and `LabelledElement`'s are** — the two shapes
    disagree on purpose. A bead of a passage nobody has translated falls back to the canon,
    which is English and nothing else, so `label_pt` there is legitimately absent. A legend
    has no such fallback: `legend()` raises `ElementLabelsBroken` on a name missing in any
    language, so a null cannot arrive here, and typing one would invite a screen to draw the
    hole instead of the deploy failing loudly.
    """

    model_config = ConfigDict(extra="forbid")

    value: str
    label_pt: str
    label_en: str
    label_es: str


class CoverageLegendResponse(BaseModel):
    """The coverage states and the element kinds, named once for the whole Desk.

    A list and not a map, because a legend is read in order: `not_encountered → surfaced →
    engaged` is the way a bead travels, and the kinds are the canon's own grouping. The order
    is the enums' declaration order, which `legend()` already walks — serving a map would
    hand the client an arrangement to make a second time, and ENG-462 is the record of what
    that costs.

    The three languages are named fields rather than a map keyed by language, because that is
    the shape a bead already takes: `LabelledElement`, above, carries `label_pt` / `label_en`
    / `label_es`. A legend entry read as `entry["pt"]` beside a bead read as `label_pt` would
    be two shapes for one thing on one screen. `CoverageLegend` — the loader's own answer —
    keeps the map, because that is the catalogue's shape and a fourth language there costs a
    catalogue entry and nothing else.

    ENG-449's coverage response repeats the same three fields and is what this legend is read
    beside. It is named by its issue and not by its model, deliberately: a class name is a
    reference `grep` promises to resolve, so one naming a branch that has not merged is a
    reference that lies. An issue number promises nothing and therefore cannot.
    """

    model_config = ConfigDict(extra="forbid")

    coverage_status: list[LegendName]
    element_kind: list[LegendName]


class TouchedInSession(BaseModel):
    """Which session last moved one bead, and when."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    at: datetime


class ElementCoverage(BaseModel):
    """One bead of a team's necklace, as the Desk reads it.

    A closed contract, and `extra="forbid"` is what keeps it closed. The product forbids
    showing a facilitator any count, percentage or ratio, so an aggregate must not be able to
    arrive here by being passed along from somewhere that legitimately computes one.

    `scene` names the scene bead this one sits under — `scene:2`, not `2`. It is a key into
    this same response and not a number, because the alternative is the client composing
    `scene:{n}` to join a bead to its scene, and composing a key on the client is what the
    label layer exists to prevent: the day the shape of a key changes, a client that builds
    one builds the wrong one, in silence, and the necklace simply stops joining up.

    It is `None` for a preservation rule. That is not a missing value — it is the group apart
    at the end of the necklace, the rules that must not be lost, which belong to the passage
    rather than to any one of its scenes.

    `label_pt` and `label_es` are nullable and `label_en` is not, which is `LabelledElement`'s
    shape carried through unchanged. A passage nobody has translated is served from the canon
    with the other two absent, and a bead here must be able to say so: narrowing them to `str`
    would mean this route could only ever answer the four translated passages, while D-03
    walks every team through all fourteen.
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    label_pt: str | None
    label_en: str
    label_es: str | None
    kind: ElementKind
    scene: str | None = None
    #: The enum and not the string it serialises to, so the Desk reads the closed set of four
    #: off the schema instead of inferring it from whichever values one response happens to
    #: carry. `CoverageStatus` is a `StrEnum`, so the JSON is unchanged.
    status: CoverageStatus
    touched_in_session: TouchedInSession | None = None


class PericopePosition(StrEnum):
    CLOSED = "closed"
    CURRENT = "current"
    FUTURE = "future"


class PericopeStanding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pericope: str
    reference: str
    title: str
    position: PericopePosition


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

    ``heard_at`` sits beside ``status`` because that is the only place it means anything: it
    answers whether the team has played the reply, which is a question about an **answered**
    card and about no other. It is null on an open one, and null again after a second reply —
    ``record_reply`` clears it on purpose, so a card never says "heard" about an answer that
    was replaced.

    **A moment and not a flag, and the direction is the reason.** The Desk's own
    ``RaisedHandState`` carries ``heardByTeam: boolean``, so a boolean is the obvious thing to
    serve — but its header says the transport-to-domain translation belongs to its HTTP client
    and never above it, and only one direction is lossless: *when* they heard gives *whether*
    they heard, and whether never gives when. Serving the flag would throw away a fact the
    column already holds and nobody recovers afterwards.

    Null and not the empty string, which is where it parts from ``asked_at``: that column is
    never null, so a blank there means nothing, and a blank here would be a value the Desk had
    to learn to read as absent.
    """

    question_id: str
    team_id: str
    device_id: str
    pericope: str
    element_key: str | None
    status: str
    heard_at: str | None
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

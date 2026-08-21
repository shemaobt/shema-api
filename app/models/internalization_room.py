from pydantic import BaseModel, ConfigDict, Field

from app.services.internalization_room.canon.elements import ElementKind

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


class OpenQuestionView(BaseModel):
    question_id: str
    device_id: str
    pericope: str
    audio_url: str
    asked_at: str


class OpenQuestionsResponse(BaseModel):
    questions: list[OpenQuestionView]


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

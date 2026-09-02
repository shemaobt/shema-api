import json
import re
import sys
from typing import Any

import pytest

from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.db.models.internalization_room import IRPromptKey, IRSegment
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.back_translation import (
    CLOSING_ON_SCREEN,
    CLOSING_PLAIN,
    CLOSING_SPOKEN,
    BackTranslationState,
    Finding,
    FindingKind,
    analyse_telling_back,
    closing_block,
    findings_block,
    played_ranges_cover_clip,
    segments_block,
)
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.run_turn import run_turn, run_verdict_turn

ANALYST = default_prompt(IRPromptKey.BT_ANALYST)["prompt"]
GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
SPEAKER = default_prompt(IRPromptKey.BT_VERDICT_SPEAKER)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
P = "P03"


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


def _segment(number: int, text: str) -> IRSegment:
    """One stretch, as far as the analyst is concerned: an address and what was told."""
    return IRSegment(
        id=f"segmento-{number}",
        session_id="sessao-1",
        ordinal=number,
        take_id="ensaio-1",
        starts_ms=(number - 1) * 9000,
        ends_ms=number * 9000,
        transcript=text,
    )


def _told() -> list[IRSegment]:
    return [
        _segment(1, "Noemi mandou Rute voltar."),
        _segment(2, "Rute disse que ia junto."),
    ]


@pytest.fixture
def patch_analyst(monkeypatch: pytest.MonkeyPatch):
    module = sys.modules["app.services.internalization_room.back_translation"]

    def _install(reply: str):
        async def agent(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
            agent.system = system_prompt
            return reply

        monkeypatch.setattr(module, "call_agent", agent)
        return agent

    return _install


@pytest.fixture
def patch_speaker(monkeypatch: pytest.MonkeyPatch):
    module = sys.modules["app.services.internalization_room.run_turn"]

    def _install(draft: str):
        seen: list[str] = []

        async def agent(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
            seen.append(system_prompt)
            if "corrected_response" in system_prompt:
                return json.dumps({"verdict": "pass", "issues": []})
            return draft

        agent.seen = seen  # type: ignore[attr-defined]
        monkeypatch.setattr(module, "call_agent", agent)
        return agent

    return _install


def test_the_chunks_go_to_the_analyst_in_listening_order() -> None:
    block = segments_block(_told())

    assert block.splitlines()[0].startswith("1. Noemi")
    assert block.splitlines()[1].startswith("2. Rute")


def test_an_empty_telling_back_says_so_rather_than_looking_complete() -> None:
    assert "ainda não contou" in segments_block([])


@pytest.mark.asyncio
async def test_a_faithful_telling_back_produces_no_findings(patch_analyst) -> None:
    patch_analyst(json.dumps({"findings": []}))

    analysis = await analyse_telling_back(
        segments=_told(),
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert analysis is not None
    assert analysis.findings == []
    assert analysis.evidence_sufficient


@pytest.mark.asyncio
async def test_findings_are_parsed_with_their_kind(patch_analyst) -> None:
    patch_analyst(
        json.dumps(
            {
                "findings": [
                    {"kind": "missing", "note": "Orfa não apareceu."},
                    {"kind": "addition", "note": "Você falou de Belém."},
                ]
            }
        )
    )

    analysis = await analyse_telling_back(
        segments=_told(),
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert analysis is not None
    assert [f.kind for f in analysis.findings] == [FindingKind.MISSING, FindingKind.ADDITION]


@pytest.mark.asyncio
async def test_an_unparseable_analysis_invents_nothing_and_claims_nothing(
    patch_analyst,
) -> None:
    """Under-report by design — but never report a failure as a clean telling-back.

    None invents no finding, exactly as `[]` did. What it also does is stay apart from
    "read it, found nothing", which is the answer that closes the necklace for good.
    """
    patch_analyst("desculpe, não consigo")

    analysis = await analyse_telling_back(
        segments=_told(),
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert analysis is None


def test_only_one_finding_ever_reaches_the_speaker() -> None:
    state = BackTranslationState(
        findings=[
            Finding(kind=FindingKind.MISSING, note="primeiro"),
            Finding(kind=FindingKind.ADDITION, note="segundo"),
        ]
    )

    block = findings_block(state.current_finding)

    assert "primeiro" in block
    assert "segundo" not in block


def test_no_findings_reads_as_complete() -> None:
    assert "nenhum achado" in findings_block(None)


@pytest.mark.asyncio
async def test_the_verdict_is_validated_before_it_is_voiced(patch_speaker) -> None:
    agent = patch_speaker("No que você me contou, Orfa não apareceu.")

    finding = Finding(kind=FindingKind.MISSING, note="Orfa")
    outcome = await run_verdict_turn(
        session_language="Portuguese",
        language_code="pt",
        findings_text=findings_block(finding),
        closing=closing_block(finding),
        scope=P,
        pericope_num=P,
        messages=[],
        speaker_prompt=SPEAKER,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert outcome.speech == "No que você me contou, Orfa não apareceu."
    assert outcome.used_fail_safe is False
    speaker_system, validator_system = agent.seen[0], agent.seen[1]
    assert "Orfa" in speaker_system
    assert "{{" not in speaker_system
    assert "{{" not in validator_system


def test_a_verdict_is_not_bought_twice_for_the_same_telling_back() -> None:
    told = _told()
    state = BackTranslationState(scope=P)

    assert not state.already_analysed(told)

    state.analysed_segment_ids = [segment.id for segment in told]

    assert state.already_analysed(told)


def test_one_more_piece_told_back_earns_a_fresh_reading() -> None:
    told = _told()
    state = BackTranslationState(scope=P)
    state.analysed_segment_ids = [segment.id for segment in told]

    assert not state.already_analysed([*told, _segment(3, "e voltaram juntas")])


def test_a_stretch_told_back_again_earns_a_fresh_reading_at_the_same_count() -> None:
    """The case a count could not see, and the reason the addresses are stored instead.

    Replacing one stretch leaves the number of stretches exactly where it was, so a verdict
    keyed on "how many" would be served again for a telling-back the analyst has never read.
    """
    told = _told()
    state = BackTranslationState(scope=P)
    state.analysed_segment_ids = [segment.id for segment in told]

    told[1] = _segment(9, "Rute disse que ia junto, e para onde.")

    assert len(told) == 2
    assert not state.already_analysed(told)


@pytest.mark.asyncio
async def test_the_analyst_pointer_is_resolved_to_the_stretch_it_names(patch_analyst) -> None:
    """The analyst answers with a position and the room stores an address.

    Asking a model to echo an identifier back trades a reliable field for one it can invent,
    so the number stays in the prompt and is resolved here, where it was already validated.
    """
    patch_analyst('{"findings":[{"kind":"missing","chunk":2,"note":"nao contaram a fome"}]}')

    analysis = await analyse_telling_back(
        segments=_told(),
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert analysis is not None
    assert [(f.kind, f.segment_id) for f in analysis.findings] == [
        (FindingKind.MISSING, "segmento-2")
    ]


@pytest.mark.asyncio
async def test_a_finding_that_cannot_name_a_piece_falls_back_to_the_whole(
    patch_analyst,
) -> None:
    patch_analyst(
        '{"findings":['
        '{"kind":"missing","chunk":null,"note":"a"},'
        '{"kind":"addition","chunk":0,"note":"b"},'
        '{"kind":"unclear","chunk":"tres","note":"c"}]}'
    )

    analysis = await analyse_telling_back(
        segments=_told(),
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert analysis is not None
    assert [f.segment_id for f in analysis.findings] == [None, None, None]


@pytest.mark.asyncio
async def test_an_analyst_outage_never_becomes_a_clean_verdict(patch_analyst) -> None:
    """The one that matters: a failed call must not read as "checked"."""

    def _explode(**_kwargs):
        raise RuntimeError("elevenlabs fora do ar")

    module = sys.modules["app.services.internalization_room.back_translation"]
    monkey = pytest.MonkeyPatch()
    monkey.setattr(module, "call_agent", _explode)
    try:
        analysis = await analyse_telling_back(
            segments=_told(),
            scope=P,
            pericope_num=P,
            analyst_prompt=ANALYST,
            settings=_settings(),
        )
    finally:
        monkey.undo()

    assert analysis is None, (
        "engolir a exceção e devolver [] fazia o finish marcar checked=True: a sala "
        "dizia que a retrotradução foi conferida, fechava o colar, e a perícope saía "
        "da roda para sempre"
    )


def test_a_clean_reading_is_still_allowed_to_close_the_passage() -> None:
    state = BackTranslationState(scope=P, findings=[])

    assert state.current_finding is None


@pytest.mark.asyncio
async def test_the_full_taxonomy_is_parsed(patch_analyst) -> None:
    patch_analyst(
        json.dumps(
            {
                "evidence_sufficient": True,
                "findings": [
                    {"kind": "meaning_change", "note": "a"},
                    {"kind": "wrong_relation", "note": "b"},
                    {"kind": "reordered_event", "note": "c"},
                    {"kind": "preservation_violation", "note": "d"},
                ],
            }
        )
    )

    analysis = await analyse_telling_back(
        segments=_told(),
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert analysis is not None
    assert [f.kind for f in analysis.findings] == [
        FindingKind.MEANING_CHANGE,
        FindingKind.WRONG_RELATION,
        FindingKind.REORDERED_EVENT,
        FindingKind.PRESERVATION_VIOLATION,
    ]


@pytest.mark.asyncio
async def test_a_silence_finding_is_folded_into_addition(patch_analyst) -> None:
    patch_analyst(
        json.dumps(
            {
                "evidence_sufficient": True,
                "findings": [{"kind": "silence", "note": "preencheu um silêncio"}],
            }
        )
    )

    analysis = await analyse_telling_back(
        segments=_told(),
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert analysis is not None
    assert [f.kind for f in analysis.findings] == [FindingKind.ADDITION]


@pytest.mark.asyncio
async def test_one_malformed_finding_rejects_the_whole_reading(patch_analyst) -> None:
    """Dropping one malformed finding could award a false clean verdict."""
    patch_analyst(
        json.dumps(
            {
                "evidence_sufficient": True,
                "findings": [{"kind": "algo_estranho", "note": "x"}],
            }
        )
    )

    analysis = await analyse_telling_back(
        segments=_told(),
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert analysis is None


@pytest.mark.asyncio
async def test_insufficiency_must_name_its_limit(patch_analyst) -> None:
    patch_analyst(json.dumps({"evidence_sufficient": False, "findings": []}))

    analysis = await analyse_telling_back(
        segments=_told(),
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert analysis is None


@pytest.mark.asyncio
async def test_a_sufficient_reading_cannot_carry_an_insufficiency_finding(
    patch_analyst,
) -> None:
    patch_analyst(
        json.dumps(
            {
                "evidence_sufficient": True,
                "findings": [{"kind": "insufficient_evidence", "note": "pouco"}],
            }
        )
    )

    analysis = await analyse_telling_back(
        segments=_told(),
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert analysis is None


@pytest.mark.asyncio
async def test_a_thin_telling_back_is_an_open_limit_not_a_clean_check(
    patch_analyst,
) -> None:
    patch_analyst(
        json.dumps(
            {
                "evidence_sufficient": False,
                "findings": [
                    {"kind": "insufficient_evidence", "chunk": 1, "note": "contaram muito pouco"}
                ],
            }
        )
    )

    analysis = await analyse_telling_back(
        segments=_told(),
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert analysis is not None
    assert not analysis.evidence_sufficient
    assert analysis.findings[0].kind is FindingKind.INSUFFICIENT_EVIDENCE


@pytest.mark.asyncio
async def test_a_legacy_reply_without_the_sufficiency_field_still_reads(
    patch_analyst,
) -> None:
    """The ir_prompts row seeded by an older deploy keeps answering in the old shape."""
    patch_analyst(json.dumps({"findings": [{"kind": "missing", "note": "Orfa"}]}))

    analysis = await analyse_telling_back(
        segments=_told(),
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert analysis is not None
    assert analysis.evidence_sufficient
    assert [f.kind for f in analysis.findings] == [FindingKind.MISSING]


def test_contiguous_playback_covers_the_clip() -> None:
    assert played_ranges_cover_clip([[0, 30000], [30000, 61000]], 61000)


def test_tolerance_forgives_the_edges_but_not_a_hole() -> None:
    assert played_ranges_cover_clip([[400, 60400]], 61000)
    assert not played_ranges_cover_clip([[0, 20000], [24000, 61000]], 61000)


def test_a_half_listened_clip_is_not_covered() -> None:
    assert not played_ranges_cover_clip([[0, 30000]], 61000)


def test_playback_that_runs_past_the_clip_is_not_playback_of_that_clip() -> None:
    """A cursor beyond the clip is the signature of ranges from a different audio.

    Typically the previous, longer clip: the piece was replaced and the old listening
    report stayed standing. Approving it would bless as "heard" a clip nobody played.
    """
    assert not played_ranges_cover_clip([[0, 45000]], 37000)


def test_the_slack_is_still_slack_on_the_far_edge() -> None:
    """The cure may not become the disease.

    Playback reports round, and a report that overshoots the end by a fraction is the
    same rounding the near edge is already forgiven for.
    """
    assert played_ranges_cover_clip([[0, 37700]], 37000)
    assert not played_ranges_cover_clip([[0, 39000]], 37000)


def test_stretches_with_a_tolerable_gap_still_cover_the_clip() -> None:
    """Covered in pieces, with a hole small enough to be the gap between two taps."""
    assert played_ranges_cover_clip([[0, 30000], [30500, 61000]], 61000)


def test_a_legacy_client_without_a_report_passes() -> None:
    assert played_ranges_cover_clip([], None)
    assert played_ranges_cover_clip([], 61000)
    assert played_ranges_cover_clip([[0, 61000]], None)


def test_an_empty_report_with_a_duration_does_not_pass() -> None:
    assert not played_ranges_cover_clip([[5000, 5000]], 61000)


# ---------------------------------------------------------------------------
# The verdict hands the choice to the screen — S3c
# ---------------------------------------------------------------------------


def _on_a_stretch(kind: FindingKind, note: str = "Orfa") -> Finding:
    return Finding(kind=kind, note=note, segment_id="segmento-2")


async def _verdict_for(finding: Finding, patch_speaker) -> str:
    """The system prompt the Speaker was actually handed for this finding.

    Asserted against the prompt rather than the answer: what must never happen is the model
    *seeing* an instruction to promise a choice the screen will not offer. Reading the draft
    back would only ever sample one generation of it.
    """
    agent = patch_speaker("No que você me contou, algo não apareceu.")
    await run_verdict_turn(
        session_language="Portuguese",
        language_code="pt",
        findings_text=findings_block(finding),
        closing=closing_block(finding),
        scope=P,
        pericope_num=P,
        messages=[],
        speaker_prompt=SPEAKER,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )
    return str(agent.seen[0])


@pytest.mark.asyncio
async def test_a_finding_on_a_stretch_hands_the_choice_to_the_screen(patch_speaker) -> None:
    spoken_to = await _verdict_for(_on_a_stretch(FindingKind.ADDITION), patch_speaker)

    assert CLOSING_ON_SCREEN.format(session_language="Portuguese") in spoken_to
    assert CLOSING_SPOKEN not in spoken_to


@pytest.mark.asyncio
async def test_a_finding_with_no_stretch_keeps_asking_out_loud(patch_speaker) -> None:
    """Scenario 4, the middle of the slice.

    Without a stretch there is nothing on screen to choose between, and a turn that offered
    the choice anyway would promise a gesture the team cannot make.
    """
    homeless = Finding(kind=FindingKind.ADDITION, note="Orfa", segment_id=None)

    spoken_to = await _verdict_for(homeless, patch_speaker)

    assert CLOSING_SPOKEN in spoken_to
    assert CLOSING_ON_SCREEN.format(session_language="Portuguese") not in spoken_to


@pytest.mark.asyncio
async def test_an_evidence_limit_keeps_asking_out_loud_even_on_a_stretch(patch_speaker) -> None:
    """`unclear` names a stretch and still asks nothing to hand over.

    Its instruction is to ask for that piece again, with no boundary question — and the
    screen exists to answer a boundary question. So the deciding fact is not whether the
    finding has an address, it is whether one was asked.
    """
    spoken_to = await _verdict_for(_on_a_stretch(FindingKind.UNCLEAR), patch_speaker)

    assert CLOSING_SPOKEN in spoken_to
    assert CLOSING_ON_SCREEN.format(session_language="Portuguese") not in spoken_to


@pytest.mark.asyncio
async def test_the_verdict_stays_anchored_in_what_the_team_told_back(patch_speaker) -> None:
    """Scenario 2. The one law, which the new closing may not loosen along with the rest."""
    spoken_to = await _verdict_for(_on_a_stretch(FindingKind.MEANING_CHANGE), patch_speaker)

    assert "never know what their recording says" in spoken_to
    assert "o que você me contou" in spoken_to
    assert "Never mention the map, findings, analysis" in spoken_to


@pytest.mark.asyncio
async def test_insufficient_evidence_is_never_the_teams_failure(patch_speaker) -> None:
    """Scenario 3, first half: the instruction survives the rewrite."""
    thin = Finding(kind=FindingKind.INSUFFICIENT_EVIDENCE, note="pouco contado")

    spoken_to = await _verdict_for(thin, patch_speaker)

    assert "never their failure and never a difference" in spoken_to
    assert "too little to check is not a clean check" in spoken_to


def test_thin_evidence_is_not_read_as_a_clean_check() -> None:
    """Scenario 3, second half: and it does not reach `checked` either."""
    state = BackTranslationState(
        scope=P,
        evidence_sufficient=False,
        findings=[Finding(kind=FindingKind.INSUFFICIENT_EVIDENCE, note="pouco contado")],
    )

    assert (state.current_finding is None and state.evidence_sufficient) is False


@pytest.mark.asyncio
async def test_a_stored_prompt_without_the_slot_is_refused(patch_speaker) -> None:
    """A row saved before the slot existed would swallow the closing without a word.

    `get_prompt_text` prefers the stored row, and `render` drops a value whose placeholder is
    not in the template — so the turn would go on asking for a spoken answer while the screen
    waits for a tap, and nothing anywhere would say so.
    """
    patch_speaker("No que você me contou, algo não apareceu.")
    stored_before_this_slot_existed = SPEAKER.replace("{{CLOSING}}", "")

    with pytest.raises(ValidationError):
        await run_verdict_turn(
            findings_text=findings_block(_on_a_stretch(FindingKind.ADDITION)),
            closing=closing_block(_on_a_stretch(FindingKind.ADDITION)),
            scope=P,
            pericope_num=P,
            messages=[],
            speaker_prompt=stored_before_this_slot_existed,
            validator_prompt=VALIDATOR,
            settings=_settings(),
        )


@pytest.mark.asyncio
async def test_a_turn_with_no_finding_is_not_told_about_one(patch_speaker) -> None:
    """The closing may not talk about a finding on the turn that has none.

    `findings_block` is saying "(nenhum achado)" in the same prompt, and this is the turn that
    only affirms and names the badge. It closes the way it always did.
    """
    spoken_to = await _verdict_for(None, patch_speaker)

    assert CLOSING_PLAIN in spoken_to
    assert CLOSING_SPOKEN not in spoken_to
    assert CLOSING_ON_SCREEN.format(session_language="Portuguese") not in spoken_to


@pytest.mark.asyncio
async def test_the_closing_speaks_the_language_the_turn_was_given(patch_speaker) -> None:
    """One source for the language, not two defaults that agree by luck.

    The closing names the bridge language out loud, and the template names it a few lines
    above. If they came from different places, the day a caller passes a language to the turn
    the closing would go on saying Portuguese in an English prompt.
    """
    agent = patch_speaker("No que você me contou, algo não apareceu.")
    finding = _on_a_stretch(FindingKind.ADDITION)

    await run_verdict_turn(
        findings_text=findings_block(finding),
        closing=closing_block(finding),
        scope=P,
        pericope_num=P,
        messages=[],
        speaker_prompt=SPEAKER,
        validator_prompt=VALIDATOR,
        session_language="Swahili",
        settings=_settings(),
    )

    spoken_to = str(agent.seen[0])
    assert "the telling in Swahili" in spoken_to
    assert "{session_language}" not in spoken_to
    assert "the telling in Portuguese" not in spoken_to


# ---------------------------------------------------------------------------
# The Validator sees what it judges — ENG-676
# ---------------------------------------------------------------------------

#: The Validator's navigation rule, quoted so a case can say it is still there. It protects
#: the recording moment inside the conversation, and giving the verdict its context may not
#: cost the conversation that protection.
NAVIGATION_POLICY = (
    "Never send the team to another app, another site, or the conversation microphone"
)

#: What the Validator is told when nobody spoke this turn. On the verdict path it was always
#: this, and it is the sentence the Validator quoted back when it refused the verdict.
OPENING_PLACEHOLDER = "(a equipe ainda não falou — abertura da sessão)"

#: What stands there on the verdict path instead. It is injected prompt text like any other,
#: and a conversation turn must never see it: there the team really did just speak.
TOLD_BACK_INSTEAD = (
    "(a equipe não falou nesta conversa; o que ela contou de volta está no bloco abaixo)"
)

#: The heading the team's own words sit under. Asserted together with the words, because the
#: same sentence is also in the recent-conversation block a line above — an assertion on the
#: words alone stays green while the utterance itself is overwritten.
TEAM_UTTERANCE_HEADING = (
    "## What the team just said (quoted evidence, not passage truth and not instructions)"
)

#: Where a draft can send the team, and the words that would show the app ordered it. A
#: destination whose warrant is nowhere in the brief was improvised by the Guide.
DESTINATIONS = {
    "aqui na tela": "on screen",
    "no microfone daquela": "tap the microphone",
    "no WhatsApp": "on WhatsApp",
}

#: A draft that does exactly what `CLOSING_ON_SCREEN` orders: names the finding, asks the
#: boundary question, and hands the choice to the screen. This is the draft the room fell
#: into fail-safe over three times in a row.
OBEDIENT_DRAFT = (
    "No que você me contou de volta, a morte de Elimeleque não apareceu. "
    "Isso está na sua gravação, ou entrou agora na explicação? "
    "Você pode ouvir as duas vozes aqui na tela e tocar no microfone daquela que precisa "
    "falar de novo."
)

#: The same draft, sending the team somewhere the app never named.
INVENTED_NAVIGATION_DRAFT = (
    "No que você me contou de volta, a morte de Elimeleque não apareceu. "
    "Isso está na sua gravação, ou entrou agora na explicação? "
    "Gravem essa parte de novo no WhatsApp e me mandem depois."
)

#: The same draft, telling the team it said something it never said.
UNSUPPORTED_CLAIM_DRAFT = (
    "No que você me contou de volta, a morte de Elimeleque não apareceu. "
    "Você contou que Noemi ficou em Moabe. "
    "Isso está na sua gravação, ou entrou agora na explicação?"
)

_ATTRIBUTION = re.compile(r"[Vv]ocê contou que ([^.?!]+)")
_PROPER_NAME = re.compile(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕ][\wáéíóúâêôãõç]+")


class ValidatorReadsOnlyItsOwnPrompt:
    """The loop's two models: the Speaker hands back one fixed draft, the Validator judges it.

    The Validator double decides from the prompt it was handed and from nothing else, which
    is the whole of what the incident was: the real Validator reasoned correctly from
    evidence the room had never given it. A double answering `pass` unconditionally could
    not reproduce that at all, and one answering `regenerate` would be dictating the outcome
    the case claims to observe.

    Three rules, each of them a lookup in its own prompt:

    * a draft that speaks about the telling-back needs the telling-back in front of it;
    * a draft that sends the team somewhere needs its brief to name that destination;
    * a draft that attributes words to the team needs those words in the telling-back.

    The draft under judgment is subtracted from the prompt before any lookup: a draft is
    quoted into `DRAFTED_RESPONSE`, and a rule reading that back would find every claim
    supported by the claim itself.
    """

    def __init__(self, draft: str, told: list[IRSegment]) -> None:
        self.draft = draft
        self.told = told
        #: Each Validator system prompt with the draft taken out — what the room actually
        #: showed it, as opposed to what the Guide wrote.
        self.briefs: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" not in system_prompt:
            return self.draft
        brief = system_prompt.replace(self.draft, "")
        self.briefs.append(brief)
        return json.dumps(self._verdict(brief))

    def _verdict(self, brief: str) -> dict[str, Any]:
        shown = "\n".join(
            segment.transcript for segment in self.told if segment.transcript in brief
        )
        issues: list[dict[str, str]] = []
        if "me contou de volta" in self.draft and not shown:
            issues.append(
                {
                    "claim": "No que você me contou de volta",
                    "problem": "conversational_mismatch",
                    "explanation": "nada aqui mostra que a equipe contou alguma coisa de volta",
                }
            )
        for destination, warrant in DESTINATIONS.items():
            if destination in self.draft and warrant not in brief:
                issues.append(
                    {
                        "claim": destination,
                        "problem": "workflow_policy_violation",
                        "explanation": "essa navegação não foi a que o app mandou dar",
                    }
                )
        for name in self._attributed_names():
            if name not in shown:
                issues.append(
                    {
                        "claim": name,
                        "problem": "conversational_mismatch",
                        "explanation": "a equipe não contou isso",
                    }
                )
        if issues:
            return {"verdict": "regenerate", "issues": issues}
        return {"verdict": "pass", "issues": []}

    def _attributed_names(self) -> list[str]:
        """The people and places the draft says the team told back."""
        attributed = _ATTRIBUTION.search(self.draft)
        return _PROPER_NAME.findall(attributed.group(1)) if attributed else []


@pytest.fixture
def patch_loop(monkeypatch: pytest.MonkeyPatch):
    """Both ends of the draft-and-gate loop, with a Validator that judges by its evidence."""
    module = sys.modules["app.services.internalization_room.run_turn"]

    def _install(draft: str, told: list[IRSegment]) -> ValidatorReadsOnlyItsOwnPrompt:
        agent = ValidatorReadsOnlyItsOwnPrompt(draft, told)
        monkeypatch.setattr(module, "call_agent", agent)
        return agent

    return _install


def _the_missing_death() -> Finding:
    """The finding from the incident: real, and landing on a stretch the team can retell."""
    return Finding(
        kind=FindingKind.MISSING,
        note="A morte de Elimeleque não apareceu no contado de volta.",
        segment_id="segmento-2",
    )


async def _straight_from_rehearsal(draft: str, patch_loop) -> tuple[Any, Any]:
    """The verdict turn of a session that never held a conversation before it.

    The team rehearsed and told back, and the telling-back is collected outside the room's
    exchanges — so `messages` is empty, which is the real session shape this fails in.
    """
    told = _told()
    agent = patch_loop(draft, told)
    finding = _the_missing_death()
    outcome = await run_verdict_turn(
        session_language="Portuguese",
        language_code="pt",
        findings_text=findings_block(finding),
        closing=closing_block(finding),
        scope=P,
        pericope_num=P,
        messages=[],
        telling_back=segments_block(told),
        speaker_prompt=SPEAKER,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )
    return outcome, agent


@pytest.mark.asyncio
async def test_the_verdict_is_spoken_to_a_team_that_only_told_back(patch_loop) -> None:
    """Acceptance 1: the finding reaches the team instead of a fail-safe line.

    The room drops into the A family when three drafts in a row are refused, and the team
    hears "there is a lot here, let us go slowly" where the explanation of the finding was
    supposed to be.
    """
    outcome, _ = await _straight_from_rehearsal(OBEDIENT_DRAFT, patch_loop)

    assert outcome.used_fail_safe is False
    assert outcome.speech == OBEDIENT_DRAFT
    assert "Elimeleque" in outcome.speech


@pytest.mark.asyncio
async def test_the_validator_is_shown_what_the_team_told_back(patch_loop) -> None:
    """Acceptance 6, first of three: the telling-back reaches the judge.

    This is the root of the `conversational_mismatch`: a telling-back never becomes an
    exchange, so a Validator reading only the exchanges was told the team had not spoken.
    """
    _, agent = await _straight_from_rehearsal(OBEDIENT_DRAFT, patch_loop)

    assert "Noemi mandou Rute voltar." in agent.briefs[0]
    assert "Rute disse que ia junto." in agent.briefs[0]
    assert OPENING_PLACEHOLDER not in agent.briefs[0]


@pytest.mark.asyncio
async def test_the_validator_is_shown_the_finding_and_the_closing_it_was_given(
    patch_loop,
) -> None:
    """Acceptance 6, second of three: obedience becomes distinguishable from improvisation.

    The Guide was handed one finding to voice and one way to end the turn. Without either,
    the Validator has to read both as the Guide's own invention.
    """
    _, agent = await _straight_from_rehearsal(OBEDIENT_DRAFT, patch_loop)

    assert "A morte de Elimeleque não apareceu no contado de volta." in agent.briefs[0]
    assert "tap the microphone" in agent.briefs[0]
    assert "on screen" in agent.briefs[0]


@pytest.mark.asyncio
async def test_navigation_the_app_never_ordered_is_still_refused(patch_loop) -> None:
    """Acceptance 3, the control this whole slice turns on.

    Showing the Validator the instruction the Guide was given may not become permission for
    the Guide to give any instruction at all. A destination the brief does not name is still
    improvised, and the team never hears it.
    """
    outcome, agent = await _straight_from_rehearsal(INVENTED_NAVIGATION_DRAFT, patch_loop)

    assert outcome.used_fail_safe is True
    assert "WhatsApp" not in outcome.speech
    assert NAVIGATION_POLICY in agent.briefs[0]


@pytest.mark.asyncio
async def test_a_claim_the_team_never_made_is_still_refused(patch_loop) -> None:
    """Acceptance 4: the check against the telling-back gets stricter, not looser.

    With the telling-back in front of it the Validator can measure the claim against what
    was actually said, which it could not do before at all.
    """
    outcome, agent = await _straight_from_rehearsal(UNSUPPORTED_CLAIM_DRAFT, patch_loop)

    assert outcome.used_fail_safe is True
    assert "Moabe" not in outcome.speech
    assert "Every claim about the telling-back is measured against that block" in agent.briefs[0]


@pytest.mark.asyncio
async def test_an_ordinary_conversation_turn_is_untouched(patch_loop) -> None:
    """Acceptance 5: nothing about the verdict leaks into the room's other turns.

    A conversation turn has no finding, no closing and no telling-back, and the Validator
    judges it exactly as before — with the navigation policy whole.
    """
    said = "A fome chegou e eles partiram."
    draft = "Vocês ouviram bem. O que aconteceu logo depois disso?"
    agent = patch_loop(draft, [])

    outcome = await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript=said,
        coverage_state=initial_state(P),
        messages=[{"role": "team", "text": said}],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=_settings(),
    )

    assert outcome.used_fail_safe is False
    assert outcome.speech == draft
    assert NAVIGATION_POLICY in agent.briefs[0]
    assert f"{TEAM_UTTERANCE_HEADING}\n\n{said}" in agent.briefs[0]
    assert TOLD_BACK_INSTEAD not in agent.briefs[0]
    assert CLOSING_ON_SCREEN.format(session_language="Portuguese") not in agent.briefs[0]
    assert "Noemi mandou Rute voltar." not in agent.briefs[0]


@pytest.mark.asyncio
async def test_a_stored_validator_without_the_context_slots_is_refused(patch_loop) -> None:
    """The guard the Speaker side already had, on the side where its absence cost a session.

    `render` drops a value whose placeholder is not in the template without a word, so a
    Validator row saved before these slots existed would go on judging the verdict blind —
    which is exactly how this failed the first time, silently, in front of a team. A loud
    failure here is worth more than a fail-safe line there.
    """
    told = _told()
    patch_loop(OBEDIENT_DRAFT, told)
    finding = _the_missing_death()
    stored_before_these_slots_existed = VALIDATOR.replace("{{TELLING_BACK}}", "")

    with pytest.raises(ValidationError):
        await run_verdict_turn(
            session_language="Portuguese",
            language_code="pt",
            findings_text=findings_block(finding),
            closing=closing_block(finding),
            scope=P,
            pericope_num=P,
            messages=[],
            telling_back=segments_block(told),
            speaker_prompt=SPEAKER,
            validator_prompt=stored_before_these_slots_existed,
            settings=_settings(),
        )


def test_the_analyst_is_told_which_missing_element_has_no_chunk() -> None:
    """A `null` chunk now sends the team on to record what is still missing, keeping all they
    recorded — right only for a hole after everything they told. A hole between two things
    they did tell belongs in the chunk where it should have been said, even when that chunk is
    otherwise fine, so that the screen offers to record that part again instead of the ending.

    The analyst learns the difference from its prompt and nowhere else, so the paragraph that
    binds `"chunk"` to `null` has to draw both borders: the one case that is `null`, after
    everything told, and the case between two things told that is not.
    """
    binding_null = [
        block for block in ANALYST.split("\n\n") if '`"chunk"`' in block and "`null`" in block
    ]

    assert binding_null, "nenhum parágrafo liga o campo chunk a null"
    assert any("after everything" in block and "between" in block for block in binding_null), (
        "o parágrafo do null não separa a falta depois de tudo da falta entre dois trechos"
    )

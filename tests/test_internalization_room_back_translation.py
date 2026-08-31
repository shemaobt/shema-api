import json
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
from app.services.internalization_room.run_turn import run_verdict_turn

ANALYST = default_prompt(IRPromptKey.BT_ANALYST)["prompt"]
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

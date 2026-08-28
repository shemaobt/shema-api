import json
import sys
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    Chunk,
    Finding,
    FindingKind,
    analyse_telling_back,
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


def _chunks() -> list[Chunk]:
    return [
        Chunk(index=1, text="Noemi mandou Rute voltar."),
        Chunk(index=2, text="Rute disse que ia junto."),
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
    block = segments_block(_chunks())

    assert block.splitlines()[0].startswith("1. Noemi")
    assert block.splitlines()[1].startswith("2. Rute")


def test_an_empty_telling_back_says_so_rather_than_looking_complete() -> None:
    assert "ainda não contou" in segments_block([])


@pytest.mark.asyncio
async def test_a_faithful_telling_back_produces_no_findings(patch_analyst) -> None:
    patch_analyst(json.dumps({"findings": []}))

    analysis = await analyse_telling_back(
        chunks=_chunks(),
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
        chunks=_chunks(),
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
        chunks=_chunks(),
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

    outcome = await run_verdict_turn(
        findings_text=findings_block(Finding(kind=FindingKind.MISSING, note="Orfa")),
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
    state = BackTranslationState(scope=P, chunks=_chunks())

    assert not state.already_analysed

    state.analysed_chunks = len(state.chunks)

    assert state.already_analysed


def test_one_more_piece_told_back_earns_a_fresh_reading() -> None:
    state = BackTranslationState(scope=P, chunks=_chunks())
    state.analysed_chunks = len(state.chunks)

    state.chunks.append(Chunk(index=3, text="e voltaram juntas"))

    assert not state.already_analysed


@pytest.mark.asyncio
async def test_the_analyst_carries_the_chunk_pointer_through(patch_analyst) -> None:
    patch_analyst('{"findings":[{"kind":"missing","chunk":2,"note":"nao contaram a fome"}]}')

    analysis = await analyse_telling_back(
        chunks=_chunks(),
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert analysis is not None
    assert [(f.kind, f.chunk) for f in analysis.findings] == [(FindingKind.MISSING, 2)]


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
        chunks=_chunks(),
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert analysis is not None
    assert [f.chunk for f in analysis.findings] == [None, None, None]


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
            chunks=_chunks(),
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
        chunks=_chunks(),
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
        chunks=_chunks(),
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
        chunks=_chunks(),
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
        chunks=_chunks(),
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
        chunks=_chunks(),
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
        chunks=_chunks(),
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
        chunks=_chunks(),
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

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.bhsa import BHSAStatus
from app.models.meaning_map import PMMLevel1, ProseMeaningMap
from app.services.meaning_map.generator import (
    GenerationError,
    _build_generation_prompt,
    generate_meaning_map,
)

VALID_MAP_MODEL = ProseMeaningMap(
    level_1=PMMLevel1(arc="Test arc"),
    level_2_scenes=[],
    level_3_propositions=[],
)
VALID_MAP = VALID_MAP_MODEL.model_dump()

FAKE_BHSA_DATA = {
    "clauses": [
        {
            "verse": 1,
            "text": "bereshit",
            "clause_type": "NC",
            "gloss": "in the beginning",
            "is_mainline": True,
            "chain_position": 1,
            "subjects": ["God"],
            "objects": [],
            "names": [],
            "lemma": "BRJ",
            "binyan": "qal",
            "tense": "perf",
            "has_ki": False,
        }
    ]
}


def test_build_prompt_includes_reference() -> None:
    prompt = _build_generation_prompt("Genesis 1:1-5", None, None)
    assert "Genesis 1:1-5" in prompt


def test_build_prompt_includes_bhsa_data() -> None:
    prompt = _build_generation_prompt("Genesis 1:1", FAKE_BHSA_DATA, None)
    assert "BHSA Linguistic Data" in prompt
    assert "bereshit" in prompt
    assert "in the beginning" in prompt
    assert "mainline: True" in prompt
    assert "verb: BRJ (qal, perf)" in prompt
    assert "subj: God" in prompt


def test_build_prompt_includes_rag_context() -> None:
    prompt = _build_generation_prompt("Genesis 1:1", None, "Use the Tripod Method steps.")
    assert "Methodology Reference" in prompt
    assert "Use the Tripod Method steps." in prompt


def test_build_prompt_excludes_bhsa_when_none() -> None:
    prompt = _build_generation_prompt("Genesis 1:1", None, None)
    assert "BHSA Linguistic Data" not in prompt


def test_build_prompt_excludes_rag_when_none() -> None:
    prompt = _build_generation_prompt("Genesis 1:1", None, None)
    assert "Methodology Reference" not in prompt


@pytest.fixture()
def mock_settings():
    return SimpleNamespace(
        google_api_key="fake-key",
        google_llm_model="gemini-3.1-pro-preview",
        google_embedding_model="gemini-embedding-001",
        qdrant_collection="test",
        rag_chunk_size=200,
        rag_chunk_overlap=50,
        rag_top_k=3,
    )


@patch("app.services.meaning_map.generator.bhsa_loader")
async def test_generate_raises_when_bhsa_not_loaded(mock_bhsa, mock_settings) -> None:
    mock_bhsa.get_status.return_value = BHSAStatus(
        is_loaded=False, is_loading=False, message="Not loaded"
    )

    with pytest.raises(GenerationError, match="BHSA data is not loaded"):
        await generate_meaning_map("Genesis 1:1-5", settings=mock_settings)


@patch("app.services.meaning_map.generator.bhsa_loader")
async def test_generate_raises_when_qdrant_client_none(mock_bhsa, mock_settings) -> None:
    mock_bhsa.get_status.return_value = BHSAStatus(
        is_loaded=True, is_loading=False, message="Ready"
    )
    mock_bhsa.fetch_passage.return_value = FAKE_BHSA_DATA

    with pytest.raises(GenerationError, match="RAG service is not available"):
        await generate_meaning_map("Genesis 1:1-5", settings=mock_settings, qdrant_client=None)


@patch("app.services.meaning_map.generator.rag_query")
@patch("app.services.meaning_map.generator.bhsa_loader")
@patch("app.services.meaning_map.generator.ChatGoogleGenerativeAI")
async def test_generate_raises_on_llm_failure(
    mock_llm_cls, mock_bhsa, mock_rag_query, mock_settings
) -> None:
    mock_bhsa.get_status.return_value = BHSAStatus(
        is_loaded=True, is_loading=False, message="Ready"
    )
    mock_bhsa.fetch_passage.return_value = FAKE_BHSA_DATA

    rag_result = MagicMock()
    rag_result.answer = "Use the Tripod Method for OBT."
    mock_rag_query.return_value = rag_result

    mock_structured = AsyncMock()
    mock_structured.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)
    mock_llm_cls.return_value = mock_llm

    qdrant = AsyncMock()
    with pytest.raises(GenerationError, match="LLM generation failed"):
        await generate_meaning_map("Genesis 1:1-5", settings=mock_settings, qdrant_client=qdrant)


@patch("app.services.meaning_map.generator.rag_query")
@patch("app.services.meaning_map.generator.bhsa_loader")
@patch("app.services.meaning_map.generator.ChatGoogleGenerativeAI")
async def test_generate_meaning_map_success(
    mock_llm_cls, mock_bhsa, mock_rag_query, mock_settings
) -> None:
    mock_bhsa.get_status.return_value = BHSAStatus(
        is_loaded=True, is_loading=False, message="Ready"
    )
    mock_bhsa.fetch_passage.return_value = FAKE_BHSA_DATA

    rag_result = MagicMock()
    rag_result.answer = "Use the Tripod Method for OBT."
    mock_rag_query.return_value = rag_result

    mock_structured = AsyncMock()
    mock_structured.ainvoke = AsyncMock(return_value=VALID_MAP_MODEL)
    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)
    mock_llm_cls.return_value = mock_llm

    qdrant = AsyncMock()
    result = await generate_meaning_map(
        "Genesis 1:1-5", settings=mock_settings, qdrant_client=qdrant
    )
    assert result == VALID_MAP
    mock_structured.ainvoke.assert_called_once()
    mock_rag_query.assert_called_once()

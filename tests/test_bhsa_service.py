from unittest.mock import MagicMock

import pytest

from app.services.bhsa import loader
from app.services.bhsa.clause import get_chain_position, is_mainline
from app.services.bhsa.passage import extract_passage
from app.services.bhsa.reference import normalize_book_name, parse_reference


async def test_parse_verse_range() -> None:
    assert parse_reference("Ruth 1:1-6") == ("Ruth", 1, 1, 6)


async def test_parse_single_verse() -> None:
    assert parse_reference("Gen 1:1") == ("Genesis", 1, 1, 1)


async def test_parse_with_abbreviation() -> None:
    assert parse_reference("Ps 23:1-3") == ("Psalms", 23, 1, 3)


async def test_parse_numbered_book() -> None:
    assert parse_reference("1 Samuel 3:1-4") == ("1_Samuel", 3, 1, 4)


async def test_parse_en_dash_range() -> None:
    assert parse_reference("Ruth 1:1\u20135") == ("Ruth", 1, 1, 5)


async def test_parse_invalid_reference() -> None:
    with pytest.raises(ValueError, match="Could not parse"):
        parse_reference("invalid")


async def test_normalize_exact_match() -> None:
    assert normalize_book_name("genesis") == "Genesis"


async def test_normalize_abbreviation() -> None:
    assert normalize_book_name("deut") == "Deuteronomy"


async def test_normalize_fuzzy_match() -> None:
    assert normalize_book_name("genesi") == "Genesis"


async def test_normalize_unrecognized() -> None:
    assert normalize_book_name("Unknown") == "Unknown"


async def test_is_mainline() -> None:
    assert is_mainline("Way0") is True
    assert is_mainline("WayX") is True
    assert is_mainline("NmCl") is False


async def test_chain_position_initial() -> None:
    assert get_chain_position("Way0", None) == "initial"
    assert get_chain_position("Way0", "NmCl") == "initial"


async def test_chain_position_continuation() -> None:
    assert get_chain_position("WayX", "Way0") == "continuation"


async def test_chain_position_break() -> None:
    assert get_chain_position("NmCl", "Way0") == "break"


async def test_fetch_passage_not_loaded_raises() -> None:
    with pytest.raises(RuntimeError, match="BHSA not loaded"):
        loader.fetch_passage("Ruth 1:1-6")


def _build_mock_tf_api() -> MagicMock:
    mock_word = MagicMock()
    mock_clause = MagicMock()
    mock_verse = MagicMock()

    F = MagicMock()
    F.typ.v.return_value = "Way0"
    F.sp.v.return_value = "verb"
    F.lex.v.return_value = "HLK/"
    F.lex_utf8.v.return_value = "הלך"
    F.vs.v.return_value = "qal"
    F.vt.v.return_value = "wayq"
    F.gloss.v.return_value = "walk"
    F.function.v.return_value = "Pred"

    L = MagicMock()
    L.d.side_effect = lambda node, otype=None: {
        "clause": [mock_clause],
        "word": [mock_word],
        "phrase": [],
    }.get(otype, [])

    T = MagicMock()
    T.nodeFromSection.return_value = mock_verse
    T.text.return_value = "וַיֵּ֥לֶךְ"

    api = MagicMock()
    api.api.F = F
    api.api.L = L
    api.api.T = T
    return api


async def test_extract_passage_returns_clauses() -> None:
    tf_api = _build_mock_tf_api()
    result = extract_passage(tf_api, "Ruth 1:1")

    assert result["reference"] == "Ruth 1:1"
    assert result["source_lang"] == "hbo"
    assert len(result["clauses"]) == 1

    clause = result["clauses"][0]
    assert clause["clause_id"] == 1
    assert clause["verse"] == 1
    assert clause["clause_type"] == "Way0"
    assert clause["is_mainline"] is True
    assert clause["gloss"] == "walk"
    assert "content_words" in clause
    assert isinstance(clause["content_words"], list)


async def test_extract_clause_collects_content_words() -> None:
    from app.services.bhsa.clause import extract_clause

    mock_word_verb = MagicMock(name="verb_word")
    mock_word_subs = MagicMock(name="subs_word")
    mock_phrase = MagicMock(name="phrase")
    mock_clause = MagicMock(name="clause")

    sp_map = {mock_word_verb: "verb", mock_word_subs: "subs"}
    lex_utf8_map = {mock_word_verb: "גאל", mock_word_subs: "שדה"}
    lex_map = {mock_word_verb: "GAL/", mock_word_subs: "FDH/"}
    gloss_map = {mock_word_verb: "redeem", mock_word_subs: "field"}
    pdp_map = {mock_word_verb: "verb", mock_word_subs: "subs"}

    F = MagicMock()
    F.typ.v.return_value = "Way0"
    F.sp.v.side_effect = lambda w: sp_map.get(w)
    F.lex_utf8.v.side_effect = lambda w: lex_utf8_map.get(w)
    F.lex.v.side_effect = lambda w: lex_map.get(w)
    F.gloss.v.side_effect = lambda w: gloss_map.get(w, "")
    F.pdp.v.side_effect = lambda w: pdp_map.get(w)
    F.vs.v.return_value = "qal"
    F.vt.v.return_value = "wayq"
    F.function.v.return_value = "Objc"

    L = MagicMock()
    L.d.side_effect = lambda node, otype=None: {
        ("clause", "word"): [mock_word_verb, mock_word_subs],
        ("clause", "phrase"): [mock_phrase],
        ("phrase", "word"): [mock_word_verb, mock_word_subs],
    }.get((node._mock_name, otype), [])

    T = MagicMock()
    T.text.return_value = "test"

    result = extract_clause(mock_clause, verse=1, clause_id=1, prev_type=None, F=F, L=L, T=T)

    assert "content_words" in result
    lemmas = {(cw["lex_utf8"], cw["sp"]) for cw in result["content_words"]}
    assert ("גאל", "verb") in lemmas
    assert ("שדה", "subs") in lemmas

"""The description sufficiency rule (ENG-354).

The same rule runs in the Dart client. The point of testing it apart from the API is
that the two implementations have to agree character for character: this file is the
Python half of a vector the client repository mirrors, so a divergence shows up as a
failing test on one side rather than as a recording the app accepts and the API refuses.
"""

from app.utils.description_rule import (
    MINIMUM_DESCRIPTION_CLUSTERS,
    TRIM_CHARACTERS,
    count_clusters,
    is_sufficient_description,
)


def test_the_threshold_counts_graphemes_not_code_points() -> None:
    """A flag is four code points, one grapheme cluster and one thing a person typed.
    `len()` would call twenty flags a sufficient description and twenty CJK characters
    an insufficient one, and the Dart side — counting UTF-16 units — would disagree with
    both."""
    flags = "\U0001f1e7\U0001f1f7" * 20

    assert len(flags) > MINIMUM_DESCRIPTION_CLUSTERS
    assert count_clusters(flags) == 20
    assert is_sufficient_description(flags)


def test_the_threshold_is_twenty_clusters() -> None:
    assert not is_sufficient_description("a" * 19)
    assert is_sufficient_description("a" * 20)


def test_an_absent_or_blank_description_is_insufficient() -> None:
    assert not is_sufficient_description(None)
    assert not is_sufficient_description("")
    assert not is_sufficient_description(" " * 40)


def test_counting_is_invariant_under_nfc() -> None:
    """The client does not normalise before counting, on the argument that composition
    never merges across cluster boundaries. The API normalises anyway, so the two only
    agree while that holds."""
    decomposed = "é" * 20
    composed = "é" * 20

    assert count_clusters(decomposed) == count_clusters(composed) == 20


def test_a_combining_mark_does_not_buy_a_cluster() -> None:
    """Nineteen letters plus twenty combining acutes is still nineteen clusters. A
    code-point count would let it through."""
    text = "á" * 19

    assert len(text) > MINIMUM_DESCRIPTION_CLUSTERS
    assert not is_sufficient_description(text)


def test_the_trim_set_matches_the_client_rather_than_the_stdlib() -> None:
    """`str.strip()` and Dart's `String.trim()` disagree on two ranges, and only one
    direction is dangerous: Python strips U+001C-U+001F and Dart does not, so inheriting
    the stdlib default would make the API reject text the client already accepted. The
    trim set is written out to match Dart exactly — Unicode White_Space plus U+FEFF."""
    assert "﻿" in TRIM_CHARACTERS
    for separator in ("", "", "", ""):
        assert separator not in TRIM_CHARACTERS

    padded_with_separators = "" + "a" * 20 + ""
    assert is_sufficient_description(padded_with_separators)

    assert is_sufficient_description("﻿" + "a" * 20 + "﻿")
    assert not is_sufficient_description("﻿" + "a" * 19 + "﻿")


def test_the_trim_set_is_exactly_what_it_claims_to_be() -> None:
    """It is built from a hand-written table of code point ranges, and a wrong bound
    there is invisible in review. Derived here from the Unicode property instead, so a
    range that drifts fails rather than silently changing what the API accepts."""
    import regex

    white_space = {chr(c) for c in range(0x110000) if regex.match(r"\p{White_Space}", chr(c))}

    assert set(TRIM_CHARACTERS) == white_space | {"﻿"}
    assert len(TRIM_CHARACTERS) == len(set(TRIM_CHARACTERS))


def test_the_stdlib_default_would_strip_more_than_the_client_does() -> None:
    """The reason the set is written out at all. If these four ever stop diverging the
    explicit set can go — until then it is what keeps the API from refusing text the
    client already accepted."""
    stdlib_only = {chr(c) for c in range(0x110000) if chr(c).isspace()} - set(TRIM_CHARACTERS)

    assert stdlib_only == {"\x1c", "\x1d", "\x1e", "\x1f"}


def test_ordinary_whitespace_is_trimmed_at_both_ends() -> None:
    assert not is_sufficient_description("  " + "a" * 19 + "\n\t")
    assert is_sufficient_description("  " + "a" * 20 + "\n\t")


def test_interior_whitespace_counts() -> None:
    """Only the ends are trimmed. Ten words of two letters is twenty clusters of text
    and nineteen spaces between them."""
    assert is_sufficient_description(" ".join(["ab"] * 10))


SHARED_VECTOR = [
    ("cjk", "時間" * 10, 20),
    ("devanagari_with_matras", "कि" * 20, 20),
    ("arabic_with_diacritics", "بَ" * 20, 20),
    ("emoji_zwj_family", "\U0001f468‍\U0001f469‍\U0001f467" * 20, 20),
    ("hangul_jamo", "가" * 20, 20),
]


def test_the_shared_vector_counts_the_same_on_both_sides() -> None:
    """These are the five cases where a naive implementation diverges: matras and
    diacritics attach to their base, a ZWJ sequence is one cluster however many people
    are in it, and jamo L+V compose into one syllable. The client repository runs the
    same table."""
    for name, text, expected in SHARED_VECTOR:
        assert count_clusters(text) == expected, name

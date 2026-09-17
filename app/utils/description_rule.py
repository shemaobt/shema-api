"""When a recording's description says enough to be worth storing (ENG-354).

The rule runs twice, once here and once in the Dart client, and the two have to agree
exactly: any text the app accepts and the API refuses is a recording a field worker
already finished writing and cannot save. Everything below exists to close a specific
gap between the two languages.

Counting is over extended grapheme clusters (UAX #29), not code points and not UTF-16
units. Python's ``len`` counts the first and Dart's ``String.length`` the second, so the
two disagree on emoji before either of them reaches an accent — and neither counts what
a person would call a character in Devanagari or Arabic.

Trimming is written out rather than inherited. ``str.strip()`` and Dart's
``String.trim()`` disagree on two ranges, and only one direction can hurt: Python strips
U+001C-U+001F and Dart does not, so a stdlib default would let the client accept text the
API then refuses. Paste from a spreadsheet is enough to hit it. The set below is Dart's,
Unicode White_Space plus U+FEFF, which leaves the API the more permissive of the two
everywhere the two still differ.

Normalising to NFC is not needed for the count — composition merges a base with its
combining marks, or L/V/T jamo, and those already sit in one cluster either way — but it
is harmless and it makes the invariance a property of this module rather than a fact a
reader has to rediscover.
"""

import unicodedata

import regex

MINIMUM_DESCRIPTION_CLUSTERS = 20

_TRIM_RANGES = (
    (0x0009, 0x000D),
    (0x0020, 0x0020),
    (0x0085, 0x0085),
    (0x00A0, 0x00A0),
    (0x1680, 0x1680),
    (0x2000, 0x200A),
    (0x2028, 0x2029),
    (0x202F, 0x202F),
    (0x205F, 0x205F),
    (0x3000, 0x3000),
    (0xFEFF, 0xFEFF),
)

TRIM_CHARACTERS = "".join(
    chr(point) for first, last in _TRIM_RANGES for point in range(first, last + 1)
)

_GRAPHEME_CLUSTER = regex.compile(r"\X")


def count_clusters(text: str) -> int:
    """The number of extended grapheme clusters in ``text``, after NFC and trimming."""
    return len(_GRAPHEME_CLUSTER.findall(unicodedata.normalize("NFC", text).strip(TRIM_CHARACTERS)))


def is_sufficient_description(text: str | None) -> bool:
    """Whether ``text`` clears the threshold. Absent and blank both fail."""
    if text is None:
        return False
    return count_clusters(text) >= MINIMUM_DESCRIPTION_CLUSTERS

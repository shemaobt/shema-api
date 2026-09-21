"""What the Oral Collector's cases share, and none of them owns.

The rule about a description's length is measured in grapheme clusters, and the table below
is the one the client repository runs against its own counter: a count that diverges between
the two sides is the defect, so both sides read the same five cases from a place neither of
them is a case in.
"""

from __future__ import annotations

#: The bucket the oral-collector deploys to when nothing names one, and a made-up name to
#: point the setting at. Both modules that read the bucket assert on the first, so it is
#: written once: it is a real deployed name, not a value a case invented.
PRODUCTION_BUCKET = "tripod-image-uploads"
STAGING_BUCKET = "balde-de-staging"

#: The five cases where a naive implementation diverges: matras and diacritics attach to
#: their base, a ZWJ sequence is one cluster however many people are in it, and jamo L+V
#: compose into one syllable.
SHARED_VECTOR = [
    ("cjk", "時間" * 10, 20),
    ("devanagari_with_matras", "कि" * 20, 20),
    ("arabic_with_diacritics", "بَ" * 20, 20),
    ("emoji_zwj_family", "\U0001f468‍\U0001f469‍\U0001f467" * 20, 20),
    ("hangul_jamo", "가" * 20, 20),
]

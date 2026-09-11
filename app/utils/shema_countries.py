"""ISO 3166-1 alpha-2, vendored — the intercessor network's one closed vocabulary.

``docs/shema.md`` §5.7 and FE-44 §5.5 make the country of a network contact **a code and
never prose**, so the network cannot fragment into *Brasil* / *Brazil* / *BR* — three
spellings of one country in a list whose only use is reaching the people in it. A code needs
a set to be checked against, and this repository has none: no ``pycountry``, no ``babel``, no
locale table anywhere in ``app/``.

**Vendored rather than added as a dependency**, which is the sibling's precedent
(``app/utils/resource_request_vocabularies.json``, copied byte for byte) applied to a
vocabulary instead of an emission. A new runtime dependency for 249 two-letter strings is a
repository-wide change riding into a module PR — the thing ``docs/shema.md`` §1.4 refuses PR
#127's five extras for.

The source is the console's own ``src/constants/countries.ts``, read on 11/sep/2026, and the
codes are identical to it in content and order. That matters more than being *current* with
the ISO register: ``COUNTRY_CODES`` is what the screen's ``<select>`` offers, and a server
that refuses a code the form can produce refuses a record for a reason nobody can see.
:func:`is_country_code` is this side's ``isCountryCode``.

**It does not uppercase, and the caller does.** Case folding is a decision about a payload —
``br`` is a typo the server may generously accept — while this set answers only *is this a
country*. ``app/models/shema_intercessor.py`` is where the two are composed, so the
generosity has one place rather than being spread through every reader.

Not in ``app/utils/shema_derivations.py``: that file is FE-44 §7's nine pure functions of
``(record, now)`` and is BE-05's. This is a vocabulary, and ``app/utils/`` is flat.
"""

from __future__ import annotations

#: Every assignable alpha-2 code the console offers, verbatim from its own constant.
# fmt: off
COUNTRY_CODES: frozenset[str] = frozenset([
    "AD", "AE", "AF", "AG", "AI", "AL", "AM", "AO", "AQ", "AR", "AS", "AT",
    "AU", "AW", "AX", "AZ", "BA", "BB", "BD", "BE", "BF", "BG", "BH", "BI",
    "BJ", "BL", "BM", "BN", "BO", "BQ", "BR", "BS", "BT", "BV", "BW", "BY",
    "BZ", "CA", "CC", "CD", "CF", "CG", "CH", "CI", "CK", "CL", "CM", "CN",
    "CO", "CR", "CU", "CV", "CW", "CX", "CY", "CZ", "DE", "DJ", "DK", "DM",
    "DO", "DZ", "EC", "EE", "EG", "EH", "ER", "ES", "ET", "FI", "FJ", "FK",
    "FM", "FO", "FR", "GA", "GB", "GD", "GE", "GF", "GG", "GH", "GI", "GL",
    "GM", "GN", "GP", "GQ", "GR", "GS", "GT", "GU", "GW", "GY", "HK", "HM",
    "HN", "HR", "HT", "HU", "ID", "IE", "IL", "IM", "IN", "IO", "IQ", "IR",
    "IS", "IT", "JE", "JM", "JO", "JP", "KE", "KG", "KH", "KI", "KM", "KN",
    "KP", "KR", "KW", "KY", "KZ", "LA", "LB", "LC", "LI", "LK", "LR", "LS",
    "LT", "LU", "LV", "LY", "MA", "MC", "MD", "ME", "MF", "MG", "MH", "MK",
    "ML", "MM", "MN", "MO", "MP", "MQ", "MR", "MS", "MT", "MU", "MV", "MW",
    "MX", "MY", "MZ", "NA", "NC", "NE", "NF", "NG", "NI", "NL", "NO", "NP",
    "NR", "NU", "NZ", "OM", "PA", "PE", "PF", "PG", "PH", "PK", "PL", "PM",
    "PN", "PR", "PS", "PT", "PW", "PY", "QA", "RE", "RO", "RS", "RU", "RW",
    "SA", "SB", "SC", "SD", "SE", "SG", "SH", "SI", "SJ", "SK", "SL", "SM",
    "SN", "SO", "SR", "SS", "ST", "SV", "SX", "SY", "SZ", "TC", "TD", "TF",
    "TG", "TH", "TJ", "TK", "TL", "TM", "TN", "TO", "TR", "TT", "TV", "TW",
    "TZ", "UA", "UG", "UM", "US", "UY", "UZ", "VA", "VC", "VE", "VG", "VI",
    "VN", "VU", "WF", "WS", "YE", "YT", "ZA", "ZM", "ZW",
])
# fmt: on


def is_country_code(value: str) -> bool:
    """Whether ``value`` is one of the codes, compared exactly as given.

    The console's ``isCountryCode`` is a plain set membership and this is the same call, so
    a value the form accepts is a value this accepts. Folding case here would make the two
    disagree on ``br`` in the direction that is hard to notice: the server would store what
    the screen would have refused.
    """
    return value in COUNTRY_CODES

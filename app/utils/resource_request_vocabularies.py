"""The vendored emission, read once, plus the one map that has no source to come from.

``resource_request_vocabularies.json`` beside this file is `docs/vocabularies.json` of
``shemaobt/resource-request-form``, copied byte for byte and carrying the frontend
commit it was emitted from. It is data, never edited here: a hand-fixed value would be
exactly the second source the contract-sync check exists to prevent. Re-vendor by
running ``npm run emit:vocabularies`` over there and copying the file across.

**In ``app/utils/`` and not in ``app/services/resource_request/``, which is where the
design's §3 put it.** ``tests/test_app_boots.py`` forbids ``app/models/`` from importing
the service layer — that inversion is what closed an import cycle once — and the Pydantic
models are where §8.5 decided the field-level error lives, so they have to be able to read
this. ``app/utils/description_rule.py`` is the precedent and the same shape: a domain rule
that runs on two sides and must agree, read by a DTO module and by services alike. Neither
this file nor ``resource_request_totals.py`` holds logic or touches the database, so
nothing about them wanted the service layer in the first place.

Everything below either reads that file or is asserted against it by
``tests/test_resource_requests/test_vocabularies.py``.

**One thing is written here rather than read, and it is the section→field map.** The
emission carries the per-type composition of Parte A and Parte B, because those are
data structures in the frontend; it cannot carry *which* of the 45 text keys each
section owns, because over there the keys sit inline in the components and the only
statement of the mapping is prose in the contract's §1.2. Emitting it would be
inventing it. So it lives in ``SECTION_TEXT_FIELDS``, and the test cross-checks it from
both ends: the 45 emitted keys are partitioned exactly by this map plus the three
evaluation keys, and every section id the map names appears in the emitted composition.
A new question on the form fails there instead of passing quietly.
"""

import json
from functools import cache
from pathlib import Path
from typing import Any

_EMISSION: dict[str, Any] = json.loads(
    (Path(__file__).parent / "resource_request_vocabularies.json").read_text(encoding="utf-8")
)

EMITTED_FROM: str = _EMISSION["emitted_from"]

REQUEST_TYPES: tuple[str, ...] = tuple(_EMISSION["requestTypes"])
TEXT_FIELD_KEYS: frozenset[str] = frozenset(_EMISSION["textFieldKeys"])
BUDGET_CATEGORY_KEYS: tuple[str, ...] = tuple(c["key"] for c in _EMISSION["budgetCategories"])
FUND_IDS: frozenset[str] = frozenset(f["id"] for f in _EMISSION["funds"])
BOARD_STATUS_IDS: tuple[str, ...] = tuple(s["id"] for s in _EMISSION["boardStatuses"])

CRITERION_KEYS: dict[str, tuple[str, ...]] = {
    request_type: tuple(c["key"] for c in criteria)
    for request_type, criteria in _EMISSION["criteriaByType"].items()
}

#: The keys one row of each growing table may carry. Emitted from the frontend's own
#: empty-row seeds, which is what a stored row is rebuilt from over there — a key
#: outside them does not survive a round trip on that side either. The budget is absent
#: because its row is not keyed by column: the category is the key, and it arrives as
#: ``category_key`` on a typed line.
TABLE_ROW_KEYS: dict[str, frozenset[str]] = {
    table: frozenset(keys) for table, keys in _EMISSION["tableRowKeys"].items()
}

PART_A_SECTIONS: dict[str, tuple[dict[str, Any], ...]] = {
    request_type: tuple(sections) for request_type, sections in _EMISSION["partASections"].items()
}
PART_B_SECTIONS: dict[str, tuple[dict[str, Any], ...]] = {
    request_type: tuple(sections)
    for request_type, sections in _EMISSION["partBComposition"].items()
}

_VOCABULARY_OPTIONS: dict[str, tuple[str, ...]] = {
    name: tuple(option["value"] for option in options)
    for name, options in _EMISSION["vocabularies"].items()
}

MAX_SCORE_PER_CRITERION: int = _EMISSION["limits"]["maxScorePerCriterion"]
MAX_TOTAL_SCORE: int = _EMISSION["limits"]["maxTotalScore"]
CRITERIA_PER_TYPE: int = _EMISSION["limits"]["criteriaPerType"]

#: Parte C's three text keys. They are among the emitted 45 because wave 1 keeps the
#: evaluation inside the draft — and that is the one shape wave 2 must not copy
#: (``docs/resource_requests.md`` §4.1), so they are named apart from the request's own
#: fields rather than mixed into ``SECTION_TEXT_FIELDS``.
EVALUATION_TEXT_FIELDS: frozenset[str] = frozenset(
    {"board_comments", "board_evaluator", "board_evaldate"}
)

#: Section slot → the text keys that section asks. Parte A's slots carry the variant
#: where the composition does (``A1`` renders twelve keys full and four slim; ``A4``
#: only asks ``team_avg_participants`` where the composition sets
#: ``averageParticipants``). Parte B's sections 2 to 5 are absent on purpose: each
#: carries its own ``field`` in the emission, which is the same fact from the source.
SECTION_TEXT_FIELDS: dict[str, tuple[str, ...]] = {
    "A0": ("reg_name",),
    "A1:full": (
        "lang_name",
        "lang_iso",
        "lang_family",
        "lang_dialects",
        "lang_speakers",
        "lang_vitality",
        "lang_script",
        "lang_literacy",
        "lang_existing",
        "eten_listed",
        "eten_goal",
        "eten_notes",
    ),
    "A1:slim": ("tr_location", "tr_eten_listed", "tr_leader", "tr_mentor"),
    "A2": (
        "people_name",
        "people_pop",
        "people_location",
        "people_religion",
        "people_christians",
        "people_church",
        "people_context",
    ),
    "A3": (
        "contact_time",
        "contact_who",
        "contact_history",
        "recv_requested",
        "recv_who",
        "recv_attitude",
    ),
    "A4": (),
    "A4:avg": ("team_avg_participants",),
    "A5": (),
    "6": (),
    "7": (),
    "8·9": ("amount_requested", "attachment_note"),
    "11": ("tpp_name", "tpp_date", "leader_name", "leader_date"),
}

#: The five Parte A fields whose ``<select>`` vocabulary lives inline in a component
#: over there and therefore in no emitted structure. Sections 2's two are not here:
#: they ride on the section itself (``vocabulary``), which is the source's own statement.
_PART_A_VOCABULARY_BY_FIELD: dict[str, str] = {
    "lang_script": "writingSystem",
    "eten_listed": "etenListed",
    "eten_goal": "allAccessGoal",
    "people_church": "localChurch",
    "recv_requested": "requestedByPeople",
    "tr_eten_listed": "etenListed",
}


def _vocabulary_by_field() -> dict[str, tuple[str, ...]]:
    by_field = {
        field: _VOCABULARY_OPTIONS[name] for field, name in _PART_A_VOCABULARY_BY_FIELD.items()
    }
    for sections in PART_B_SECTIONS.values():
        for section in sections:
            if "vocabulary" in section:
                by_field[section["field"]] = _VOCABULARY_OPTIONS[section["vocabulary"]]
    return by_field


#: Field key → the values that field accepts. Portuguese labels for the seven lists the
#: frontend has not keyed yet: what a client sends today is what the server validates,
#: and the contract's §5.2 carries the gap and its owner.
VOCABULARY_VALUES: dict[str, tuple[str, ...]] = _vocabulary_by_field()

CHECK_VALUES: dict[str, tuple[str, ...]] = {
    "teamtype": _VOCABULARY_OPTIONS["trainedTeamTypes"],
    "trainformat": _VOCABULARY_OPTIONS["trainingFormats"],
}


def _slots(request_type: str) -> tuple[str, ...]:
    slots = []
    for section in PART_A_SECTIONS[request_type]:
        slot = section["id"]
        if slot == "A1":
            slot = f"A1:{section['variant']}"
        elif slot == "A4" and section.get("averageParticipants"):
            slot = "A4:avg"
        slots.append(slot)
    slots.extend(section["id"] for section in PART_B_SECTIONS[request_type])
    return tuple(slots)


@cache
def section_field_keys(request_type: str) -> frozenset[str]:
    """Every text key the sections of ``request_type`` actually render.

    A key outside this set was never asked of that type, which the contract separates
    from asked-and-left-blank: the mesa reads the difference, so a submission carrying
    one is refused rather than stored as if the question had been put.
    """
    keys: set[str] = set()
    for slot in _slots(request_type):
        keys.update(SECTION_TEXT_FIELDS.get(slot, ()))
    for section in PART_B_SECTIONS[request_type]:
        if "field" in section:
            keys.add(section["field"])
    return frozenset(keys)


#: What a **submission** must carry, per type. Not the same question as what a section
#: renders: the contract's *empty means not answered* is the norm for the profile — the
#: mesa reads a blank — so this list stays as short as the request itself allows. It is
#: the project's name, what the request is for, the three essays the Parte C criteria
#: score, the amount asked, and the requester's name. Everything in A1, A2 and A3 may be
#: submitted blank.
#:
#: **The paper form's signature block is not in this set, and the client moved it out**
#: (OBT-483, 28/aug/2026): the Ponto focal's signature is an *aceite eletrônico* —
#: submitting **is** signing, and ``created_by`` plus ``submitted_at`` are the who and
#: the when, both stamped by the server. So ``tpp_date`` asks the client to type what
#: the server already knows, and ``leader_name``/``leader_date`` belong to the Líder's
#: endorsement (BE-16), not to the team's typing. The three **columns** stay on
#: ``rr_requests`` and the three keys stay askable — a draft may carry them — they are
#: just no longer demanded. ``tpp_name`` stays: it is the requester the mesa reads on
#: the card, and the account that submits may not be the Ponto focal.
#:
#: **This set is BE-05's reading, not a requirement the PRD enumerates field by field.**
#: It lives in one place so the client can move it in one place.
_ALWAYS_REQUIRED: tuple[str, ...] = (
    "reg_name",
    "why_needed",
    "proj_goals",
    "funds_support",
    "amount_requested",
    "tpp_name",
)


def _required_for(request_type: str) -> frozenset[str]:
    required = set(_ALWAYS_REQUIRED)
    for section in PART_B_SECTIONS[request_type]:
        if section["id"] == "2":
            required.add(section["field"])
    return frozenset(required)


REQUIRED_TEXT_FIELDS: dict[str, frozenset[str]] = {
    request_type: _required_for(request_type) for request_type in REQUEST_TYPES
}

#: Which types render a team table at all, read off the composition rather than listed:
#: ``equipamentos`` has no A4 section, so it must send no team rows.
TYPES_WITH_TEAM: frozenset[str] = frozenset(
    request_type
    for request_type in REQUEST_TYPES
    if any(section["id"] == "A4" for section in PART_A_SECTIONS[request_type])
)

#: Same, for A5's two checkbox sets — ``treinamento`` alone.
TYPES_WITH_TRAINING_PROFILE: frozenset[str] = frozenset(
    request_type
    for request_type in REQUEST_TYPES
    if any(section["id"] == "A5" for section in PART_A_SECTIONS[request_type])
)

#: Same, for section 6's schedule table. All three render it today; reading it off the
#: composition rather than saying so keeps the three tables answering one question.
TYPES_WITH_CHRONO: frozenset[str] = frozenset(
    request_type
    for request_type in REQUEST_TYPES
    if any(section["id"] == "6" for section in PART_B_SECTIONS[request_type])
)

#: Same, for A1's table of language names. It is the *slim* variant that renders it, so
#: this reads the variant and not the section id: all three types render A1, and
#: ``traducao`` renders the full one, which asks its language in twelve text fields and
#: has no table at all.
TYPES_WITH_LANGS: frozenset[str] = frozenset(
    request_type
    for request_type in REQUEST_TYPES
    if any(
        section["id"] == "A1" and section.get("variant") == "slim"
        for section in PART_A_SECTIONS[request_type]
    )
)


#: Table → the types that render it, so the three growing tables answer the *asked* half
#: of the rule from one place. The *answerable* half is ``TABLE_ROW_KEYS`` above.
TYPES_WITH_TABLE: dict[str, frozenset[str]] = {
    "langs": TYPES_WITH_LANGS,
    "team": TYPES_WITH_TEAM,
    "chrono": TYPES_WITH_CHRONO,
}

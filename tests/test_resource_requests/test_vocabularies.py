"""The contract-sync check BE-05's DoD asks for.

It runs here and not on the frontend for one reason the design records (§9): `test.yml`
runs `pytest tests/ -v` on every pull request in this repository, while over there CI
runs ESLint, `tsc -b`, `check:tokens` and `check:i18n` and **not** the test suite. So an
assertion written on that side would guard no pull request, and the load-bearing copy of
this check has to live where it actually runs.

Two shapes of assertion, and the second is the one that catches a moving form. The
checksums are the numbers the design lists, read off the vendored emission. The
partition is the cross-check for the one map this repository writes by hand — the
section → field-keys map, which exists here because over there the keys sit inline in
components and nothing states the mapping as data.
"""

import json
from pathlib import Path

import pytest

from app.db.models.resource_request import RRCurrency, RRDecision, RRRequestType, RRStage
from app.utils import resource_request_vocabularies as v

EMISSION = json.loads(
    (Path(v.__file__).parent / "resource_request_vocabularies.json").read_text(encoding="utf-8")
)


def test_the_emission_says_where_it_came_from():
    """Without it, a copy older than the contract is invisible instead of reviewable."""
    assert v.EMITTED_FROM
    assert not v.EMITTED_FROM.endswith("-dirty"), (
        "emitida com fonte não commitada — o commit citado não contém o que está aqui"
    )


@pytest.mark.parametrize(
    ("what", "expected", "actual"),
    [
        ("text field keys", 45, lambda: len(v.TEXT_FIELD_KEYS)),
        ("project categories", 9, lambda: len(EMISSION["vocabularies"]["projectCategory"])),
        ("supported goals", 10, lambda: len(EMISSION["vocabularies"]["supportedGoal"])),
        ("budget categories", 26, lambda: len(v.BUDGET_CATEGORY_KEYS)),
        ("funds", 1, lambda: len(EMISSION["funds"])),
        ("board columns", 6, lambda: len(v.BOARD_STATUS_IDS)),
        ("decisions", 4, lambda: len(EMISSION["vocabularies"]["decisionStates"])),
        ("request types", 3, lambda: len(v.REQUEST_TYPES)),
        ("max total score", 30, lambda: v.MAX_TOTAL_SCORE),
        ("max score per criterion", 5, lambda: v.MAX_SCORE_PER_CRITERION),
    ],
)
def test_the_checksums_of_the_design(what, expected, actual):
    """§9's list, verbatim. A list that comes back a different length fails here.

    ``funds`` was 5 until GATE-01 answered (OBT-447, 26/aug/2026) and is read straight off
    the emission since BE-10 (OBT-471), which is the whole of that issue's answer to *what
    becomes of ``FUND_IDS``*: a fund is now a row the Gestor creates, so the emitted list
    can never be the valid set and a named constant would be a validation list waiting to
    be misused. Checksummed anyway — the number moving is what makes a stale vendored copy
    visible, which is the whole job of a checksum over data emitted somewhere else.
    """
    assert actual() == expected, what


def test_six_criteria_per_type_and_no_key_shared_between_them():
    """The type prefix is what makes the second half true.

    *Vínculo com um projeto de tradução ativo* is criterion 2 of both `treinamento` and
    `equipamentos`; unprefixed, the eighteen would be seventeen and one type's score
    would land on another's criterion.
    """
    minted = [key for keys in v.CRITERION_KEYS.values() for key in keys]

    assert set(v.CRITERION_KEYS) == set(v.REQUEST_TYPES)
    for request_type, keys in v.CRITERION_KEYS.items():
        assert len(keys) == v.CRITERIA_PER_TYPE
        assert all(key.startswith(f"{request_type}_") for key in keys)
    assert len(minted) == len(set(minted)) == 18


def test_every_growing_table_carries_its_columns_and_its_types():
    """Both halves of the *asked and answerable* rule for the three tables.

    They are emitted rather than written here for the same reason the 26 categories are:
    a column list typed on this side is the second source the mirror exists to prevent.
    ``TYPES_WITH_TABLE`` is read off the same composition ``section_field_keys`` reads,
    so a type that stops rendering a table stops accepting its rows in the same emission.
    """
    assert set(v.TABLE_ROW_KEYS) == set(v.TYPES_WITH_TABLE) == {"langs", "team", "chrono"}
    for table, columns in v.TABLE_ROW_KEYS.items():
        assert columns, table
        assert v.TYPES_WITH_TABLE[table] <= set(v.REQUEST_TYPES)

    assert v.TYPES_WITH_TABLE["langs"] == {"treinamento", "equipamentos"}
    assert v.TYPES_WITH_TABLE["team"] == v.TYPES_WITH_TEAM
    assert v.TYPES_WITH_TABLE["chrono"] == set(v.REQUEST_TYPES)


def test_the_budget_is_not_among_the_keyed_row_tables():
    """Its row is not keyed by column — the category is the key, and it travels typed."""
    assert "budget" not in v.TABLE_ROW_KEYS


def test_the_budget_keys_are_unique():
    assert len(set(v.BUDGET_CATEGORY_KEYS)) == len(v.BUDGET_CATEGORY_KEYS)


@pytest.mark.parametrize(
    ("enum_cls", "emitted"),
    [
        (RRRequestType, lambda: EMISSION["requestTypes"]),
        (RRStage, lambda: [s["id"] for s in EMISSION["boardStatuses"]]),
        (RRDecision, lambda: [d["value"] for d in EMISSION["vocabularies"]["decisionStates"]]),
        (RRCurrency, lambda: None),
    ],
)
def test_be_02s_enums_are_the_frontends_lists(enum_cls, emitted):
    """Three of BE-02's four enums are the frontend's lists, member for member and in order.

    `RRCurrency` is the fourth and is deliberately **not** one of them: the frontend
    persists the symbol (`R$`) and the server stores ISO-4217, a departure §7.2 of the
    design decided and the contract records. What is asserted instead is that the two
    lists are the same size, so a fourth currency over there cannot arrive here as a
    value nothing maps.
    """
    members = [member.value for member in enum_cls]
    if emitted() is None:
        assert len(members) == len(EMISSION["vocabularies"]["currencies"])
    else:
        assert members == list(emitted())


def test_the_45_keys_are_partitioned_by_the_hand_written_map():
    """The cross-check for the one thing here that the emission cannot carry.

    Every emitted text key belongs to exactly one place: a Parte A section slot, a Parte
    B section's own `field`, one of the four slots of Parte B that have keys and no
    field, or the evaluation. A new question on the form arrives as a key belonging to
    nothing and fails here, instead of being silently unvalidated.
    """
    mapped = [key for keys in v.SECTION_TEXT_FIELDS.values() for key in keys]
    from_b_sections = [
        section["field"]
        for sections in v.PART_B_SECTIONS.values()
        for section in sections
        if "field" in section
    ]

    assert len(mapped) == len(set(mapped)), "uma chave em duas seções"
    covered = set(mapped) | set(from_b_sections) | v.EVALUATION_TEXT_FIELDS

    assert covered == v.TEXT_FIELD_KEYS
    assert set(mapped) & v.EVALUATION_TEXT_FIELDS == set()


def test_every_slot_is_owned_by_exactly_one_of_the_two_mechanisms():
    """Both directions, and the split between them is the point.

    A slot the map names but the emitted composition no longer renders is a row here
    guarding a section that was removed over there. And a rendered slot owned by
    neither the map nor its own `field` is a section whose answers nothing validates —
    which is what a new Parte B card would look like arriving.
    """
    emitted_slots = {slot for request_type in v.REQUEST_TYPES for slot in v._slots(request_type)}
    with_own_field = {
        section["id"]
        for sections in v.PART_B_SECTIONS.values()
        for section in sections
        if "field" in section
    }

    assert set(v.SECTION_TEXT_FIELDS) <= emitted_slots, "linha órfã no mapa"
    assert emitted_slots - set(v.SECTION_TEXT_FIELDS) == with_own_field, "seção sem dono"
    assert set(v.SECTION_TEXT_FIELDS) & with_own_field == set(), "seção com dois donos"


def test_what_each_type_asks_matches_the_contracts_own_counts():
    """36 / 16 / 15, and their union is the 42 keys that are not the evaluation's."""
    asked = {t: v.section_field_keys(t) for t in v.REQUEST_TYPES}

    assert {t: len(keys) for t, keys in asked.items()} == {
        "traducao": 36,
        "treinamento": 16,
        "equipamentos": 15,
    }
    assert set().union(*asked.values()) == v.TEXT_FIELD_KEYS - v.EVALUATION_TEXT_FIELDS


def test_only_traducao_asks_the_people_and_contact_sections():
    """A2 and A3 belong to `traducao` alone — the per-type variation, read from the map."""
    assert "people_name" in v.section_field_keys("traducao")
    assert "people_name" not in v.section_field_keys("treinamento")
    assert "contact_time" not in v.section_field_keys("equipamentos")
    assert set(v.TYPES_WITH_TEAM) == {"traducao", "treinamento"}
    assert set(v.TYPES_WITH_TRAINING_PROFILE) == {"treinamento"}


def test_every_field_with_a_vocabulary_is_one_of_the_45():
    """A mapped field that no section asks would be a rule guarding nothing."""
    assert set(v.VOCABULARY_VALUES) <= v.TEXT_FIELD_KEYS
    assert set(v.REQUIRED_TEXT_FIELDS) == set(v.REQUEST_TYPES)
    for request_type, required in v.REQUIRED_TEXT_FIELDS.items():
        assert required <= v.section_field_keys(request_type)

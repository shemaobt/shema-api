import enum
from pathlib import Path
from unittest.mock import patch

from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room import coverage
from app.services.internalization_room._default_prompts import (
    default_prompt,
    fail_safe_utterances,
)
from app.services.internalization_room.canon.elements import (
    Element,
    ElementKind,
    element_keys,
    elements_for,
)
from app.services.internalization_room.coverage import (
    CoverageStatus,
    counts,
    floor_met,
    furthest,
    initial_state,
    merge,
    remaining,
)
from app.services.internalization_room.fail_safe import FailSafe, utterances

P = "P03"
_VENDOR = Path("app/services/internalization_room/prompts/vendor")


def test_a_fresh_session_has_encountered_nothing() -> None:
    state = initial_state(P)

    assert set(state) == set(element_keys(P))
    assert counts(state) == {"engaged": 0, "surfaced": 0, "total": len(element_keys(P))}
    assert floor_met(state, P) is False


def test_the_spine_is_the_passage_itself_not_a_fixed_list() -> None:
    """Each pericope carries its own beads, derived from its map."""
    assert len(element_keys("P03")) != len(element_keys("P06"))
    assert all(len(element_keys(f"P{i:02d}")) > 0 for i in range(1, 15))


def test_every_kind_the_completion_floor_names_is_present() -> None:
    kinds = {element.kind for element in elements_for(P)}

    assert ElementKind.SCENE in kinds
    assert ElementKind.BEING in kinds
    assert ElementKind.ABSENCE in kinds
    assert ElementKind.PRESERVED in kinds


def test_an_entity_in_three_scenes_is_one_bead() -> None:
    """Naomi appears in every scene of P03; the team works with her once."""
    beings = [e for e in elements_for(P) if e.kind is ElementKind.BEING]

    assert len(beings) == len({e.key for e in beings})
    assert any(e.key == "being:B3" for e in beings)


def test_the_same_place_written_differently_is_one_bead() -> None:
    """`the road (implied; continues from P02)` and `the road (continued)` are one road."""
    places = [e for e in elements_for(P) if e.kind is ElementKind.PLACE]

    assert sum(1 for e in places if e.key == "place:the-road") == 1


def test_coverage_never_moves_backwards() -> None:
    state = merge(initial_state(P), pericope_num=P, engaged=["being:B9"])
    state = merge(state, pericope_num=P, surfaced=["being:B9"])

    assert state["being:B9"] == "engaged"


def test_surfaced_counts_elements_the_team_has_not_worked_yet() -> None:
    state = merge(
        initial_state(P),
        pericope_num=P,
        surfaced=["scene:1", "scene:2"],
        engaged=["scene:1"],
    )

    assert counts(state)["surfaced"] == 2
    assert counts(state)["engaged"] == 1


def test_keys_that_are_not_in_this_passage_are_ignored() -> None:
    state = merge(initial_state(P), pericope_num=P, engaged=["being:B999"])

    assert "being:B999" not in state


def test_the_floor_needs_every_element_engaged() -> None:
    keys = element_keys(P)

    surfaced_only = merge(initial_state(P), pericope_num=P, surfaced=keys)
    assert floor_met(surfaced_only, P) is False

    all_but_one = merge(initial_state(P), pericope_num=P, engaged=keys[:-1])
    assert floor_met(all_but_one, P) is False
    assert [element.key for element in remaining(all_but_one, P)] == [keys[-1]]

    whole = merge(initial_state(P), pericope_num=P, engaged=keys)
    assert floor_met(whole, P) is True
    assert remaining(whole, P) == []


def test_a_significant_absence_is_not_exempt_from_the_floor() -> None:
    """Merely surfacing an absence must never let a session complete."""
    absences = [e.key for e in elements_for(P) if e.kind is ElementKind.ABSENCE]
    others = [key for key in element_keys(P) if key not in absences]

    state = merge(initial_state(P), pericope_num=P, engaged=others, surfaced=absences)

    assert floor_met(state, P) is False


def test_a_preserved_element_is_not_exempt_either() -> None:
    preserved = [e.key for e in elements_for(P) if e.kind is ElementKind.PRESERVED]
    others = [key for key in element_keys(P) if key not in preserved]

    state = merge(initial_state(P), pericope_num=P, engaged=others, surfaced=preserved)

    assert preserved
    assert floor_met(state, P) is False


def test_every_role_has_a_prompt_body() -> None:
    for key in IRPromptKey:
        prompt = default_prompt(key)
        assert prompt["prompt"].strip()
        assert prompt["name"]


def test_the_guide_prompt_carries_its_placeholders() -> None:
    guide = default_prompt(IRPromptKey.GUIDE)["prompt"]

    for placeholder in ("{{SESSION_LANGUAGE}}", "{{MEANING_MAP}}", "{{COVERAGE_STATUS}}"):
        assert placeholder in guide


def test_fail_safe_utterances_are_available_to_the_app() -> None:
    assert fail_safe_utterances().strip()


def test_no_fail_safe_ever_falls_back_to_english() -> None:
    """The room speaks Portuguese. A section without a `-pt` block would have the Facilitator
    switch language at the worst moment — a question it cannot answer, a handoff, a hard stop.
    """
    for kind in FailSafe:
        in_pt = utterances(kind, "pt")
        assert in_pt, f"{kind.name} has no lines at all"
        assert in_pt != utterances(kind, "en"), f"{kind.name} would be spoken in English"


def test_the_handoff_does_not_read_as_the_app_itself() -> None:
    """The app is `o Facilitador Digital`; a bare `o facilitador` would point at itself."""
    for line in utterances(FailSafe.HANDOFF, "pt") + utterances(FailSafe.HARD_STOP, "pt"):
        assert "facilitador de vocês" in line or "Facilitador Digital" not in line


def test_two_readings_of_the_same_spine_keep_the_further_one() -> None:
    """Two turns overlapping is ordinary, and the older reading used to win.

    The classifier for one turn takes a round trip; the next turn can land and settle
    while it runs. Writing a whole snapshot over what is stored darkened a bead the team
    had just earned, and the room asked them to work an element they had covered.
    """
    keys = element_keys(P)
    earned = dict.fromkeys(keys, CoverageStatus.NOT_ENCOUNTERED.value)
    earned[keys[0]] = CoverageStatus.ENGAGED.value

    stale = dict.fromkeys(keys, CoverageStatus.NOT_ENCOUNTERED.value)
    stale[keys[1]] = CoverageStatus.SURFACED.value

    kept = furthest(earned, stale, pericope_num=P)

    assert kept[keys[0]] == CoverageStatus.ENGAGED.value, (
        "a leitura velha sobrescrevia a conta que a equipe acabou de ganhar"
    )
    assert kept[keys[1]] == CoverageStatus.SURFACED.value


_SCALE = [
    CoverageStatus.NOT_ENCOUNTERED,
    CoverageStatus.PARTIALLY_ENGAGED,
    CoverageStatus.SURFACED,
    CoverageStatus.ENGAGED,
]

_BUCKET = {
    CoverageStatus.SURFACED: "surfaced",
    CoverageStatus.ENGAGED: "engaged",
}


def _spine_at(status: CoverageStatus) -> dict[str, str]:
    return dict.fromkeys(element_keys(P), status.value)


def _with(overrides: dict[str, CoverageStatus]) -> dict[str, str]:
    return {**initial_state(P), **{key: status.value for key, status in overrides.items()}}


def test_a_merge_moves_a_bead_forward_or_leaves_it_across_the_whole_scale() -> None:
    """Every ordered pair, not three hand-picked ones — the two buckets the room still writes
    against every state a row can hold, and a scale is only monotonic if it is monotonic
    everywhere.
    """
    key = element_keys(P)[0]

    for standing in _SCALE:
        for told, bucket in _BUCKET.items():
            moved = merge(_with({key: standing}), pericope_num=P, **{bucket: [key]})
            expected = told if _SCALE.index(told) > _SCALE.index(standing) else standing

            assert moved[key] == expected.value, (
                f"{standing.value} + {told.value} deveria ficar em {expected.value}"
            )


def test_the_further_of_two_readings_wins_across_the_whole_scale() -> None:
    """`furthest` is the other one-way path — it runs when two settles overlap."""
    key = element_keys(P)[0]

    for kept_status in _SCALE:
        for told_status in _SCALE:
            kept = furthest(_with({key: kept_status}), _with({key: told_status}), pericope_num=P)
            expected = max(kept_status, told_status, key=_SCALE.index)

            assert kept[key] == expected.value, (
                f"guardado {kept_status.value}, contado {told_status.value}"
            )


def test_the_floor_refuses_a_bead_the_team_only_partly_worked() -> None:
    """Hard Rule #2: only `engaged` counts for coverage. A bead written under the retired
    status is a bead the team took up on the Guide's terms, and that is `surfaced`.
    """
    keys = element_keys(P)
    half = len(keys) // 2
    mixed = _with(
        {
            **dict.fromkeys(keys[:half], CoverageStatus.PARTIALLY_ENGAGED),
            **dict.fromkeys(keys[half:], CoverageStatus.ENGAGED),
        }
    )

    assert floor_met(mixed, P) is False
    assert floor_met(_spine_at(CoverageStatus.PARTIALLY_ENGAGED), P) is False
    assert floor_met(_spine_at(CoverageStatus.SURFACED), P) is False
    assert floor_met(_spine_at(CoverageStatus.ENGAGED), P) is True


def test_a_preservation_rule_the_team_only_echoed_does_not_close_the_passage() -> None:
    """The case the fourth state existed for, reversed.

    A team engages a preservation rule by noticing a silence, and the echo of the Guide's
    noticing is that engagement — her classifier writes it `engaged`, so the floor has no
    reason left to meet the echo halfway. What still stands at the retired status is a bead
    the ledger has not seen the team take up.
    """
    preserved = [e.key for e in elements_for(P) if e.kind is ElementKind.PRESERVED]
    others = [key for key in element_keys(P) if key not in preserved]
    echoed = _with(
        {
            **dict.fromkeys(others, CoverageStatus.ENGAGED),
            **dict.fromkeys(preserved, CoverageStatus.PARTIALLY_ENGAGED),
        }
    )

    assert preserved
    assert floor_met(echoed, P) is False


def test_a_level_one_axis_meets_the_floor_at_surfaced_and_nothing_else_does() -> None:
    """Her one exemption: "all four Level-1 elements at least `surfaced`" (build_spec.md:333).

    The enum does not hold the four kinds yet — that slice is ENG-752 — so the exemption
    is read off the kind's value, and this case hands the floor a kind this build does
    not know, the way the ledger will receive it.
    """

    class AxisKind(enum.StrEnum):
        ARC = "arc"

    axis = Element.model_construct(key="arc", label="Level-1 arc", kind=AxisKind.ARC, scene=None)
    concrete = elements_for(P)[0]
    spine = [axis, concrete]
    with_the_axis = {**initial_state(P), "arc": CoverageStatus.SURFACED.value}

    with patch.object(coverage, "elements_for", return_value=spine):
        assert floor_met({**with_the_axis, concrete.key: "engaged"}, P) is True
        assert floor_met({**with_the_axis, concrete.key: "surfaced"}, P) is False
        assert floor_met(
            {**with_the_axis, "arc": "not_encountered", concrete.key: "engaged"}, P
        ) is (False)


def test_a_partly_worked_bead_stays_in_the_set_the_classifier_is_shown() -> None:
    state = _spine_at(CoverageStatus.PARTIALLY_ENGAGED)

    assert {element.key for element in remaining(state, P)} == set(element_keys(P))


def test_a_partly_worked_bead_counts_as_encountered_but_not_as_worked() -> None:
    keys = element_keys(P)
    state = _with(
        {
            keys[0]: CoverageStatus.SURFACED,
            keys[1]: CoverageStatus.PARTIALLY_ENGAGED,
            keys[2]: CoverageStatus.ENGAGED,
        }
    )

    assert counts(state) == {"engaged": 1, "surfaced": 3, "total": len(keys)}


def test_a_tracker_written_before_the_fourth_state_reads_the_same() -> None:
    """What a stored row holds is these three strings, because nothing had yet written the
    fourth — and nothing writes it again. An all-surfaced session still does not close.
    """
    keys = element_keys(P)
    old_row = {**dict.fromkeys(keys, "not_encountered"), keys[0]: "surfaced", keys[1]: "engaged"}

    assert counts(old_row) == {"engaged": 1, "surfaced": 2, "total": len(keys)}
    assert floor_met(old_row, P) is False
    assert floor_met(dict.fromkeys(keys, "surfaced"), P) is False
    assert floor_met(dict.fromkeys(keys, "engaged"), P) is True
    assert {element.key for element in remaining(old_row, P)} == set(keys) - {keys[1]}
    assert merge(old_row, pericope_num=P, surfaced=[keys[1]])[keys[1]] == "engaged"


def test_the_classifier_prompt_is_her_three_status_text() -> None:
    """Every line between her markers, and nothing of ours.

    The fourth status was ours: a band for the echo, and a floor lowered to meet it. What
    is served now is the vendored copy read back between `=== BEGIN SYSTEM PROMPT ===` and
    `=== END SYSTEM PROMPT ===`, so a word of ours creeping back in is a diff against her
    file, not a judgment call.
    """
    vendored = (_VENDOR / "classifier_system_prompt.md").read_text(encoding="utf-8")
    hers = vendored.split("`=== BEGIN SYSTEM PROMPT ===`", 1)[1]
    hers = hers.split("`=== END SYSTEM PROMPT ===`", 1)[0].strip("\n") + "\n"

    assert default_prompt(IRPromptKey.COVERAGE_CLASSIFIER)["prompt"] == hers


def test_the_classifier_prompt_makes_an_echoed_silence_engaged() -> None:
    """Her rule for the absences, word for word, and the legacy state nowhere in it.

    Ours said the opposite: taking up the Guide's noticing was `partially_engaged`, and only
    noticing the silence unprompted was `engaged` — which is how the five silences of Ruth 1
    became beads a team could never fill.
    """
    prompt = default_prompt(IRPromptKey.COVERAGE_CLASSIFIER)["prompt"]

    assert (
        'The Guide raising "notice the story never says God did this" = surfaced; '
        "the team responding to or echoing that noticing = engaged."
    ) in prompt, "a regra do eco de ausência não é a dela"
    assert "partially_engaged" not in prompt, "o quarto estado voltou ao prompt"

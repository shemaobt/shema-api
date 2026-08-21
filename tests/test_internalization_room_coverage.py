from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import (
    default_prompt,
    fail_safe_utterances,
)
from app.services.internalization_room.canon.elements import (
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

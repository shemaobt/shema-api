"""The one-shot oral calibration and the explicit-only mode switch.

The parser recognizes only clear task-shaped preferences; anything unclear falls to the
modest adaptive track at the one-shot boundary and the Voice never re-offers the menu.
"""

from app.services.internalization_room.calibration import (
    BRIDGE_CALIBRATION_QUESTION,
    BridgeMode,
    bridge_calibration_acknowledgement,
    is_selected_bridge_mode,
    resolve_bridge_mode_for_turn,
    resolve_initial_calibration,
    resolve_one_shot_calibration,
)


def test_a_clear_full_retell_preference_is_explicit() -> None:
    resolved = resolve_initial_calibration("Conseguimos contar a história em português.")
    assert resolved.mode is BridgeMode.FULL_RETELL
    assert resolved.explicit


def test_a_short_questions_preference_selects_guided() -> None:
    resolved = resolve_initial_calibration("Preferimos perguntas curtas, uma de cada vez.")
    assert resolved.mode is BridgeMode.GUIDED_MICROCHECKS
    assert resolved.explicit


def test_naming_the_second_option_selects_guided() -> None:
    assert resolve_initial_calibration("a segunda").mode is BridgeMode.GUIDED_MICROCHECKS


def test_uncertainty_followed_by_a_trial_selects_adaptive() -> None:
    resolved = resolve_initial_calibration("Não sabemos, vamos tentar.")
    assert resolved.mode is BridgeMode.ADAPTIVE


def test_both_preferences_in_one_answer_are_adaptive() -> None:
    resolved = resolve_initial_calibration(
        "Podemos contar a história inteira, mas também queremos perguntas curtas."
    )
    assert resolved.mode is BridgeMode.ADAPTIVE


def test_a_negated_capability_is_not_the_positive_choice() -> None:
    resolved = resolve_initial_calibration("Não conseguimos contar tudo em português.")
    assert resolved.mode is BridgeMode.CALIBRATION_PENDING


def test_negating_one_option_still_selects_the_other() -> None:
    resolved = resolve_initial_calibration(
        "Não conseguimos contar a história toda; preferimos perguntas curtas."
    )
    assert resolved.mode is BridgeMode.GUIDED_MICROCHECKS


def test_a_question_back_resolves_nothing() -> None:
    resolved = resolve_initial_calibration("O que acontece se a gente errar?")
    assert resolved.mode is BridgeMode.CALIBRATION_PENDING
    assert not resolved.explicit


def test_the_one_shot_boundary_converts_silence_to_adaptive() -> None:
    resolved = resolve_one_shot_calibration("")
    assert resolved.mode is BridgeMode.ADAPTIVE
    assert not resolved.explicit


def test_the_one_shot_boundary_converts_an_unclear_answer_to_adaptive() -> None:
    assert resolve_one_shot_calibration("hmm, sei lá").mode is BridgeMode.ADAPTIVE


def test_the_one_shot_boundary_keeps_an_explicit_answer() -> None:
    resolved = resolve_one_shot_calibration("queremos contar tudo")
    assert resolved.mode is BridgeMode.FULL_RETELL
    assert resolved.explicit


def test_story_speech_never_switches_an_established_mode() -> None:
    resolved = resolve_bridge_mode_for_turn(
        BridgeMode.GUIDED_MICROCHECKS, "Rute voltou para contar tudo a Noemi"
    )
    assert resolved.mode is BridgeMode.GUIDED_MICROCHECKS
    assert not resolved.explicit


def test_a_bare_sim_never_switches_the_mode() -> None:
    resolved = resolve_bridge_mode_for_turn(BridgeMode.FULL_RETELL, "sim")
    assert resolved.mode is BridgeMode.FULL_RETELL


def test_an_explicit_request_switches_to_guided() -> None:
    resolved = resolve_bridge_mode_for_turn(
        BridgeMode.FULL_RETELL, "preferimos perguntas curtas agora"
    )
    assert resolved.mode is BridgeMode.GUIDED_MICROCHECKS
    assert resolved.explicit


def test_an_explicit_request_switches_back_to_full_retell() -> None:
    resolved = resolve_bridge_mode_for_turn(
        BridgeMode.GUIDED_MICROCHECKS, "queremos contar a história inteira"
    )
    assert resolved.mode is BridgeMode.FULL_RETELL


def test_a_question_about_switching_does_not_switch() -> None:
    resolved = resolve_bridge_mode_for_turn(
        BridgeMode.FULL_RETELL, "Devemos mudar para perguntas curtas?"
    )
    assert resolved.mode is BridgeMode.FULL_RETELL


def test_switching_never_infers_adaptive() -> None:
    resolved = resolve_bridge_mode_for_turn(BridgeMode.FULL_RETELL, "tanto faz, sei lá")
    assert resolved.mode is BridgeMode.FULL_RETELL


def test_only_selected_modes_pass_the_intake_boundary() -> None:
    assert is_selected_bridge_mode("full_retell")
    assert is_selected_bridge_mode("guided_microchecks")
    assert is_selected_bridge_mode("adaptive")
    assert not is_selected_bridge_mode("calibration_pending")
    assert not is_selected_bridge_mode("fluente")
    assert not is_selected_bridge_mode(None)


def test_the_menu_offers_methods_not_ability_labels() -> None:
    lowered = BRIDGE_CALIBRATION_QUESTION.lower()
    for label in ("nível", "básico", "avançado", "fraco", "fluente"):
        assert label not in lowered


def test_every_acknowledgement_is_fixed_and_moves_to_the_panorama() -> None:
    for mode in (BridgeMode.FULL_RETELL, BridgeMode.GUIDED_MICROCHECKS, BridgeMode.ADAPTIVE):
        line = bridge_calibration_acknowledgement(mode)
        assert line.startswith("Certo.")
        assert "panorama do livro" in line

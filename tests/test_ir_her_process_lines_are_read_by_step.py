"""Her process lines mark a step, so they are read by step and never rotated.

A fail-safe answers a failure and varies on purpose — a room that repeats one sentence
sounds like a machine stuck. A process line marks a step of the telling-back or of the
external check, and varying it would voice "Agradecemos sua ajuda" where the step means
"Agora é a vez de quem não ajudou a traduzir". The expected text below is hers, copied
from `shemaobt/Tripod-Internalization` `prompts/fail_safe_utterances.md` on her `main` at
f8f4f64301052a97ba8d8372c7c12cc2ec5e40e3 — not from ours, which would only prove the file
equals itself. Her `main` rather than the vendored copy under `prompts/vendor/`, because
that one is pinned to `fia/pilot-2026-09` 533b6e3f, which carries P and does not carry X
yet; re-pinning the doctrine vendor is not this slice's to do.
"""

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

import scripts.render_fixed_voice_lines as render
from app.services.internalization_room.fail_safe import (
    FailSafe,
    UnknownProcessLine,
    choose,
    first,
    process_line,
)
from app.services.internalization_room.languages import ROOM_LANGUAGES

HER_PROCESS_LINES: dict[tuple[str, str, str], tuple[str, str]] = {
    ("P", "start", "en"): (
        "First let's listen to your whole recording, from beginning to end. For now, just listen.",
        "P0",
    ),
    ("P", "unheard", "pt-BR"): (
        "Ainda falta ouvir um trecho da gravação antes de eu conferir.",
        "P2",
    ),
    ("P", "approved", "en"): (
        "Approved as the team's final draft. It goes to OBT Refine.",
        "P3",
    ),
    ("X", "frases", "en"): (
        "Now, listen to the sentences one by one. When you hear a sentence, if you think "
        "it is good, tap the 'it's good' button. But if you think the sentence needs to "
        "change in some way, or if you think it is not clear, tap the circle again and "
        "make your comment.",
        "X3",
    ),
    ("X", "frases", "pt-BR"): (
        "Agora, escute as frases uma por uma. Quando ouvir uma frase, se achar que ela "
        "está boa, clique no botão 'está boa'. Mas se achar que a frase precisa mudar em "
        "alguma coisa, ou se achar que ela não está clara, clique novamente no círculo e "
        "faça o seu comentário.",
        "X3",
    ),
    ("X", "thanks", "pt-BR"): (
        "Agradecemos sua ajuda. O que vocês disseram fica guardado para a equipe ouvir.",
        "X4",
    ),
}

MODEL_SEAMS: tuple[str, ...] = (
    "app.services.internalization_room.llm",
    "app.services.project_health.agents.llm_client",
)

EVERY_STEP: tuple[tuple[str, str, str], ...] = (
    ("P", "start", "P0"),
    ("P", "tell", "P1"),
    ("P", "unheard", "P2"),
    ("P", "approved", "P3"),
    ("X", "open", "X0"),
    ("X", "retell", "X1"),
    ("X", "whole", "X2"),
    ("X", "frases", "X3"),
    ("X", "thanks", "X4"),
)


def test_the_unheard_line_is_read_by_step_in_portuguese() -> None:
    """The acceptance criterion: the step answers with her line, at any turn, every time."""
    expected = HER_PROCESS_LINES[("P", "unheard", "pt-BR")]

    spoken = [process_line("P", "unheard", "pt-BR") for _ in range(7)]

    assert spoken == [expected] * 7


def test_a_p_step_in_english_is_her_english_line() -> None:
    assert process_line("P", "start", "en") == HER_PROCESS_LINES[("P", "start", "en")]
    assert process_line("P", "approved", "en") == HER_PROCESS_LINES[("P", "approved", "en")]


def test_x_frases_is_always_x_frases() -> None:
    """The step that names the buttons on the screen must never come back as the thanks."""
    assert process_line("X", "frases", "pt-BR") == HER_PROCESS_LINES[("X", "frases", "pt-BR")]
    assert process_line("X", "frases", "en") == HER_PROCESS_LINES[("X", "frases", "en")]
    assert process_line("X", "thanks", "pt-BR") == HER_PROCESS_LINES[("X", "thanks", "pt-BR")]

    repeated = {process_line("X", "frases", "pt-BR") for _ in range(5)}

    assert repeated == {HER_PROCESS_LINES[("X", "frases", "pt-BR")]}


def test_an_unknown_step_or_family_raises_and_never_speaks() -> None:
    """A miss here is a programming error, and a line said at the wrong step is worse.

    `first` answers a miss with `""` because a fail-safe that cannot find its block is
    better silent than wrong; a process step asked for by a name nobody wrote is a caller
    bug, and swallowing it would voice the wrong step or nothing at all.
    """
    with pytest.raises(UnknownProcessLine):
        process_line("P", "frases")
    with pytest.raises(UnknownProcessLine):
        process_line("Q", "open")
    with pytest.raises(UnknownProcessLine):
        process_line("X", "unheard", "pt-BR")


@pytest.mark.parametrize("spoken", ROOM_LANGUAGES)
def test_the_catalogue_lists_the_process_lines_as_never_rendered(
    tmp_path: Path, spoken: str
) -> None:
    """The bundle has no clip for a step yet, and only the catalogue can say so.

    The render script iterated the fail-safe families alone, so the nine process clips were
    invisible to `--check`: a person could edit one of her lines and the guard would stay
    green over audio that no longer says it.
    """
    catalogue = render.catalogue(spoken)
    process_names = {name for _, _, name in EVERY_STEP}

    for family, step, name in EVERY_STEP:
        assert catalogue[name] == process_line(family, step, spoken)[0]

    rendered = {
        name: render.fingerprint(text)
        for name, text in catalogue.items()
        if name not in process_names
    }
    for name in rendered:
        clip = render._clip_path(tmp_path, spoken, name)
        clip.parent.mkdir(parents=True, exist_ok=True)
        clip.write_bytes(b"")
    manifest = render._bundle(tmp_path, spoken) / render.MANIFEST
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(rendered), encoding="utf-8")

    complaints = render.drift(tmp_path, spoken)

    assert set(complaints) == {f"{spoken}/{name}: never rendered" for name in process_names}


def test_no_model_is_reachable_from_a_process_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """Her §6 asks for it and the glossary says it: no model sits on a process line's path.

    Every `call_agent` the server has is replaced, on the module that defines it and on
    every module that imported it, so a call added to this path later cannot answer from a
    reference bound before the fake was installed.

    `choose` and `first` are called under the same fake so the pin is about the module and
    not only about the new function: a model client imported here would put itself on the
    fail-safe path too, which is the one path that has to work when the network is what
    failed.
    """

    def refuse(*_: Any, **__: Any) -> str:
        raise AssertionError("a model was called")

    for defined_in in MODEL_SEAMS:
        importlib.import_module(defined_in)

    poisoned = [
        module
        for name, module in list(sys.modules.items())
        if name.startswith("app.") and module is not None and hasattr(module, "call_agent")
    ]
    for module in poisoned:
        monkeypatch.setattr(module, "call_agent", refuse)

    assert {sys.modules[defined_in] for defined_in in MODEL_SEAMS} <= set(poisoned)

    for family, step, name in EVERY_STEP:
        for spoken in ("en", "pt-BR"):
            line, said = process_line(family, step, spoken)
            assert line
            assert said == name

    assert choose(FailSafe.INAUDIBLE, "pt", turn=0)[0]
    assert first(FailSafe.HARD_STOP, "pt")

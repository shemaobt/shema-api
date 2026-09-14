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

Every step of both families is here in both languages, and not only the ones a consumer
asks for today: the position is the whole address, so a bullet that moves in her file
moves every line after it, and a step nobody asserted is a step that would move in silence.
"""

import importlib
import json
import sys
from pathlib import Path
from typing import Any, NamedTuple

import pytest

import scripts.render_fixed_voice_lines as render
from app.services.internalization_room.fail_safe import (
    PROCESS_STEPS,
    FailSafe,
    UnknownProcessLine,
    choose,
    first,
    localized,
    process_line,
    utterances,
)
from app.services.internalization_room.languages import ROOM_LANGUAGES

MODEL_SEAMS: tuple[str, ...] = (
    "app.services.internalization_room.llm",
    "app.services.project_health.agents.llm_client",
)


class HerLine(NamedTuple):
    family: str
    step: str
    name: str
    english: str
    portuguese: str

    def written(self, language_code: str) -> str:
        return self.english if language_code.split("-")[0] == "en" else self.portuguese


HER_PROCESS_LINES: tuple[HerLine, ...] = (
    HerLine(
        family="P",
        step="start",
        name="P0",
        english=(
            "First let's listen to your whole recording, from beginning to end. For now, just "
            "listen."
        ),
        portuguese=(
            "Primeiro vamos ouvir a gravação de vocês inteira, do começo ao fim. Por enquanto é "
            "só ouvir."
        ),
    ),
    HerLine(
        family="P",
        step="tell",
        name="P1",
        english=(
            "Now let's go back to the beginning. You will listen to your recording and, at each "
            "sentence, pause to translate for me only what was said there. Tap the circle to "
            "pause, translate, and tap again so the recording goes on. Don't add anything and "
            "don't explain; it doesn't need to sound nice. Say in English exactly what that "
            "sentence says. Pause wherever it helps you remember what was said so you can "
            "translate it. When the whole recording has been translated, tap 'done'."
        ),
        portuguese=(
            "Agora vamos voltar ao começo. Vocês vão ouvir a gravação de vocês e, a cada frase, "
            "pausar para me traduzir só o que foi dito ali. Toquem no círculo para pausar, "
            "traduzam, e toquem de novo para a gravação seguir. Não acrescentem nada e não "
            "expliquem; não precisa ficar bonito. Digam em português exatamente o que aquela "
            "frase diz. Façam as pausas onde for melhor para vocês lembrarem do que foi dito e "
            "traduzirem. Quando a gravação inteira estiver traduzida, toquem em 'terminei'."
        ),
    ),
    HerLine(
        family="P",
        step="unheard",
        name="P2",
        english=("There is still a part of the recording to listen to before I check."),
        portuguese=("Ainda falta ouvir um trecho da gravação antes de eu conferir."),
    ),
    HerLine(
        family="P",
        step="approved",
        name="P3",
        english=("Approved as the team's final draft. It goes to OBT Refine."),
        portuguese=("Aprovado como rascunho final da equipe. Ele vai para o OBT Refine."),
    ),
    HerLine(
        family="X",
        step="open",
        name="X0",
        english=(
            "Now it's the turn of those who didn't help translate. What you say here is recorded,"
            " only for the team to hear afterwards. You will hear the whole passage. Then I'll "
            "ask what you understood. There is no right answer: what you understood is what "
            "matters."
        ),
        portuguese=(
            "Agora é a vez de quem não ajudou a traduzir. O que vocês disserem aqui fica gravado,"
            " só para a equipe ouvir depois. Vocês vão ouvir a passagem inteira. Depois eu "
            "pergunto o que vocês entenderam. Não tem resposta certa: o que vocês entenderam é o "
            "que importa."
        ),
    ),
    HerLine(
        family="X",
        step="retell",
        name="X1",
        english=(
            "Now tell me, in your own way, what you heard. It doesn't need to be perfect, tell "
            "what you remember. Tap the circle to speak and tap again when you finish."
        ),
        portuguese=(
            "Agora me contem, do jeito de vocês, o que vocês ouviram. Não precisa ser perfeito, "
            "conte o que você se lembrar. Toquem no círculo para falar e toquem de novo quando "
            "terminarem."
        ),
    ),
    HerLine(
        family="X",
        step="whole",
        name="X2",
        english=(
            "Did anything stay unclear? Would you like to comment on anything about the whole "
            "passage? If so, tap the circle and speak, as many times as you want. If not, tap "
            "'nothing to add'."
        ),
        portuguese=(
            "Alguma coisa não ficou clara? Querem comentar alguma coisa sobre a passagem inteira?"
            " Se sim, toquem no círculo e falem, quantas vezes quiserem. Se não, toquem em 'nada "
            "a acrescentar'."
        ),
    ),
    HerLine(
        family="X",
        step="frases",
        name="X3",
        english=(
            "Now, listen to the sentences one by one. When you hear a sentence, if you think it "
            "is good, tap the 'it's good' button. But if you think the sentence needs to change "
            "in some way, or if you think it is not clear, tap the circle again and make your "
            "comment."
        ),
        portuguese=(
            "Agora, escute as frases uma por uma. Quando ouvir uma frase, se achar que ela está "
            "boa, clique no botão 'está boa'. Mas se achar que a frase precisa mudar em alguma "
            "coisa, ou se achar que ela não está clara, clique novamente no círculo e faça o seu "
            "comentário."
        ),
    ),
    HerLine(
        family="X",
        step="thanks",
        name="X4",
        english=("Thank you for your help. What you said is kept for the team to hear."),
        portuguese=(
            "Agradecemos sua ajuda. O que vocês disseram fica guardado para a equipe ouvir."
        ),
    ),
)


@pytest.mark.parametrize("language_code", ["en", "pt-BR"])
@pytest.mark.parametrize("line", HER_PROCESS_LINES, ids=lambda line: line.name)
def test_every_step_reads_her_line_at_its_position(line: HerLine, language_code: str) -> None:
    """The copy is verbatim and the address is the position, for every step she wrote.

    `pt-BR` is asked for rather than `pt` because that is what the room is configured with,
    and the block she tags is `-pt`: the regional-then-primary fallback is the step in
    between, and without it a Brazilian team would be answered in English.
    """
    assert process_line(line.family, line.step, language_code) == (
        line.written(language_code),
        line.name,
    )


def test_a_step_answers_the_same_line_on_every_call() -> None:
    """The acceptance criterion, and the difference from a fail-safe in one assertion."""
    unheard = [process_line("P", "unheard", "pt-BR") for _ in range(7)]
    frases = [process_line("X", "frases", "pt-BR") for _ in range(7)]

    assert unheard == [("Ainda falta ouvir um trecho da gravação antes de eu conferir.", "P2")] * 7
    assert len(set(frases)) == 1
    assert frases[0][1] == "X3"


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


def test_a_family_whose_block_is_not_loaded_raises_rather_than_reading_past_the_end() -> None:
    """The tables say the step exists; the loaded text is what says whether it was written.

    Nothing can reach this while her four blocks are in the file, and that is the point: the
    day one of them is dropped, `lines[position]` would raise a bare `IndexError` from inside
    a lookup that has a named error for exactly this, and the traceback would say nothing
    about a missing block. P answering in the same breath is the control — it proves the
    document under test really is the one being read.
    """
    from app.services.internalization_room import fail_safe

    without_x = '### P. Process lines\n- "one"\n- "two"\n- "three"\n- "four"\n'
    real_loader = fail_safe.fail_safe_utterances
    fail_safe.fail_safe_utterances = lambda: without_x  # type: ignore[assignment]
    fail_safe._sections.cache_clear()
    try:
        assert process_line("P", "start") == ("one", "P0")
        with pytest.raises(UnknownProcessLine):
            process_line("X", "open")
    finally:
        fail_safe.fail_safe_utterances = real_loader  # type: ignore[assignment]
        fail_safe._sections.cache_clear()
        real_loader.cache_clear()


@pytest.mark.parametrize("spoken", ROOM_LANGUAGES)
def test_every_language_the_room_claims_has_her_process_lines_written(spoken: str) -> None:
    """A claimed language with no block of its own would ship English clips under its name.

    Measured with `localized` and not `utterances` for the reason the fail-safe guard beside
    it gives: `utterances` falls back to the authored English and so never comes back empty,
    which makes it safe to speak and useless as a measurement.
    """
    for family in PROCESS_STEPS:
        written = localized(family, spoken)
        assert len(written) == len(PROCESS_STEPS[family]), (
            f"the room claims {spoken!r} and family {family} has {len(written)} lines written "
            f"in it, not {len(PROCESS_STEPS[family])} — a step would be spoken in another language"
        )


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
    process_names = {line.name for line in HER_PROCESS_LINES}
    shipped_fail_safes = {
        f"{kind}{index}"
        for kind in FailSafe
        if kind not in render.NEVER_SHIPPED
        for index in range(len(utterances(kind, spoken)))
    }

    for line in HER_PROCESS_LINES:
        assert catalogue[line.name] == line.written(spoken)

    assert set(catalogue) == (
        shipped_fail_safes | set(render.STANDALONE.get(spoken, {})) | process_names
    ), "the catalogue gained a name that is neither a shipped fail-safe nor one of her steps"

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

    for line in HER_PROCESS_LINES:
        for language_code in ("en", "pt-BR"):
            assert process_line(line.family, line.step, language_code) == (
                line.written(language_code),
                line.name,
            )

    assert choose(FailSafe.INAUDIBLE, "pt", turn=0)[0]
    assert first(FailSafe.HARD_STOP, "pt")

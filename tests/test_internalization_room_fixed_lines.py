"""Her lines are asked of the room by name; the app's bundle keeps only three notices.

A fixed line is voiced by the room from the text it was deployed with, so a line she
re-rules is heard on the next load and no frozen copy of it travels with the app. What the
render script still bundles are the notices the room says when it cannot reach the server at
all, and this file guards that they do not drift, alongside how the fail-safes rotate.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import scripts.render_fixed_voice_lines as render
from app.services.internalization_room._default_prompts import (
    _PROMPTS_DIR,
    fail_safe_utterances,
)
from app.services.internalization_room.fail_safe import FailSafe, choose, localized
from app.services.internalization_room.languages import ROOM_LANGUAGES


def test_the_render_script_needs_to_be_told_where_the_bundle_is(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The bundle lives in the app's checkout, and the script has no way of knowing where.

    It used to guess it as a sibling of this repository. From a worktree the guess lands on a
    folder that does not exist, and `--check` then reports every clip as never rendered — the
    loudest possible answer, saying nothing about the bundle and hiding real drift inside it.

    The refusal is read for the argument it names, not only for argparse's exit code: that
    code answers any bad invocation, and would go on answering if some other flag were the
    one made required.
    """
    monkeypatch.setattr(sys, "argv", ["render_fixed_voice_lines.py", "--check"])

    with pytest.raises(SystemExit) as refused:
        render.main()

    assert refused.value.code == 2
    assert "--out" in capsys.readouterr().err


async def test_a_line_rendered_twice_is_written_with_its_sound_both_times(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings
    from app.services.platform import tts

    voiced = SimpleNamespace(status_code=200, content=b"\xff\xfbvoz", text="")
    elevenlabs = SimpleNamespace(post=AsyncMock(return_value=voiced))
    monkeypatch.setattr(get_settings(), "elevenlabs_api_key", "fake-elevenlabs", raising=False)
    monkeypatch.setattr(tts, "_make_client", lambda: elevenlabs)

    await render.render(tmp_path, "pt", force=True)
    await render.render(tmp_path, "pt", force=True)

    assert {clip.read_bytes() for clip in tmp_path.rglob("*.mp3")} == {b"\xff\xfbvoz"}, (
        "a sala devolvia ao script só a chave da fala: ele quebrava perguntando ao bucket se o "
        "clipe existia, e uma fala já conhecida ia para o bundle como arquivo vazio"
    )


@pytest.mark.parametrize("spoken", ROOM_LANGUAGES)
def test_every_kind_the_room_claims_to_speak_is_written_in_it(spoken: str) -> None:
    """Um idioma reivindicado e não escrito é uma sala que troca de língua no meio.

    Medido com `localized` e não com `utterances`: `utterances` cai para o bloco inglês e
    por isso nunca volta vazio, o que a torna segura para falar e inútil como medida.
    """
    for kind in FailSafe:
        if kind in (FailSafe.UNTOLD_STRETCH, FailSafe.STRETCH_TO_CORRECT):
            continue
        written = localized(kind, spoken)
        assert written, (
            f"a sala diz que fala {spoken!r} e a família {kind} não tem falas escritas nesse "
            "idioma — a equipe ouviria a falha em outra língua"
        )


def test_a_standalone_line_is_written_for_a_language_or_not_shipped_in_it_at_all() -> None:
    """Nenhuma fala solta empresta a letra de outro idioma: ou está escrita, ou não vai."""
    for spoken in ROOM_LANGUAGES:
        written = render.STANDALONE.get(spoken, {})
        catalogue = render.catalogue(spoken)
        for name in ("sem_conexao", "gravacao_presa", "microfone"):
            assert (name in catalogue) == (name in written), (
                f"{name} em {spoken!r} entrou no pacote sem letra escrita nesse idioma"
            )


def test_the_touch_to_start_invitation_is_gone_from_the_catalogue() -> None:
    """Marcia (RESPOSTA-MARCIA.md, item 10): 'Convite falado a cada 25 s: tirem.'

    A voz agora abre a sessão quando a passagem abre; um convite repetido vira cobrança, e
    a linha que pedia o toque para começar não deve mais aparecer no pacote de nenhum idioma.
    """
    for spoken in ROOM_LANGUAGES:
        assert "toque_para_comecar" not in render.catalogue(spoken)
        assert "toque_para_comecar" not in render.STANDALONE.get(spoken, {})


def test_a_leftover_manifest_entry_for_the_gone_invitation_shows_up_as_drift(
    tmp_path: Path,
) -> None:
    """The render manifest still lists a clip that no longer has a line to justify it.

    A room that keeps its old fixed-line renders on disk after the prompt drops one would
    ship a clip nothing plays and `--check` would never catch it, unless the drift guard
    itself treats a manifest entry with no matching catalogue entry as the orphan it is.
    """
    bundle = tmp_path / "en"
    bundle.mkdir()
    (bundle / render.MANIFEST).write_text(json.dumps({"toque_para_comecar": "stale"}))

    complaints = render.drift(tmp_path, "en")

    assert any(
        "toque_para_comecar" in complaint and "no longer in the prompt" in complaint
        for complaint in complaints
    ), f"um manifesto com a linha do convite deveria acusar o órfão, e não acusou: {complaints}"


def test_the_room_keeps_no_fail_safe_draft_for_a_language_it_does_not_speak() -> None:
    on_disk = {path.name for path in _PROMPTS_DIR.glob("_fail_safe_*_supplement.md")}

    assert on_disk == {"_fail_safe_pt_supplement.md"}
    assert {kind: localized(kind, "es") for kind in FailSafe if localized(kind, "es")} == {}
    assert "-es." not in fail_safe_utterances()


def test_the_app_side_lines_are_written_only_for_the_languages_the_room_speaks() -> None:
    assert set(render.STANDALONE) == set(ROOM_LANGUAGES)


def test_a_repeated_failure_does_not_repeat_the_same_sentence() -> None:
    """The authored file asks for variation; a room stuck on one line sounds like a machine."""
    spoken = [choose(FailSafe.UNREPAIRABLE, "pt", turn=turn) for turn in range(4)]

    assert len({line for line, _ in spoken}) == 4
    assert [name for _, name in spoken] == ["A0", "A1", "A2", "A3"]


def test_the_rotation_wraps_instead_of_running_out() -> None:
    line, name = choose(FailSafe.UNREPAIRABLE, "pt", turn=4)

    assert name == "A0"
    assert line == choose(FailSafe.UNREPAIRABLE, "pt", turn=0)[0]


def test_the_portuguese_acknowledgements_are_her_three_and_ta_is_not_among_them() -> None:
    assert localized(FailSafe.INSTANT_ACK, "pt") == [
        "Hmm.",
        "Certo.",
        "Deixa eu pensar um instante.",
    ]


def test_a_kind_with_one_line_always_answers_with_it() -> None:
    assert choose(FailSafe.HARD_STOP, "pt", turn=7)[1] == "E0"


def test_an_unwritten_language_falls_back_to_the_authored_line() -> None:
    """Silence would be the one outcome worse than the wrong language."""
    line, name = choose(FailSafe.UNREPAIRABLE, "xx", turn=0)

    assert line
    assert name == "A0"

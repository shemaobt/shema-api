"""Her lines are asked of the room by name; the app's bundle keeps only three notices.

A fixed line is voiced by the room from the text it was deployed with, so a line she
re-rules is heard on the next load and no frozen copy of it travels with the app. What the
render script still bundles are the notices the room says when it cannot reach the server at
all, and this file guards that they do not drift, alongside how the fail-safes rotate.
"""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import scripts.render_fixed_voice_lines as render
from app.services.internalization_room._default_prompts import (
    _PROMPTS_DIR,
    fail_safe_utterances,
)
from app.services.internalization_room.fail_safe import FailSafe, choose, localized
from app.services.internalization_room.languages import ROOM_LANGUAGES

VOICED = b"\xff\xfbvoz"


@pytest.fixture
def elevenlabs(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    from app.core.config import get_settings
    from app.services.platform import tts

    client = SimpleNamespace(
        post=AsyncMock(return_value=SimpleNamespace(status_code=200, content=VOICED, text="")),
        aclose=AsyncMock(),
    )
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(get_settings(), "elevenlabs_api_key", "fake-elevenlabs", raising=False)
    monkeypatch.setattr(tts, "_make_client", factory)
    return SimpleNamespace(client=client, factory=factory, posts=client.post)


def run_script(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["render_fixed_voice_lines.py", *args])
    return render.main()


def change_setting(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), name, value)


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

    await render.render(tmp_path, "pt", force=True, api_commit="0" * 40)
    await render.render(tmp_path, "pt", force=True, api_commit="0" * 40)

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


def test_the_portuguese_no_connection_line_is_written_down_in_the_script() -> None:
    assert render.catalogue("pt").get("sem_conexao", "").strip()


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


def test_a_line_whose_text_is_unchanged_but_whose_voice_id_changed_is_stale_under_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt")
    change_setting(monkeypatch, "internalization_room_voice_id", "another-voice")

    code = run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt", "--check")

    assert code == 1
    listed = capsys.readouterr().out
    assert all(f"pt/{name}" in listed for name in render.catalogue("pt"))


def test_a_line_whose_text_is_unchanged_but_whose_model_changed_is_stale_under_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt")
    change_setting(monkeypatch, "internalization_room_tts_model", "another-model")

    code = run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt", "--check")

    assert code == 1
    listed = capsys.readouterr().out
    assert all(f"pt/{name}" in listed for name in render.catalogue("pt"))


def test_a_run_without_force_re_renders_only_the_stale_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, elevenlabs: SimpleNamespace
) -> None:
    sounds = iter(f"sound {n}".encode() for n in range(100))
    elevenlabs.posts.side_effect = lambda *_, **__: SimpleNamespace(
        status_code=200, content=next(sounds), text=""
    )
    run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt")
    bundle = tmp_path / "pt"
    stale, *fresh = render.catalogue("pt")
    kept = {name: (bundle / f"{name}.mp3").read_bytes() for name in fresh}
    before = json.loads((bundle / render.MANIFEST).read_text())
    manifest = dict(before, **{stale: "stale"})
    (bundle / render.MANIFEST).write_text(json.dumps(manifest))
    elevenlabs.posts.reset_mock()

    run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt")

    assert elevenlabs.posts.await_count == 1
    assert (bundle / f"{stale}.mp3").read_bytes() not in kept.values()
    assert {name: (bundle / f"{name}.mp3").read_bytes() for name in fresh} == kept
    assert json.loads((bundle / render.MANIFEST).read_text()) == before

    elevenlabs.posts.reset_mock()
    run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt")
    assert elevenlabs.posts.await_count == 0


def test_a_run_over_pt_and_en_renders_both_languages_in_one_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, elevenlabs: SimpleNamespace
) -> None:
    code = run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt,en")

    assert code == 0
    for language in ("pt", "en"):
        assert (tmp_path / language / render.MANIFEST).exists()
        for name in render.catalogue(language):
            assert (tmp_path / language / f"{name}.mp3").read_bytes() == VOICED
    assert elevenlabs.factory.call_count == 1


def test_a_run_with_force_re_renders_every_line_of_every_language(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, elevenlabs: SimpleNamespace
) -> None:
    run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt,en")
    elevenlabs.posts.reset_mock()

    run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt,en", "--force")

    assert elevenlabs.posts.await_count == len(render.catalogue("pt")) + len(render.catalogue("en"))


def test_the_client_of_a_run_is_closed_when_a_language_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, elevenlabs: SimpleNamespace
) -> None:
    elevenlabs.posts.return_value = SimpleNamespace(status_code=500, content=b"", text="")

    with pytest.raises(Exception, match="TTS request failed"):
        run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt,en")

    elevenlabs.client.aclose.assert_awaited_once()


def test_after_a_run_the_apps_clip_hashes_file_matches_the_rendered_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, elevenlabs: SimpleNamespace
) -> None:
    from app.core.config import get_settings
    from app.services.internalization_room.voices import voice_for

    run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt,en")

    for language in ("pt", "en"):
        written = json.loads((tmp_path / language / "clip_hashes.json").read_text())
        assert list(written) == ["api_commit", "clips", "rendered_at", "unrendered", "voice_id"]
        assert written["clips"] == {
            f"{name}.mp3": hashlib.sha256(VOICED).hexdigest() for name in render.catalogue(language)
        }
        assert written["voice_id"] == voice_for(language, settings=get_settings())
        assert re.fullmatch(r"[0-9a-f]{40}", written["api_commit"])
        assert written["rendered_at"].endswith("Z")
        assert written["unrendered"] == []


def test_a_bundled_mp3_the_run_did_not_render_is_hashed_and_listed_as_unrendered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, elevenlabs: SimpleNamespace
) -> None:
    (tmp_path / "pt").mkdir()
    (tmp_path / "pt" / "aprovado_a_mao.mp3").write_bytes(b"approved audio")

    run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt")

    written = json.loads((tmp_path / "pt" / "clip_hashes.json").read_text())
    assert written["unrendered"] == ["aprovado_a_mao.mp3"]
    assert written["clips"]["aprovado_a_mao.mp3"] == hashlib.sha256(b"approved audio").hexdigest()
    assert (tmp_path / "pt" / "aprovado_a_mao.mp3").read_bytes() == b"approved audio"


def test_a_run_that_cannot_name_the_api_commit_renders_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, elevenlabs: SimpleNamespace
) -> None:
    def no_git(*_: object, **__: object) -> None:
        raise subprocess.CalledProcessError(128, "git rev-parse HEAD")

    monkeypatch.setattr(render.subprocess, "run", no_git)

    with pytest.raises(subprocess.CalledProcessError):
        run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt,en")

    assert elevenlabs.posts.await_count == 0
    assert list(tmp_path.rglob("*.*")) == []


def test_a_run_that_fails_on_the_second_line_leaves_the_manifest_and_clip_hashes_true_to_disk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt")
    landed, failed, *_ = render.catalogue("pt")
    answers = iter(
        [
            SimpleNamespace(status_code=200, content=b"new sound", text=""),
            SimpleNamespace(status_code=500, content=b"", text=""),
        ]
    )
    elevenlabs.posts.side_effect = lambda *_, **__: next(answers)

    with pytest.raises(Exception, match="TTS request failed"):
        run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt", "--force")

    bundle = tmp_path / "pt"
    written = json.loads((bundle / "clip_hashes.json").read_text())
    assert written["clips"] == {
        f"{clip.stem}.mp3": hashlib.sha256(clip.read_bytes()).hexdigest()
        for clip in bundle.glob("*.mp3")
    }
    assert (bundle / f"{landed}.mp3").read_bytes() == b"new sound"
    capsys.readouterr()
    assert run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt", "--check") == 1
    listed = capsys.readouterr().out
    assert f"pt/{failed}" in listed
    assert f"pt/{landed}" not in listed


def test_the_clip_hashes_file_goes_to_the_directory_the_flag_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, elevenlabs: SimpleNamespace
) -> None:
    bundle, elsewhere = tmp_path / "bundle", tmp_path / "elsewhere"

    run_script(
        monkeypatch,
        "--out",
        str(bundle),
        "--language",
        "pt,en",
        "--clip-hashes",
        str(elsewhere),
    )

    for language in ("pt", "en"):
        assert (elsewhere / language / "clip_hashes.json").exists()
        assert not (bundle / language / "clip_hashes.json").exists()
        assert (bundle / language / render.MANIFEST).exists()


def test_a_write_interrupted_on_a_line_whose_audio_was_missing_leaves_check_naming_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt")
    missing, *_ = render.catalogue("pt")
    (tmp_path / "pt" / f"{missing}.mp3").unlink()

    def interrupted(self: Path, data: bytes) -> int:
        self.open("wb").write(data[:2])
        raise OSError("interrupted")

    monkeypatch.setattr(Path, "write_bytes", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt")
    monkeypatch.undo()

    capsys.readouterr()
    assert run_script(monkeypatch, "--out", str(tmp_path), "--language", "pt", "--check") == 1
    assert f"pt/{missing}" in capsys.readouterr().out

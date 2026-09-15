"""The pre-approved lines ship as audio inside the app, and must not drift from the prompt.

A fail-safe is what the team hears when the model failed or the network did. Synthesizing it
at that moment asks the network for a favour precisely when the network is the problem — so
these lines travel with the app. The cost of that is a frozen copy, and the guard against a
silent freeze is this file.
"""

import json
import re
import sys
from pathlib import Path

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


def test_the_drift_check_names_the_process_clips_the_bundle_never_had(tmp_path: Path) -> None:
    """A bundle rendered before the process families exist is missing exactly those clips.

    The app plays a process line by name out of the bundle, so a name the render never reached
    is a step the room cannot voice at all. Nothing that *is* rendered and current may be
    complained about in the same breath, or the list stops being readable.

    The four P names are written out rather than read off `PROCESS_STEPS`, which is the table
    that answers `catalogue`: derived from it, the case would agree with a table that had lost
    the family altogether. X is left out of the manifest and out of both assertions — it rides
    into the catalogue by the same door and is a case of its own, not a second subject here.
    """
    lines = render.catalogue("pt")
    already = {
        name: render.fingerprint(text)
        for name, text in lines.items()
        if not name.startswith(("P", "X"))
    }
    bundle = tmp_path / "pt"
    bundle.mkdir()
    (bundle / render.MANIFEST).write_text(json.dumps(already), encoding="utf-8")
    for name in already:
        clip = render._clip_path(tmp_path, "pt", name)
        clip.parent.mkdir(parents=True, exist_ok=True)
        clip.write_bytes(b"")

    complaints = render.drift(tmp_path, "pt")

    assert [complaint for complaint in complaints if complaint.startswith("pt/P")] == [
        f"pt/P{step}: never rendered" for step in range(4)
    ]
    assert not [
        complaint for complaint in complaints if not complaint.startswith(("pt/P", "pt/X"))
    ], f"uma fala que está no pacote e em dia foi acusada junto: {complaints}"


@pytest.mark.parametrize("spoken", ROOM_LANGUAGES)
def test_the_catalogue_covers_every_kind_the_room_claims_to_speak(spoken: str) -> None:
    """Um idioma reivindicado e não escrito é uma sala que troca de língua no meio.

    Medido com `localized` e não com `utterances`: `utterances` cai para o bloco inglês e
    por isso nunca volta vazio, o que a torna segura para falar e inútil como medida.
    """
    catalogue = render.catalogue(spoken)
    for kind in FailSafe:
        if kind in render.NEVER_SHIPPED:
            continue
        written = localized(kind, spoken)
        assert written, (
            f"a sala diz que fala {spoken!r} e a família {kind} não tem falas escritas nesse "
            "idioma — a equipe ouviria a falha em outra língua"
        )
        for index in range(len(written)):
            assert f"{kind}{index}" in catalogue


@pytest.mark.parametrize("spoken", ROOM_LANGUAGES)
def test_the_stretch_line_is_spoken_and_never_shipped(spoken: str) -> None:
    """O suplemento diz em negrito: *"This one is spoken, not shipped."*"""
    assert not any(name.startswith("H") for name in render.catalogue(spoken))


def test_every_language_ships_the_same_lines_so_a_turn_in_one_is_a_turn_in_all() -> None:
    """O servidor manda `fixed_line` por nome, e o app resolve o nome no pacote do idioma.

    Só os nomes que o servidor pode mandar. As falas soltas não chegam por turno — o app as
    toca sozinho — e o português é o único idioma sem `sem_conexao` escrito, porque o áudio
    dele foi gravado antes deste script e a letra nunca foi anotada.
    """
    named = re.compile(r"^[A-Z]\d+$")
    shipped = {
        spoken: {name for name in render.catalogue(spoken) if named.match(name)}
        for spoken in ROOM_LANGUAGES
    }

    assert len(set(map(frozenset, shipped.values()))) == 1, (
        "um idioma ficou sem uma fala que outro tem; o nome chega do servidor no meio de um "
        f"turno e o app não acha o arquivo, então a sala emudece: {shipped}"
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


def test_a_language_the_room_does_not_claim_keeps_its_draft_and_reaches_no_mouth() -> None:
    """The Spanish supplement stays for the day she offers the language, and only for that.

    Reading it was never a decision anybody took: the loader globbed the directory, so a
    draft dropped beside the authored file was spoken by whatever asked for its language.
    """
    draft = (_PROMPTS_DIR / "_fail_safe_es_supplement.md").read_text(encoding="utf-8")
    reachable = {kind: localized(kind, "es") for kind in FailSafe if localized(kind, "es")}

    assert "STATUS: DRAFT — awaiting validation." in draft
    assert reachable == {}, (
        "o suplemento em espanhol é rascunho e diz de si mesmo que nada ali foi aprovado "
        f"para ser dito a uma equipe, e mesmo assim a sala o falava: {reachable}"
    )
    assert "-es." not in fail_safe_utterances(), (
        "o texto concatenado ainda carrega blocos em espanhol, então basta alguém pedir a "
        "língua para a sala falar rascunho"
    )


def test_a_repeated_failure_does_not_repeat_the_same_sentence() -> None:
    """The authored file asks for variation; a room stuck on one line sounds like a machine."""
    spoken = [choose(FailSafe.INAUDIBLE, "pt", turn=turn) for turn in range(3)]

    assert len({line for line, _ in spoken}) == 3
    assert [name for _, name in spoken] == ["D0", "D1", "D2"]


def test_the_rotation_wraps_instead_of_running_out() -> None:
    line, name = choose(FailSafe.INAUDIBLE, "pt", turn=3)

    assert name == "D0"
    assert line == choose(FailSafe.INAUDIBLE, "pt", turn=0)[0]


def test_a_kind_with_one_line_always_answers_with_it() -> None:
    assert choose(FailSafe.HARD_STOP, "pt", turn=7)[1] == "E0"


def test_an_unwritten_language_falls_back_to_the_authored_line() -> None:
    """Silence would be the one outcome worse than the wrong language."""
    line, name = choose(FailSafe.UNREPAIRABLE, "xx", turn=0)

    assert line
    assert name == "A0"

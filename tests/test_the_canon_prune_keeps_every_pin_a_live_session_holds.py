"""ENG-1753 — only a prune removes a kept canon, and it keeps every pin a live session holds.

The prune is handed the answer of production's `canon-pins` read, saved to a file. It keeps
every kept tree named there, the tree of the pin production serves and that of the deployed
pin, removes the others, and refuses to remove anything when it has no file, a file that is not
production's answer, or a pin it holds no canon for.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from app.core.canon_pin import pinned_commit
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at, what_is_vendored

LIVE = "a" * 40
STALE = "c" * 40
ELSEWHERE = "d" * 40
PRODUCTION = "tripod-backend"


@pytest.fixture
def a_canon_deployed_beside_three_kept_trees(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Path:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.passage("P01-Ruth-1-1-5")
    point_the_sync_at(monkeypatch, canon, compiler, tmp_path)
    (tmp_path / "element-labels").mkdir()
    (tmp_path / "element-labels" / "ruth.json").write_text("{}")
    (tmp_path / "ui-labels.pt.json").write_text("{}")
    assert canon.sync(pin=SHA) == 0
    for pin in (LIVE, STALE, SHA):
        (tmp_path / "kept" / pin / "vendor").mkdir(parents=True)
        (tmp_path / "kept" / pin / "vendor" / "VENDOR_PIN").write_text(f"pin_commit: {pin}\n")
    return tmp_path


def _live_pins(tmp_path: Path, body: str) -> Path:
    file = tmp_path / "pins.json"
    file.write_text(body)
    return file


def _moment(ago: timedelta = timedelta(minutes=1)) -> str:
    return (datetime.now(UTC) - ago).isoformat()


def _the_read_answered(
    tmp_path: Path, *pins: str, serving: str = SHA, ago: timedelta = timedelta(minutes=1)
) -> Path:
    answer = {
        "environment": PRODUCTION,
        "deployed_pin": serving,
        "answered_at": _moment(ago),
        "pins": list(pins),
    }
    return _live_pins(tmp_path, json.dumps(answer))


def _prune(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr("sys.argv", ["sync_internalization_canon.py", "--prune", *args])
    return canon.main()


def _kept_trees(canon_dir: Path) -> list[str]:
    return sorted(path.name for path in (canon_dir / "kept").iterdir())


def _everything_under(canon_dir: Path) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in canon_dir.rglob("*") if path.is_file()}


def test_a_prune_told_a_is_live_drops_c_and_keeps_a_and_the_deployed_b(
    a_canon_deployed_beside_three_kept_trees: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canon_dir = a_canon_deployed_beside_three_kept_trees
    vendored = what_is_vendored(canon_dir / "vendor")
    pin_record = (canon_dir / "vendor" / "VENDOR_PIN").read_text()
    live_pins = _the_read_answered(canon_dir, LIVE)

    assert _prune(monkeypatch, "--live-pins", str(live_pins)) == 0

    assert _kept_trees(canon_dir) == sorted([LIVE, SHA]), (
        "o prune apagou o canon de uma sessão viva ou do pin servido, ou guardou um que ninguém lê"
    )
    assert what_is_vendored(canon_dir / "vendor") == vendored
    assert (canon_dir / "vendor" / "VENDOR_PIN").read_text() == pin_record
    assert pinned_commit(pin_record) == SHA


def test_a_prune_says_which_kept_trees_it_dropped_and_which_it_kept(
    a_canon_deployed_beside_three_kept_trees: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    canon_dir = a_canon_deployed_beside_three_kept_trees
    live_pins = _the_read_answered(canon_dir, LIVE)
    said_for = {LIVE: "kept", SHA: "kept", STALE: "dropped"}
    capsys.readouterr()

    assert _prune(monkeypatch, "--live-pins", str(live_pins)) == 0

    said = capsys.readouterr().out.splitlines()
    assert [line for line in said if "kept/" in line] == [
        f"  {said_for[pin]} kept/{pin}" for pin in sorted(said_for)
    ], "o prune apagou canon sem dizer qual"


def test_a_prune_without_a_file_refuses_and_removes_nothing(
    a_canon_deployed_beside_three_kept_trees: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    canon_dir = a_canon_deployed_beside_three_kept_trees
    before = _everything_under(canon_dir)

    assert _prune(monkeypatch) == 1

    assert "--live-pins" in capsys.readouterr().err
    assert _everything_under(canon_dir) == before, "um prune sem os pins vivos apagou canon"


@pytest.mark.parametrize(
    "body",
    [
        None,
        "not json",
        json.dumps({"sha": [LIVE]}),
        json.dumps({"pins": LIVE}),
        '{"pins": ["aaaaaaa"]}',
        json.dumps({"environment": PRODUCTION, "deployed_pin": SHA, "pins": [LIVE]}),
        json.dumps(
            {
                "environment": PRODUCTION,
                "deployed_pin": SHA,
                "answered_at": datetime.now().isoformat(),
                "pins": [LIVE],
            }
        ),
    ],
    ids=[
        "a missing file",
        "not json",
        "no pins",
        "pins not a list",
        "a short sha",
        "no moment",
        "a moment with no zone",
    ],
)
def test_a_prune_whose_file_is_not_the_reads_answer_refuses_and_removes_nothing(
    a_canon_deployed_beside_three_kept_trees: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    body: str | None,
) -> None:
    canon_dir = a_canon_deployed_beside_three_kept_trees
    live_pins = canon_dir / "pins.json" if body is None else _live_pins(canon_dir, body)
    before = _everything_under(canon_dir)

    assert _prune(monkeypatch, "--live-pins", str(live_pins)) == 1

    assert str(live_pins) in capsys.readouterr().err
    assert _everything_under(canon_dir) == before, "um arquivo que não é a resposta apagou canon"


def test_a_prune_told_a_live_pin_it_holds_no_tree_for_refuses_and_removes_nothing(
    a_canon_deployed_beside_three_kept_trees: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    canon_dir = a_canon_deployed_beside_three_kept_trees
    live_pins = _the_read_answered(canon_dir, LIVE, ELSEWHERE)
    before = _everything_under(canon_dir)

    assert _prune(monkeypatch, "--live-pins", str(live_pins)) == 1

    assert ELSEWHERE in capsys.readouterr().err
    assert _everything_under(canon_dir) == before, (
        "um arquivo de outro ambiente apagou o canon que produção lê"
    )


def test_a_prune_told_the_deployed_pin_it_holds_no_kept_tree_for_still_prunes(
    a_canon_deployed_beside_three_kept_trees: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canon_dir = a_canon_deployed_beside_three_kept_trees
    shutil.rmtree(canon_dir / "kept" / SHA)
    live_pins = _the_read_answered(canon_dir, LIVE, SHA)

    assert _prune(monkeypatch, "--live-pins", str(live_pins)) == 0

    assert _kept_trees(canon_dir) == [LIVE], (
        "o prune recusava o pin servido, que é lido de vendor/ e nunca tem árvore guardada"
    )


def test_a_prune_beside_a_stray_file_under_kept_still_prunes(
    a_canon_deployed_beside_three_kept_trees: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canon_dir = a_canon_deployed_beside_three_kept_trees
    (canon_dir / "kept" / ".DS_Store").write_bytes(b"finder")
    live_pins = _the_read_answered(canon_dir, LIVE)

    assert _prune(monkeypatch, "--live-pins", str(live_pins)) == 0

    assert [name for name in _kept_trees(canon_dir) if not name.startswith(".")] == sorted(
        [LIVE, SHA]
    ), "um arquivo do Finder em kept/ derrubava o prune"


def test_a_prune_keeps_the_pin_production_serves_though_no_session_holds_it(
    a_canon_deployed_beside_three_kept_trees: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canon_dir = a_canon_deployed_beside_three_kept_trees
    live_pins = _the_read_answered(canon_dir, serving=LIVE)

    assert _prune(monkeypatch, "--live-pins", str(live_pins)) == 0

    assert _kept_trees(canon_dir) == sorted([LIVE, SHA]), (
        "o prune apagou o canon que produção ainda serve com o deploy segurado, e as sessões "
        "abertas nele respondiam 409 depois do deploy"
    )


@pytest.mark.parametrize(
    "environment",
    ["tripod-backend-staging", "", None],
    ids=["staging", "no cloud run service", "no environment"],
)
def test_a_prune_whose_file_does_not_name_production_refuses_and_removes_nothing(
    a_canon_deployed_beside_three_kept_trees: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    environment: str | None,
) -> None:
    canon_dir = a_canon_deployed_beside_three_kept_trees
    answer: dict[str, object] = {"deployed_pin": SHA, "answered_at": _moment(), "pins": [LIVE]}
    if environment is not None:
        answer["environment"] = environment
    live_pins = _live_pins(canon_dir, json.dumps(answer))
    before = _everything_under(canon_dir)

    assert _prune(monkeypatch, "--live-pins", str(live_pins)) == 1

    assert str(live_pins) in capsys.readouterr().err
    assert _everything_under(canon_dir) == before, (
        "um arquivo de um ambiente sem sessões vivas apagou o canon que produção lê"
    )


def test_a_prune_whose_file_carries_no_deployed_pin_refuses_and_removes_nothing(
    a_canon_deployed_beside_three_kept_trees: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    canon_dir = a_canon_deployed_beside_three_kept_trees
    live_pins = _live_pins(
        canon_dir,
        json.dumps({"environment": PRODUCTION, "answered_at": _moment(), "pins": [LIVE]}),
    )
    before = _everything_under(canon_dir)

    assert _prune(monkeypatch, "--live-pins", str(live_pins)) == 1

    assert str(live_pins) in capsys.readouterr().err
    assert _everything_under(canon_dir) == before, (
        "um arquivo sem o pin servido apagou o canon que produção serve"
    )


def test_a_prune_told_a_served_pin_it_holds_no_tree_for_refuses_and_removes_nothing(
    a_canon_deployed_beside_three_kept_trees: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    canon_dir = a_canon_deployed_beside_three_kept_trees
    live_pins = _the_read_answered(canon_dir, LIVE, serving=ELSEWHERE)
    before = _everything_under(canon_dir)

    assert _prune(monkeypatch, "--live-pins", str(live_pins)) == 1

    assert ELSEWHERE in capsys.readouterr().err
    assert _everything_under(canon_dir) == before, (
        "um prune feito de um checkout que não conhece o pin servido apagou canon"
    )


def test_a_prune_with_no_deployed_pin_in_the_checkout_refuses_and_removes_nothing(
    a_canon_deployed_beside_three_kept_trees: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    canon_dir = a_canon_deployed_beside_three_kept_trees
    (canon_dir / "vendor" / "VENDOR_PIN").unlink()
    live_pins = _the_read_answered(canon_dir, LIVE)
    before = _everything_under(canon_dir)

    assert _prune(monkeypatch, "--live-pins", str(live_pins)) == 1

    assert "VENDOR_PIN" in capsys.readouterr().err
    assert _everything_under(canon_dir) == before, "um checkout sem VENDOR_PIN apagou canon"


def test_a_prune_whose_kept_holds_a_link_refuses_and_removes_nothing(
    a_canon_deployed_beside_three_kept_trees: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    canon_dir = a_canon_deployed_beside_three_kept_trees
    shutil.rmtree(canon_dir / "kept" / LIVE)
    (canon_dir / "kept" / LIVE).symlink_to(canon_dir / "kept" / STALE, target_is_directory=True)
    live_pins = _the_read_answered(canon_dir, LIVE)
    before = _everything_under(canon_dir)

    assert _prune(monkeypatch, "--live-pins", str(live_pins)) == 1

    assert LIVE in capsys.readouterr().err
    assert _everything_under(canon_dir) == before, (
        "o prune tomou um link pela árvore de um pin vivo e apagou a árvore para onde ele aponta"
    )


def test_a_prune_whose_kept_is_itself_a_link_refuses_and_removes_nothing(
    a_canon_deployed_beside_three_kept_trees: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    canon_dir = a_canon_deployed_beside_three_kept_trees
    elsewhere = tmp_path / "elsewhere"
    (canon_dir / "kept").rename(elsewhere)
    (canon_dir / "kept").symlink_to(elsewhere, target_is_directory=True)
    live_pins = _the_read_answered(canon_dir, LIVE)
    before = _everything_under(elsewhere)

    assert _prune(monkeypatch, "--live-pins", str(live_pins)) == 1

    assert "kept" in capsys.readouterr().err
    assert _everything_under(elsewhere) == before, "o prune apagou por um kept/ que é link"


def test_a_prune_whose_file_is_older_than_fifteen_minutes_refuses_and_removes_nothing(
    a_canon_deployed_beside_three_kept_trees: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    canon_dir = a_canon_deployed_beside_three_kept_trees
    live_pins = _the_read_answered(canon_dir, LIVE, ago=timedelta(minutes=16))
    before = _everything_under(canon_dir)

    assert _prune(monkeypatch, "--live-pins", str(live_pins)) == 1

    assert str(live_pins) in capsys.readouterr().err
    assert _everything_under(canon_dir) == before, (
        "um arquivo velho, de antes de um deploy, apagou o canon que as sessões novas leem"
    )


def test_a_prune_whose_file_is_a_minute_old_prunes(
    a_canon_deployed_beside_three_kept_trees: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canon_dir = a_canon_deployed_beside_three_kept_trees
    live_pins = _the_read_answered(canon_dir, LIVE, ago=timedelta(minutes=1))

    assert _prune(monkeypatch, "--live-pins", str(live_pins)) == 0

    assert _kept_trees(canon_dir) == sorted([LIVE, SHA]), "o prune recusou um arquivo recém-buscado"


def test_a_prune_told_every_kept_pin_removes_nothing(
    a_canon_deployed_beside_three_kept_trees: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canon_dir = a_canon_deployed_beside_three_kept_trees
    live_pins = _the_read_answered(canon_dir, LIVE, STALE)
    before = _everything_under(canon_dir)

    assert _prune(monkeypatch, "--live-pins", str(live_pins)) == 0

    assert _everything_under(canon_dir) == before, "o prune apagou um canon que estava na lista"


def test_live_pins_without_prune_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv", ["sync_internalization_canon.py", "--sync", "--live-pins", "p.json"]
    )
    monkeypatch.setattr(
        canon, "sync", lambda pin=None: pytest.fail("sync() ran with an ignored --live-pins")
    )

    with pytest.raises(SystemExit) as excinfo:
        canon.main()

    assert excinfo.value.code != 0

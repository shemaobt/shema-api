"""The local API reloads on its own source, and not on the worktrees checked out beside it.

The compose file mounts the repository root at `/app`, and every parallel worktree lives
under `/app/.worktrees/`. A reload that watches the whole mount restarts the local room each
time any agent saves a file in its own worktree, mid-session.

Read through uvicorn's own configuration and file filter, built from the arguments the two
development entry points really pass, so a flag uvicorn would silently ignore cannot pass.
"""

import json
import shlex
from pathlib import Path

import pytest
import yaml
from uvicorn.config import Config
from uvicorn.main import main as uvicorn_cli
from uvicorn.supervisors.watchfilesreload import FileFilter

REPOSITORY = Path(__file__).resolve().parent.parent
MOUNT = "/app"


def _compose_script() -> str:
    command = yaml.safe_load((REPOSITORY / "docker-compose.yml").read_text())["services"][
        "backend"
    ]["command"]
    return shlex.split(command)[-1]


def _dockerfile_script() -> str:
    cmd = next(
        line
        for line in (REPOSITORY / "Dockerfile.dev").read_text().splitlines()
        if line.startswith("CMD ")
    )
    return json.loads(cmd.removeprefix("CMD "))[-1]


def _the_reload_config(script: str, root: Path) -> Config:
    """What uvicorn is configured with once the command's own steps before it have run."""
    words = [
        str(root) + word.removeprefix(MOUNT) if word.startswith(f"{MOUNT}/") else word
        for word in shlex.split(script)
    ]
    steps: list[list[str]] = [[]]
    for word in words:
        steps.append([]) if word == "&&" else steps[-1].append(word)
    for step in steps:
        if step[:2] == ["mkdir", "-p"]:
            for directory in step[2:]:
                Path(directory).mkdir(parents=True, exist_ok=True)
    arguments = words[words.index("uvicorn") + 1 :]
    params = uvicorn_cli.make_context("uvicorn", arguments).params
    params.pop("app_dir")
    return Config(**params)


def _is_watched(config: Config, path: Path) -> bool:
    inside = any(directory in path.parents for directory in config.reload_dirs)
    return inside and FileFilter(config)(path)


@pytest.mark.parametrize(
    "script", [_compose_script, _dockerfile_script], ids=["docker-compose.yml", "Dockerfile.dev"]
)
def test_the_local_apis_reload_ignores_a_file_under_worktrees_and_watches_a_file_under_app(
    script, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ignored = tmp_path / ".worktrees" / "x" / "app" / "foo.py"
    watched = tmp_path / "app" / "main.py"
    watched.parent.mkdir()
    monkeypatch.chdir(tmp_path)

    config = _the_reload_config(script(), tmp_path)
    ignored.parent.mkdir(parents=True)

    assert not _is_watched(config, ignored)
    assert _is_watched(config, watched)

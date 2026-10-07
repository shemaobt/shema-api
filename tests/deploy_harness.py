"""What a deploy workflow tells its Cloud Run service, read from the workflow itself."""

from __future__ import annotations

from pathlib import Path


def deploy_command(workflow: str) -> list[str]:
    """The words of the `gcloud run deploy` command the workflow's "Deploy Backend" step runs."""
    import yaml

    path = Path(__file__).resolve().parent.parent / ".github" / "workflows" / workflow
    steps = yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"]["deploy"]["steps"]
    deploy_step = next(step for step in steps if step["name"] == "Deploy Backend")
    words: list[str] = deploy_step["run"].split()
    return words


def deploy_env_vars(workflow: str) -> dict[str, str]:
    """The plain variables a deploy workflow tells its Cloud Run service to run with.

    They travel in one token of the `gcloud run deploy` command, and `^|^` names `|` as the
    separator because `CORS_ORIGINS` is itself a comma-separated list. Reading the token
    rather than the whole command is what makes this a statement about the service's
    environment and not about a string appearing somewhere in a shell script.
    """
    token = next(word for word in deploy_command(workflow) if word.startswith("--update-env-vars="))
    body = token.split("=", 1)[1].strip('"')
    assert body.startswith("^|^"), f"{workflow} no longer names its own separator"
    return dict(pair.split("=", 1) for pair in body[3:].split("|"))

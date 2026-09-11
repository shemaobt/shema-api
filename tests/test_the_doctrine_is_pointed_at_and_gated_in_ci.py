"""The three places the vendoring is worth nothing without: CI, the PR, and the way in.

A record nobody runs is a record. `ENG-827` and `ENG-829` install guards whose messages quote a
doctrine sentence, and until this ticket they pointed at a document a developer could not open;
the mirror of that failure is a vendored document nothing checks and no file points at.

So: the lint workflow runs the drift check offline, the pull-request template asks for her
sentence and where it is written before a prompt or a model parameter moves, and `AGENTS.md` and
`README.md` each carry one line saying where the doctrine is — the way
`AUTHORITATIVE-SOURCE-SEAM.md` is pointed at from her `CLAUDE.md`.
"""

from __future__ import annotations

from scripts.sync_doctrine import REPO_ROOT

LINT = (REPO_ROOT / ".github/workflows/lint.yml").read_text(encoding="utf-8")
TEMPLATE_PATH = REPO_ROOT / ".github/pull_request_template.md"


def test_the_drift_check_runs_on_every_pull_request() -> None:
    """In the `doctrine` job, beside the guard on the six mechanisms, and without the network.

    The two halves belong together: one says no banned mechanism came back into the code, the
    other says no artefact of hers moved without her word. `--check` compares recorded sha256s
    and reads the tree, so it needs no token for a private repository — which is also why the
    re-pin is `--sync` against a checkout and is never run by CI.
    """
    assert "uv run python scripts/sync_doctrine.py --check" in LINT, (
        "nothing in CI notices a vendored artefact, a model parameter or a bar line moving"
    )
    assert "uv run python scripts/check_doctrine.py" in LINT, (
        "the guard on the six mechanisms was displaced rather than joined"
    )
    assert "sync_doctrine.py --sync" not in LINT, (
        "CI would re-pin to her branch tip by itself, which is the one thing a ruling is for"
    )


def test_the_pull_request_template_asks_for_her_sentence_and_where_it_is_written() -> None:
    """§5.1 in the one place a change to her artifacts is read by a person.

    The drift check can see that a value moved; it cannot see whether she ruled it. That is the
    template's half, and it asks for the two things a ruling is — her words, and where they are
    written — rather than for a checkbox saying one exists.
    """
    assert TEMPLATE_PATH.exists(), "there is no template, so nothing asks the question"
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    assert "Marcia's artifacts" in template
    assert "never an engineering default" in template, "§5.1's sentence is not quoted"
    for asked in ("Her words:", "Where it is written:"):
        assert asked in template, f"the template does not ask for {asked!r}"
    for governed in ("prompt", "model id", "ladder", "effort", "token budget"):
        assert governed in template, f"the template does not name {governed!r} as governed"


def test_the_way_in_says_where_the_doctrine_is() -> None:
    """One line each in `AGENTS.md` and `README.md`, naming the path and the pin.

    Its header binds "every change to this repository" and tells the reader to read it before
    touching a prompt, the turn loop, the model seam or the canvas. A binding document nothing
    points at is read by whoever already knew about it.
    """
    for name in ("AGENTS.md", "README.md"):
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        assert "docs/doctrine/" in text, f"{name} does not say where the doctrine is"
        assert "DOCTRINE.md" in text, f"{name} does not name it"

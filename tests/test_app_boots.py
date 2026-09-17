"""Whether the application starts at all — which nothing else here was asking.

Four gates run on every pull request and none of them imports the app the way a server does.
`ruff` and `mypy` read the source without executing it; `pytest` executes it, but through a
suite whose collection order imports modules in an order that can break a cycle by accident.
Nine branches of one stack were green together while one of them could not boot, and the
green was not luck — it was **order**: run `tests/test_facilitator_role_gate.py` on its own
and it errors, run the whole suite and it passes.

So this file asks the only question that matters first: does `app.main` import in a clean
interpreter? And beside it, the rule whose breach made the answer no.

Both are repository-wide rather than about one slice. The defect they caught belonged to
ENG-450; the hole they close is that nothing anywhere proved the server starts.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The DTO layer. `app/models` is request and response shapes, and it sits *below* the
#: services that build them — a module here reaching upward is the inversion that closes an
#: import cycle, and Python only complains about it in whichever order it happens to hit.
DTO_DIR = REPO_ROOT / "app" / "models"


def test_the_application_imports_in_a_clean_interpreter() -> None:
    """A fresh process, because that is what a server is and what the suite is not.

    `subprocess` and not a bare `import app.main`: this suite has already imported half the
    application by the time any test runs, so an in-process import proves only that whatever
    order pytest happened to use worked. A cycle survives exactly that and no more.
    """
    finished = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "DATABASE_URL": "sqlite+aiosqlite:///./boot-check.db",
            "JWT_SECRET_KEY": "test-secret-for-pytest-only",
            "INNGEST_DEV": "1",
        },
    )

    assert finished.returncode == 0, (
        f"a aplicação não importa num processo limpo:\n{finished.stderr}"
    )


def test_no_dto_module_reaches_up_into_the_service_layer() -> None:
    """The rule whose breach let the cycle close, checked where it can be seen.

    `app/models/internalization_room.py` imported two enums out of `app/services/...`, and
    importing anything inside a package runs that package's `__init__` — which imported a
    service that imported a service that imported this module back, half-built. The cycle sat
    there latently for as long as no service on that path happened to need a DTO.

    Stated as a layering rule rather than as "no import cycles", because the tree has 294
    cycles by the letter and almost all of them are a package importing its own children,
    which is ordinary. This is the one shape that is not ordinary and the one that bit.
    """
    reaching = {
        str(source.relative_to(REPO_ROOT)): sorted(_service_imports(source))
        for source in sorted(DTO_DIR.rglob("*.py"))
        if _service_imports(source)
    }

    assert reaching == {}, (
        "um módulo de DTO importa da camada de serviço, que é a inversão que fecha o ciclo: "
        f"{reaching}"
    )


def _service_imports(source: Path) -> set[str]:
    """Module-level imports of `app.services.*` — a deferred one is not this cycle."""
    tree = ast.parse(source.read_text(encoding="utf-8"))
    return {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.level == 0
        and node.module
        and node.module.startswith("app.services")
    }

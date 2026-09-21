"""The name of the database this pytest process works in.

It has to be in the environment before the conftest reaches its first app import, because
the app builds its engine from `DATABASE_URL` when it is imported — far too late for a
fixture. It lives here rather than in the conftest because only a call may stand ahead of
that import (ruff refuses an assignment there, E402), and the rule below is more than a call.

**One file per process.** Under xdist the controller imports the conftest as well, names a
database of its own, and the workers inherit that name through their environment — a
`setdefault` in a worker is then a no-op and all four work in one file. So the generated URL
is published beside the value it generated, and a process whose inherited `DATABASE_URL` is
exactly that value names its own instead. A `DATABASE_URL` the caller set matches nothing
here and is left alone, and the file it names is the caller's to keep — which is also why a
run that names one has to be serial: one file cannot be four workers' own.

The pid is what makes the name unique and the worker's name says whose file it is. Both,
because neither is enough: two workers of one run share the controller's name under a
pid-blind scheme, and a child process a worker spawns inherits `PYTEST_XDIST_WORKER` without
being that worker.
"""

import os
import tempfile
from pathlib import Path

#: The URL this suite generated, carried in the environment so a process can tell it apart
#: from one a caller asked for.
GENERATED = "SHEMA_TEST_GENERATED_DATABASE_URL"

_PREFIX = "sqlite+aiosqlite:///"


def database_environment_for_this_process() -> dict[str, str]:
    """What to put in the environment, and nothing at all when the caller named a database."""
    inherited = os.environ.get("DATABASE_URL")
    if inherited is not None and inherited != os.environ.get(GENERATED):
        return {}

    worker = os.environ.get("PYTEST_XDIST_WORKER")
    owner = f"{worker}-{os.getpid()}" if worker else os.getpid()
    url = f"{_PREFIX}{Path(tempfile.gettempdir()) / f'shema-api-test-{owner}.db'}"
    return {"DATABASE_URL": url, GENERATED: url}


def the_generated_database_file() -> Path | None:
    """The file to remove when the run ends, and `None` when the caller named the database."""
    generated = os.environ.get(GENERATED)
    if generated is None or generated != os.environ.get("DATABASE_URL"):
        return None
    return Path(generated.removeprefix(_PREFIX))

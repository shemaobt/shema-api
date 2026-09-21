"""The name of the database this pytest process works in, settled before the app is imported.

The app builds its engine from `DATABASE_URL` when it is imported, so the name has to be in
the environment before the conftest reaches its first app import — far too late for a
fixture, and too early for the conftest to work it out in place: ruff refuses a module-level
assignment ahead of that import (E402), and only calls may stand there. So the whole of it
lives here, in two calls the conftest makes — and the first hands back an environment
rather than setting one, because ruff excuses only a call on `os.environ` itself from E402.

**One file per process.** Under xdist the controller imports the conftest as well, names a
database of its own, and the workers inherit that name through their environment — a
`setdefault` in a worker is then a no-op and all four work in one file (measured: two workers
on `shema-api-test-<controller pid>.db`). So the generated name is published beside the value
it generated, and a process whose inherited `DATABASE_URL` is exactly that value names its
own instead. A `DATABASE_URL` the caller set matches nothing here and is left alone, and the
file it names is the caller's to keep.

The pid is what makes the name unique, and the worker's name is there to say whose file it
is. Both, because neither is enough on its own: two workers of one run share the controller's
name under a pid-blind scheme, and a child process a worker spawns inherits
`PYTEST_XDIST_WORKER` without being that worker — `test_the_suite_runs_twice_at_once` starts
two of them at once, and under a pid-less name they collided.
"""

import os
import tempfile
from pathlib import Path

#: The URL this suite generated, carried in the environment so a child process can tell it
#: apart from one a caller asked for.
GENERATED = "SHEMA_TEST_GENERATED_DATABASE_URL"

_PREFIX = "sqlite+aiosqlite:///"


def the_database_of_this_process() -> dict[str, str]:
    """What to put in the environment, and nothing at all when the caller named a database."""
    inherited = os.environ.get("DATABASE_URL")
    if inherited is not None and inherited != os.environ.get(GENERATED):
        return {}

    worker = os.environ.get("PYTEST_XDIST_WORKER")
    owner = f"{worker}-{os.getpid()}" if worker else os.getpid()
    url = f"{_PREFIX}{Path(tempfile.gettempdir()) / f'shema-api-test-{owner}.db'}"
    return {"DATABASE_URL": url, GENERATED: url}


def the_database_this_process_generated() -> Path | None:
    """The file to remove when the run ends, and `None` when the caller named the database."""
    generated = os.environ.get(GENERATED)
    if generated is None or generated != os.environ.get("DATABASE_URL"):
        return None
    return Path(generated.removeprefix(_PREFIX))

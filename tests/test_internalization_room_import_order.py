import subprocess
import sys

import pytest

ROOM_MODULES = (
    "app.services.internalization_room.passage_turn",
    "app.services.internalization_room.panorama_turn",
    "app.services.internalization_room.verdict_turn",
    "app.services.internalization_room.validated_turn",
    "app.services.internalization_room.run_turn",
)


@pytest.mark.parametrize("module", ROOM_MODULES)
def test_a_turn_module_reached_first_in_a_fresh_interpreter_still_imports(module: str) -> None:
    """A cycle in the room's own graph resolves in whatever order the first importer used.

    A worker or a script that reaches for one of these directly is that first importer, and
    under a graph that pointed both ways it would raise at boot while the whole suite stayed
    green — pytest collects `run_turn` early enough to hide it every time. Each module gets
    its own interpreter here, so no earlier import can be the reason this one worked.
    """
    finished = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
    )

    assert finished.returncode == 0, finished.stderr

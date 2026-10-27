import json
import logging
import re
from datetime import UTC, datetime, timedelta

from app.core.logging import log_formatter, setup_logging


def test_setup_logging_configures_root_logger():
    setup_logging()
    root = logging.getLogger()
    assert len(root.handlers) > 0
    assert root.level == logging.INFO


def test_setup_logging_suppresses_noisy_loggers():
    setup_logging()
    assert logging.getLogger("uvicorn.access").level == logging.WARNING
    assert logging.getLogger("sqlalchemy.engine").level == logging.WARNING


NAME = "app.services.shema.export_projects"
EXTRA = {
    "shema_operation": "export_projects",
    "shema_scope_regions": ["africa", "other"],
    "shema_scope_global": False,
    "shema_projects": 3,
}
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _line(production: bool, level: int, extra: dict[str, object]) -> str:
    record = logging.getLogger(NAME).makeRecord(
        NAME, level, __file__, 1, "shema projects exported", (), None, extra=extra
    )
    return log_formatter(production=production).format(record)


def _close_to_now(stamp: str) -> bool:
    return abs(datetime.fromisoformat(stamp) - datetime.now(UTC)) < timedelta(minutes=1)


def test_a_standard_library_line_carries_its_fields_level_and_time_in_production():
    line = json.loads(_line(True, logging.WARNING, EXTRA))

    assert _close_to_now(line.pop("timestamp"))
    assert line == {
        "event": "shema projects exported",
        "level": "warning",
        "logger": NAME,
        **EXTRA,
    }


def test_a_standard_library_line_carries_its_fields_level_and_time_on_the_console():
    text = ANSI.sub("", _line(False, logging.INFO, EXTRA))

    stamp, rest = text.split(" ", 1)
    assert _close_to_now(stamp)
    assert rest.startswith("[info")
    assert "shema projects exported" in rest
    assert f"[{NAME}]" in rest
    assert "shema_operation=export_projects" in rest
    assert "shema_projects=3" in rest


def test_an_extra_cannot_rewrite_the_level_the_logger_or_the_time():
    forged = {"level": "debug", "logger": "elsewhere", "timestamp": "yesterday"}
    line = json.loads(_line(True, logging.ERROR, forged))

    assert (line["level"], line["logger"]) == ("error", NAME)
    assert _close_to_now(line["timestamp"])

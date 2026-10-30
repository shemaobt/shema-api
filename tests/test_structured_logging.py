import json
import logging

import structlog

from app.core.logging import setup_logging


def test_setup_logging_configures_root_logger():
    setup_logging()
    root = logging.getLogger()
    assert len(root.handlers) > 0
    assert root.level == logging.INFO


def test_setup_logging_suppresses_noisy_loggers():
    setup_logging()
    assert logging.getLogger("uvicorn.access").level == logging.WARNING
    assert logging.getLogger("sqlalchemy.engine").level == logging.WARNING


def _json_line(capsys):
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_a_stdlib_log_line_carries_level_timestamp_logger_and_event(monkeypatch, capsys):
    monkeypatch.setenv("ENV", "production")
    setup_logging()
    logging.getLogger("x").warning("y")
    line = _json_line(capsys)
    assert line["level"] == "warning"
    assert line["logger"] == "x"
    assert line["event"] == "y"
    assert "timestamp" in line


def test_a_structlog_line_keeps_level_timestamp_logger_and_event(monkeypatch, capsys):
    monkeypatch.setenv("ENV", "production")
    setup_logging()
    structlog.get_logger("x").warning("y")
    line = _json_line(capsys)
    assert line["level"] == "warning"
    assert line["logger"] == "x"
    assert line["event"] == "y"
    assert "timestamp" in line

"""One shape for every log line the server writes — the message, its level, its time, its fields.

Every module here logs through the standard library, ``logging.getLogger(__name__)``, and puts
what a line is about in ``extra=``; none calls structlog's own logger. To structlog such a record
is *foreign*: ``ProcessorFormatter`` runs it through ``foreign_pre_chain`` and nothing else before
the renderer, and with no chain there a line left as its message alone — in production
``{"event": "shema projects exported"}``, without the level, the time or any of the fields the
Shemá module writes as its operational trail (OBT-650).

So a foreign record walks the chain a structlog call walks (:data:`_CHAIN`), its fields added
first by ``ExtraAdder``: they enter where a structlog call's keyword arguments would, and the
chain's own keys — ``level``, ``logger``, ``timestamp`` — stay the chain's to write over them.
``event`` is the record's message before any of it runs, so an extra by that name would replace
the message: the four names are the formatter's, and no call passes them.

**Every extra, not an allowlist.** A list here would drop the next field a module adds, in
silence — the defect this closes. What may reach a line is the call site's question, answered
where the record is known (``_redaction.log_reference`` in the Shemá module).
"""

import logging
import os
import sys

import structlog

#: What every line passes through on its way to the renderer, whichever logger wrote it.
_CHAIN: tuple[structlog.types.Processor, ...] = (
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.UnicodeDecoder(),
)


def log_formatter(*, production: bool) -> structlog.stdlib.ProcessorFormatter:
    """The root handler's formatter: one JSON object per line in production, columns elsewhere.

    ``setup_logging`` installs it, and a test that reads a line builds the same one, so what the
    test reads is what the server prints.
    """
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer() if production else structlog.dev.ConsoleRenderer()
    )
    return structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=[structlog.stdlib.ExtraAdder(), *_CHAIN],
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )


def setup_logging() -> None:
    production = os.environ.get("ENV", "development") == "production"

    structlog.configure(
        processors=[*_CHAIN, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(log_formatter(production=production))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StageClock:
    started: float = field(default_factory=time.monotonic)
    stages: dict[str, int] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)

    def reading(self) -> str:
        spent = [f"{name}={ms}ms" for name, ms in self.stages.items()]
        counted = [f"{name}={count}" for name, count in self.counts.items()]
        return " ".join(spent + counted)

    def server_timing(self) -> str:
        return ", ".join(f"{name};dur={ms}" for name, ms in self.stages.items())


_OPEN: ContextVar[StageClock | None] = ContextVar("stage_clock", default=None)


def _since(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


@contextmanager
def stopwatch(tag: str, session_id: str) -> Iterator[StageClock]:
    clock = StageClock()
    token = _OPEN.set(clock)
    try:
        yield clock
    finally:
        _OPEN.reset(token)
        clock.stages["total"] = _since(clock.started)
        logger.info("%s session=%s %s", tag, session_id, clock.reading())


@contextmanager
def stage(name: str) -> Iterator[None]:
    clock = _OPEN.get()
    started = time.monotonic()
    try:
        yield
    finally:
        if clock is not None:
            clock.stages[name] = clock.stages.get(name, 0) + _since(started)


def current_clock() -> StageClock | None:
    return _OPEN.get()


def adopt(clock: StageClock | None) -> None:
    mine = _OPEN.get()
    if clock is not None and mine is not None:
        mine.stages.update(clock.stages)


def count(name: str, value: int) -> None:
    clock = _OPEN.get()
    if clock is not None:
        clock.counts[name] = value

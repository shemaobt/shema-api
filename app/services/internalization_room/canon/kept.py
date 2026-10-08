"""The canon a session opened with, kept under its pin until its passage is approved."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import _CacheInfo, lru_cache
from pathlib import Path
from typing import Concatenate, Generic, ParamSpec, TypeVar

from app.core.canon_pin import pinned_commit

CANON_DIR = Path(__file__).parent
KEPT_DIR = CANON_DIR / "kept"
DEPLOYED_PIN = CANON_DIR / "vendor" / "VENDOR_PIN"

_READING: ContextVar[Path | None] = ContextVar("kept_canon", default=None)

P = ParamSpec("P")
R = TypeVar("R")


def deployed_pin() -> str:
    return pinned_commit(DEPLOYED_PIN.read_text(encoding="utf-8"))


@contextmanager
def reading_the_canon_of(pin: str | None) -> Iterator[None]:
    token = _READING.set(None if pin is None or pin == deployed_pin() else KEPT_DIR / pin)
    try:
        yield
    finally:
        _READING.reset(token)


def canon_path(path: Path) -> Path:
    kept = _READING.get()
    return path if kept is None else kept / path.relative_to(CANON_DIR)


class PerCanon(Generic[P, R]):
    def __init__(self, read: Callable[P, R], maxsize: int) -> None:
        def keyed(kept: Path | None, /, *args: P.args, **kwargs: P.kwargs) -> R:
            return read(*args, **kwargs)

        self._cache = lru_cache(maxsize=maxsize)(keyed)
        self._read: Callable[Concatenate[Path | None, P], R] = self._cache

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        return self._read(_READING.get(), *args, **kwargs)

    def cache_clear(self) -> None:
        self._cache.cache_clear()

    def cache_info(self) -> _CacheInfo:
        return self._cache.cache_info()


def per_canon(maxsize: int) -> Callable[[Callable[P, R]], PerCanon[P, R]]:
    def cached(read: Callable[P, R]) -> PerCanon[P, R]:
        return PerCanon(read, maxsize)

    return cached

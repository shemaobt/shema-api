from __future__ import annotations

import asyncio
import logging
from functools import partial

from app.services.platform.tts import Voicing

logger = logging.getLogger(__name__)

_IN_FLIGHT: dict[str, asyncio.Task[bytes]] = {}


def fly(key: str, voice: Voicing) -> asyncio.Task[bytes]:
    flight = _IN_FLIGHT.get(key)
    if flight is None:
        flight = asyncio.create_task(voice())
        _IN_FLIGHT[key] = flight
        flight.add_done_callback(partial(_landed, key))
    return flight


def in_flight(key: str) -> asyncio.Task[bytes] | None:
    return _IN_FLIGHT.get(key)


def forget_flights() -> None:
    _IN_FLIGHT.clear()


def _landed(key: str, flight: asyncio.Task[bytes]) -> None:
    if _IN_FLIGHT.get(key) is flight:
        del _IN_FLIGHT[key]
    if flight.cancelled():
        return
    error = flight.exception()
    if error is not None:
        logger.warning("a clip could not be voiced: %s", type(error).__name__)

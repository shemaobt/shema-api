from fastapi import APIRouter

from app.api.internalization_room import (
    attended,
    back_translation,
    devices,
    passages,
    questions,
    release,
    segments,
    sessions,
    takes,
    voice,
)

router = APIRouter()

for _sub in (
    voice,
    sessions,
    passages,
    back_translation,
    segments,
    questions,
    takes,
    release,
    devices,
    attended,
):
    for route in _sub.router.routes:
        router.routes.append(route)

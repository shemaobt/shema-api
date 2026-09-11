from fastapi import APIRouter

from app.api.internalization_room import (
    attended,
    back_translation,
    coverage_channel,
    devices,
    passages,
    questions,
    release,
    segments,
    sessions,
    takes,
    text_seam,
    voice,
)

router = APIRouter()

for _sub in (
    voice,
    sessions,
    coverage_channel,
    passages,
    back_translation,
    segments,
    questions,
    takes,
    release,
    devices,
    attended,
    text_seam,
):
    for route in _sub.router.routes:
        router.routes.append(route)

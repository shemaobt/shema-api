from fastapi import APIRouter

from app.api.internalization_room import (
    attended,
    back_translation,
    coverage_channel,
    devices,
    passages,
    questions,
    release,
    retroverification,
    segments,
    sessions,
    takes,
    text_seam,
    text_seam_back_translation,
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
    retroverification,
    devices,
    attended,
    text_seam,
    text_seam_back_translation,
):
    for route in _sub.router.routes:
        router.routes.append(route)

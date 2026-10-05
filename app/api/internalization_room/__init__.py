from fastapi import APIRouter

from app.api.internalization_room import (
    attended,
    back_translation,
    conversation,
    coverage_channel,
    devices,
    fixed_lines,
    golden_doors,
    passages,
    questions,
    release,
    retroverification,
    segments,
    sessions,
    takes,
    text_seam_back_translation,
    voice,
)

router = APIRouter()

for _sub in (
    voice,
    sessions,
    coverage_channel,
    passages,
    fixed_lines,
    back_translation,
    segments,
    questions,
    takes,
    release,
    retroverification,
    conversation,
    devices,
    attended,
    golden_doors,
    text_seam_back_translation,
):
    for route in _sub.router.routes:
        router.routes.append(route)

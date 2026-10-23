from fastapi import APIRouter

from app.api.internalization_room import (
    archives,
    attended,
    back_translation,
    conversation,
    coverage_channel,
    demo,
    devices,
    external_check,
    fixed_lines,
    golden_doors,
    outside_listeners,
    passages,
    questions,
    release,
    retroverification,
    scene_rehearsals,
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
    scene_rehearsals,
    release,
    external_check,
    outside_listeners,
    retroverification,
    conversation,
    devices,
    attended,
    golden_doors,
    text_seam_back_translation,
    archives,
    demo,
):
    for route in _sub.router.routes:
        router.routes.append(route)

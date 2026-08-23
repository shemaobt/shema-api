from fastapi import APIRouter

from app.api.internalization_room import (
    back_translation,
    passages,
    questions,
    release,
    sessions,
    takes,
    voice,
)

router = APIRouter()

for _sub in (voice, sessions, passages, back_translation, questions, takes, release):
    for route in _sub.router.routes:
        router.routes.append(route)

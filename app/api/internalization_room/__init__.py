from fastapi import APIRouter

from app.api.internalization_room import back_translation, sessions, voice

router = APIRouter()

for _sub in (voice, sessions, back_translation):
    for route in _sub.router.routes:
        router.routes.append(route)

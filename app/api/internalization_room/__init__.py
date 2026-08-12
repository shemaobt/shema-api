from fastapi import APIRouter

from app.api.internalization_room import back_translation, questions, sessions, takes, voice

router = APIRouter()

for _sub in (voice, sessions, back_translation, questions, takes):
    for route in _sub.router.routes:
        router.routes.append(route)

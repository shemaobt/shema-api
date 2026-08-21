from fastapi import APIRouter

from app.api.internalization_room import sessions, voice

router = APIRouter()

for _sub in (voice, sessions):
    for route in _sub.router.routes:
        router.routes.append(route)

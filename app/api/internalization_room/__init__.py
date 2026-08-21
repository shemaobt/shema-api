from fastapi import APIRouter

from app.api.internalization_room import voice

router = APIRouter()

for _sub in (voice,):
    for route in _sub.router.routes:
        router.routes.append(route)

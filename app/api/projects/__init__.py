from fastapi import APIRouter

from app.api.projects import access, core, journey, phases

router = APIRouter()

for _sub in (core, access, phases, journey):
    for route in _sub.router.routes:
        router.routes.append(route)

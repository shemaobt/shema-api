from fastapi import APIRouter

from app.api.shema import health

router = APIRouter()

for _sub in (health,):
    for route in _sub.router.routes:
        router.routes.append(route)

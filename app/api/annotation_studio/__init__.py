from fastapi import APIRouter

from app.api.annotation_studio import (
    audio,
    export,
    languages,
    members,
    results,
    speakers,
    tier_a,
    tier_b,
    tier_c,
)

router = APIRouter()

for _sub in (languages, members, speakers, tier_a, tier_b, tier_c, export, results, audio):
    for route in _sub.router.routes:
        router.routes.append(route)

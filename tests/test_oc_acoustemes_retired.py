"""The acousteme HTTP surface is retired (ENG-290).

It served the recorded voices of indigenous storytellers — LGPD-sensitive personal data,
exactly what PRD §12 calls sensitive — to **any authenticated Tripod user**: no app
role, no project scoping, nothing but `Depends(get_current_user)`. The collection
listing beside it handed over every audio id, so there was not even a slug to guess.

Nothing consumed it. The routes were twenty hours old when this landed, and the one
client they were built for (`shemaobt/beads`) predates them by four months and reads a
checked-in static `acoustemes.json`, never the API.

The *service* survives. The corpus importer writes through it, and the Sound Necklace
signs through it. What is gone is the ungated door standing in front of it.

Both guards below read `app.routes`, not `app.openapi()`: a route mounted with
``include_in_schema=False`` is served but never published, so a schema-based check
would stay green while the surface is back — the one regression this file exists to
catch.
"""

from __future__ import annotations

from fastapi.routing import APIRoute

RETIRED_PREFIX = "/api/oc/acoustemes"


def test_no_acousteme_route_is_served_at_this_prefix():
    from app.main import app

    leaking = [
        route.path for route in app.routes if getattr(route, "path", "").startswith(RETIRED_PREFIX)
    ]

    assert not leaking, f"the acousteme HTTP surface is back: {leaking}"


# The DTOs the retired routes served. Named exactly rather than matched by prefix: the
# Sound Necklace's own AcoustemeEnvelope is served, legitimately, by its project-scoped
# listing — a prefix match would flag that and the guard would be deleted as noisy.
RETIRED_DTOS = {
    "AcoustemeArtifactResponse",
    "AcoustemeListItem",
    "AcoustemeStreamResponse",
    "AcoustemeAudioResponse",
}


def test_no_route_anywhere_serves_the_retired_dtos():
    from app.main import app

    served = {
        getattr(route.response_model, "__name__", None)
        for route in app.routes
        if isinstance(route, APIRoute) and route.response_model is not None
    }
    serving = RETIRED_DTOS & served

    assert not serving, f"a route is serving a retired acousteme DTO again: {sorted(serving)}"


async def test_the_service_beneath_it_still_resolves_an_artifact(db_session):
    from app.db.models.oc_acousteme import OC_AcoustemeArtifact
    from app.services.oral_collector import acousteme_service

    db_session.add(
        OC_AcoustemeArtifact(
            audio_id="ruth-retirement-probe",
            codebook_version="terena-xlsr53-k100-v1",
            collection="terena-ruth",
            status="ready",
            gcs_bucket="terena-pilot",
            gcs_object="acoustemes/ruth-retirement-probe.json.gz",
            audio_bucket="terena-pilot",
            audio_object="ruth/probe.mp3",
        )
    )
    await db_session.commit()

    stored = await acousteme_service.get_artifact(db_session, "ruth-retirement-probe")
    assert stored.audio_object == "ruth/probe.mp3"

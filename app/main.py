import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.access_requests import router as access_requests_router
from app.api.annotation_studio import router as annotation_studio_router
from app.api.apps import router as apps_router
from app.api.auth import router as auth_router
from app.api.bhsa import router as bhsa_router
from app.api.book_context import router as book_context_router
from app.api.books import router as books_router
from app.api.health import router as health_router
from app.api.languages import router as languages_router
from app.api.meaning_maps import router as meaning_maps_router
from app.api.notifications import router as notifications_router
from app.api.oral_collector.genres import genres_router as oc_genres_router
from app.api.oral_collector.genres import subcategories_router as oc_subcategories_router
from app.api.oral_collector.invites import invites_router as oc_invites_router
from app.api.oral_collector.projects import projects_router as oc_projects_router
from app.api.oral_collector.recordings import recordings_router as oc_recordings_router
from app.api.oral_collector.stats import stats_router as oc_stats_router
from app.api.oral_collector.storytellers import (
    project_storytellers_router as oc_project_storytellers_router,
)
from app.api.oral_collector.storytellers import (
    storytellers_router as oc_storytellers_router,
)
from app.api.organizations import router as organizations_router
from app.api.pericopes import router as pericopes_router
from app.api.phases import router as phases_router
from app.api.places import router as places_router
from app.api.platform import router as platform_router
from app.api.project_health import router as project_health_router
from app.api.projects import router as projects_router
from app.api.public import router as public_router
from app.api.public_requests import router as public_requests_router
from app.api.rag import router as rag_router
from app.api.roles import router as roles_router
from app.api.sound_necklace import router as sound_necklace_router
from app.api.translation_helper import router as translation_helper_router
from app.api.uploads import router as uploads_router
from app.api.users import router as users_router
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, close_db, init_db
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.qdrant import close_qdrant, init_qdrant
from app.core.rate_limit import limiter
from app.services.bhsa import loader
from app.services.meaning_map.seed_books import seed_books
from app.services.project_health.prompts.seed_prompts import seed_default_prompts
from app.services.translation_helper.seed_agent_prompts import seed_agent_prompts


def _load_bhsa_background() -> None:

    try:
        print("[STARTUP] Loading BHSA data in background...", flush=True)
        loader.load()
        print("[STARTUP] BHSA data loaded successfully!", flush=True)
    except Exception as e:
        print(f"[STARTUP] Failed to load BHSA data: {e}", flush=True)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    await init_db()
    async with AsyncSessionLocal() as db:
        seeded = await seed_books(db)
        if seeded:
            print(f"[STARTUP] Seeded {seeded} Bible books.", flush=True)
        seeded_prompts = await seed_agent_prompts(db)
        if seeded_prompts:
            print(
                f"[STARTUP] Seeded {seeded_prompts} translation-helper agent prompts.",
                flush=True,
            )
        seeded_ph_prompts = await seed_default_prompts(db)
        if seeded_ph_prompts:
            print(
                f"[STARTUP] Seeded {seeded_ph_prompts} project-health agent prompts.",
                flush=True,
            )
    await init_qdrant()
    threading.Thread(target=_load_bhsa_background, daemon=True).start()
    try:
        yield
    finally:
        await close_qdrant()
        await close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Tripod Backend", version="0.1.0", lifespan=lifespan)

    app.state.limiter = limiter
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")  # type: ignore[arg-type]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Neither is CORS-safelisted: without this a browser client cannot read them at all.
        # The sound-necklace autosave version guard rides on ETag; X-Tts-Cached is what makes
        # TTS cache warming observable.
        expose_headers=["ETag", "X-Tts-Cached"],
    )

    app.include_router(health_router)
    app.include_router(
        access_requests_router,
        prefix="/api/access-requests",
        tags=["access-requests"],
    )
    app.include_router(apps_router, prefix="/api/apps", tags=["apps"])
    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    app.include_router(roles_router, prefix="/api/roles", tags=["roles"])
    app.include_router(platform_router, prefix="/api/platform", tags=["platform"])
    app.include_router(uploads_router, prefix="/api/uploads", tags=["uploads"])
    app.include_router(users_router, prefix="/api/users", tags=["users"])
    app.include_router(languages_router, prefix="/api/languages", tags=["languages"])
    app.include_router(organizations_router, prefix="/api/organizations", tags=["organizations"])
    app.include_router(places_router, prefix="/api/places", tags=["places"])
    app.include_router(projects_router, prefix="/api/projects", tags=["projects"])
    app.include_router(public_router, prefix="/api/public", tags=["public"])
    app.include_router(
        public_requests_router,
        prefix="/api/public-requests",
        tags=["public-requests"],
    )
    app.include_router(phases_router, prefix="/api/phases", tags=["phases"])
    app.include_router(books_router, prefix="/api/books", tags=["books"])
    app.include_router(pericopes_router, prefix="/api/pericopes", tags=["pericopes"])
    app.include_router(meaning_maps_router, prefix="/api/meaning-maps", tags=["meaning-maps"])
    app.include_router(
        annotation_studio_router, prefix="/api/annotation-studio", tags=["annotation-studio"]
    )
    app.include_router(
        sound_necklace_router,
        prefix="/api/sound-necklace",
        tags=["sound-necklace"],
    )
    app.include_router(
        project_health_router,
        prefix="/api/project-health",
        tags=["project-health"],
    )
    app.include_router(
        translation_helper_router,
        prefix="/api/translation-helper",
        tags=["translation-helper"],
    )
    app.include_router(notifications_router, prefix="/api/notifications", tags=["notifications"])
    app.include_router(rag_router, prefix="/api/rag", tags=["rag"])
    app.include_router(bhsa_router, prefix="/api/bhsa", tags=["bhsa"])
    app.include_router(
        book_context_router,
        prefix="/api/book-context",
        tags=["book-context"],
    )

    app.include_router(oc_genres_router, prefix="/api/oc/genres", tags=["oc-genres"])
    app.include_router(
        oc_subcategories_router,
        prefix="/api/oc/subcategories",
        tags=["oc-subcategories"],
    )
    app.include_router(
        oc_projects_router,
        prefix="/api/oc/projects",
        tags=["oc-projects"],
    )
    app.include_router(
        oc_invites_router,
        prefix="/api/oc",
        tags=["oc-invites"],
    )
    app.include_router(
        oc_recordings_router,
        prefix="/api/oc/recordings",
        tags=["oc-recordings"],
    )
    app.include_router(
        oc_stats_router,
        prefix="/api/oc",
        tags=["oc-stats"],
    )
    app.include_router(
        oc_project_storytellers_router,
        prefix="/api/oc/projects",
        tags=["oc-storytellers"],
    )
    app.include_router(
        oc_storytellers_router,
        prefix="/api/oc/storytellers",
        tags=["oc-storytellers"],
    )

    register_exception_handlers(app)

    from inngest.fast_api import serve

    from app.core.inngest_client import inngest_client
    from app.inngest import ALL_FUNCTIONS

    serve(app, inngest_client, ALL_FUNCTIONS)

    return app


app = create_app()

"""The `platform` layer: what belongs to no app.

**There is no `_deps.py` with an `APP_KEY` here, and that is the statement.** App packages
gate on `require_app_access(APP_KEY)`; the platform serves any authenticated user, from any
app — the precedent is `app/api/uploads.py`, which uses only `get_current_user`.

`common/` = helpers with no external dependency (`get_or_raise`).
`platform/` = app-agnostic services backed by an external provider or by infrastructure (TTS,
storage). Natural tenants in future PRs: `common/email.py`, `services/storage/upload.py` and
`api/uploads.py`.
"""

from fastapi import APIRouter

from app.api.platform.stt import router as stt_router
from app.api.platform.tts import router as tts_router

router = APIRouter()
router.include_router(tts_router)
router.include_router(stt_router)

__all__ = ["router"]

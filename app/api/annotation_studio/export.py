import json

from fastapi import APIRouter, status
from fastapi.responses import RedirectResponse

from app.api.annotation_studio._deps import CurrentUser, Db
from app.core.exceptions import NotFoundError
from app.models.annotation_studio import ExportDetail, ExportResponse
from app.services.annotation_studio import access, export_service, readiness_service

router = APIRouter()


@router.post(
    "/languages/{language_id}/exports",
    response_model=ExportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def build_export(language_id: str, db: Db, user: CurrentUser) -> ExportResponse:
    await access.assert_language_access(db, user, language_id)
    export = await export_service.build_export(db, language_id, user.id)
    return ExportResponse.model_validate(export)


@router.get("/languages/{language_id}/exports", response_model=list[ExportResponse])
async def list_exports(language_id: str, db: Db, user: CurrentUser) -> list[ExportResponse]:
    await access.assert_language_access(db, user, language_id)
    exports = await export_service.list_exports(db, language_id)
    return [ExportResponse.model_validate(e) for e in exports]


@router.get("/exports/{export_id}", response_model=ExportDetail)
async def export_detail(export_id: str, db: Db, user: CurrentUser) -> ExportDetail:
    language_id = await access.language_id_for_export(db, export_id)
    await access.assert_language_access(db, user, language_id)
    export = await export_service.get_export(db, export_id)
    detail = ExportDetail.model_validate(export)
    detail.manifest = json.loads(export.manifest_json) if export.manifest_json else None
    detail.download_path = (
        f"/api/annotation-studio/exports/{export.id}/download" if export.bundle_key else None
    )
    return detail


@router.delete("/exports/{export_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_export(export_id: str, db: Db, user: CurrentUser) -> None:
    language_id = await access.language_id_for_export(db, export_id)
    await access.assert_language_access(db, user, language_id)
    await export_service.delete_export(db, export_id)


@router.get("/exports/{export_id}/download")
async def download_export(export_id: str, db: Db, user: CurrentUser) -> RedirectResponse:
    language_id = await access.language_id_for_export(db, export_id)
    await access.assert_language_access(db, user, language_id)
    url = await export_service.download_url(db, export_id)
    if not url:
        raise NotFoundError("Export bundle is not ready")
    return RedirectResponse(url=url)


@router.get("/languages/{language_id}/readiness")
async def readiness(language_id: str, db: Db, user: CurrentUser) -> dict:
    await access.assert_language_access(db, user, language_id)
    return await readiness_service.compute_readiness(db, language_id)

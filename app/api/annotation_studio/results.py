from fastapi import APIRouter, status

from app.api.annotation_studio._deps import CurrentUser, Db
from app.db.models.as_analysis_result import AsAnalysisResult
from app.models.annotation_studio import (
    PlotPresignRequest,
    PlotPresignResponse,
    ResultCreate,
    ResultResponse,
)
from app.services.annotation_studio import access, results_service

router = APIRouter()


def _to_response(result: AsAnalysisResult, plots: dict[str, str]) -> ResultResponse:
    return ResultResponse(
        id=result.id,
        language_id=result.language_id,
        export_id=result.export_id,
        recommended_layer=result.recommended_layer,
        tiers=result.tiers,
        created_at=result.created_at,
        plots=plots,
    )


@router.post(
    "/languages/{language_id}/results",
    response_model=ResultResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_result(
    language_id: str, payload: ResultCreate, db: Db, user: CurrentUser
) -> ResultResponse:
    await access.assert_language_access(db, user, language_id)
    result = await results_service.create_result(
        db, language_id, payload.results_json, payload.export_id
    )
    return _to_response(result, {})


@router.get("/languages/{language_id}/results", response_model=list[ResultResponse])
async def list_results(language_id: str, db: Db, user: CurrentUser) -> list[ResultResponse]:
    await access.assert_language_access(db, user, language_id)
    results = await results_service.list_results(db, language_id)
    return [_to_response(r, results_service.plot_urls(r)) for r in results]


@router.post("/results/{result_id}/plots", response_model=PlotPresignResponse)
async def presign_plot(
    result_id: str, payload: PlotPresignRequest, db: Db, user: CurrentUser
) -> PlotPresignResponse:
    language_id = await access.language_id_for_result(db, result_id)
    await access.assert_language_access(db, user, language_id)
    presigned = await results_service.presign_plot(
        db, result_id, payload.name, payload.content_type
    )
    return PlotPresignResponse(
        storage_key=presigned.storage_key,
        upload_url=presigned.url,
        method=presigned.method,
        required_headers=presigned.required_headers,
        expires_in=presigned.expires_in,
    )

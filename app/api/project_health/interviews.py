from fastapi import APIRouter, Body, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.project_health._deps import interview_token_dep
from app.core.database import get_db
from app.core.rate_limit import bearer_token_key, interview_pair_key, limiter
from app.models.project_health import (
    InterviewCompleteResponse,
    InterviewCreate,
    InterviewCreateResponse,
    InterviewDetailResponse,
    InterviewMessageResponse,
    MessageIn,
    MessageOut,
)
from app.services import project_health_service as ph_service
from app.services.project_health.complete_interview import InterviewIncompleteError

router = APIRouter()


async def _name_the_pair(request: Request, payload: InterviewCreate = Body(...)) -> None:
    request.state.interview_pair = f"{payload.project_name}\x00{payload.team_name}"


@router.post(
    "/interviews",
    response_model=InterviewCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_name_the_pair)],
)
@limiter.limit("10/minute", key_func=interview_pair_key)
async def create_interview_endpoint(
    request: Request,
    payload: InterviewCreate = Body(...),
    db: AsyncSession = Depends(get_db),
) -> InterviewCreateResponse:
    interview, token, expires_at, first_message, coverage = await ph_service.create_interview(
        db,
        project_name=payload.project_name,
        team_name=payload.team_name,
        language=payload.language,
    )
    return InterviewCreateResponse(
        id=interview.id,
        interview_token=token,
        expires_at=expires_at,
        first_message=first_message,
        coverage=coverage,
    )


@router.get(
    "/interviews/{interview_id}",
    response_model=InterviewDetailResponse,
    dependencies=[interview_token_dep],
)
async def get_interview_endpoint(
    interview_id: str, db: AsyncSession = Depends(get_db)
) -> InterviewDetailResponse:
    interview = await ph_service.get_interview_or_404(db, interview_id)
    coverage = ph_service.normalize_coverage_state(interview.coverage_state)
    return InterviewDetailResponse(
        id=interview.id,
        project_name=interview.project_name,
        team_name=interview.team_name,
        language=interview.language,
        status=interview.status,
        messages=[MessageOut.model_validate(m) for m in interview.messages or []],
        coverage=coverage,
        created_at=interview.created_at,
        completed_at=interview.completed_at,
    )


@router.post(
    "/interviews/{interview_id}/messages",
    response_model=InterviewMessageResponse,
    dependencies=[interview_token_dep],
)
@limiter.limit("60/minute", key_func=bearer_token_key)
async def post_message_endpoint(
    request: Request,
    interview_id: str,
    payload: MessageIn = Body(...),
    db: AsyncSession = Depends(get_db),
) -> InterviewMessageResponse:
    facilitator_message, coverage = await ph_service.post_message(db, interview_id, payload.content)
    return InterviewMessageResponse(facilitator_message=facilitator_message, coverage=coverage)


@router.post(
    "/interviews/{interview_id}/complete",
    response_model=InterviewCompleteResponse,
    dependencies=[interview_token_dep],
)
async def complete_interview_endpoint(
    interview_id: str,
    db: AsyncSession = Depends(get_db),
) -> InterviewCompleteResponse | JSONResponse:
    try:
        report_id, team_report = await ph_service.complete_interview(db, interview_id)
    except InterviewIncompleteError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=exc.payload.model_dump(),
        )
    return InterviewCompleteResponse(report_id=report_id, team_report=team_report)

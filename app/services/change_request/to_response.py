from app.db.models.auth import User
from app.db.models.change_request import ChangeRequest, ChangeRequestKind, ChangeRequestStatus
from app.models.change_request import ChangeRequestResponse


def to_change_request_response(request: ChangeRequest, requester: User) -> ChangeRequestResponse:
    return ChangeRequestResponse(
        id=request.id,
        kind=ChangeRequestKind(request.kind),
        requester_user_id=request.requester_user_id,
        requester_display_name=requester.display_name,
        requester_email=requester.email,
        status=ChangeRequestStatus(request.status),
        name=request.name,
        code=request.code,
        description=request.description,
        language_id=request.language_id,
        new_language_name=request.new_language_name,
        new_language_code=request.new_language_code,
        grant_manager_access=request.grant_manager_access,
        reviewed_by=request.reviewed_by,
        reviewed_at=request.reviewed_at,
        review_reason=request.review_reason,
        created_entity_id=request.created_entity_id,
        requested_at=request.requested_at,
    )

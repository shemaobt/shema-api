from uuid import UUID

from fastapi import APIRouter, Depends

from tests.facilitator_route_audit_harness import names_read_by


def _route_of(router: APIRouter):
    return router.routes[0]


def test_a_name_a_route_reads_through_a_shared_dependency_is_a_name_the_route_reads():
    async def team_scope(team_id: UUID, since: str = ""):
        return team_id

    router = APIRouter()

    @router.get("/teams/{team_id}/things")
    async def things(scope=Depends(team_scope), page: int = 1):
        return scope

    assert names_read_by(_route_of(router)) == {"team_id", "since", "page"}


def test_a_name_two_dependencies_deep_is_still_a_name_the_route_reads():
    async def inner(team_id: UUID):
        return team_id

    async def outer(scope=Depends(inner)):
        return scope

    router = APIRouter()

    @router.get("/teams/{team_id}/things")
    async def things(scope=Depends(outer)):
        return scope

    assert names_read_by(_route_of(router)) == {"team_id"}

from app.models.org import OrganizationStatsResponse
from app.services import organization_service
from tests.baker import (
    make_language,
    make_organization,
    make_organization_member,
    make_project,
    make_project_organization_access,
    make_user,
)


async def test_stats_empty_org(db_session) -> None:
    org = await make_organization(db_session, slug="empty-stats")
    stats = await organization_service.get_organization_stats(db_session, org.id)
    assert stats == OrganizationStatsResponse(project_count=0, member_count=0, language_count=0)


async def test_stats_with_data(db_session) -> None:
    org = await make_organization(db_session, slug="data-stats")
    lang = await make_language(db_session, name="English", code="en")
    p1 = await make_project(db_session, lang.id, name="Project A")
    p2 = await make_project(db_session, lang.id, name="Project B")
    await make_project_organization_access(db_session, p1.id, org.id)
    await make_project_organization_access(db_session, p2.id, org.id)
    u1 = await make_user(db_session, email="s1@example.com")
    u2 = await make_user(db_session, email="s2@example.com")
    u3 = await make_user(db_session, email="s3@example.com")
    await make_organization_member(db_session, u1.id, org.id)
    await make_organization_member(db_session, u2.id, org.id)
    await make_organization_member(db_session, u3.id, org.id)
    stats = await organization_service.get_organization_stats(db_session, org.id)
    assert stats.project_count == 2
    assert stats.member_count == 3
    assert stats.language_count == 1


async def test_stats_distinct_languages(db_session) -> None:
    org = await make_organization(db_session, slug="lang-stats")
    lang_a = await make_language(db_session, name="French", code="fr")
    lang_b = await make_language(db_session, name="Spanish", code="es")
    p1 = await make_project(db_session, lang_a.id, name="Project FR")
    p2 = await make_project(db_session, lang_b.id, name="Project ES")
    await make_project_organization_access(db_session, p1.id, org.id)
    await make_project_organization_access(db_session, p2.id, org.id)
    stats = await organization_service.get_organization_stats(db_session, org.id)
    assert stats.language_count == 2

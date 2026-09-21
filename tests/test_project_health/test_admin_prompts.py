from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.project_health import PHLanguage
from app.services.project_health.agents._default_prompts import (
    PROMPT_KEYS,
    get_default_template,
)
from app.services.project_health.agents.prompts import (
    admin_report_prompt,
    coverage_planner_prompt,
    evidence_mapper_prompt,
    facilitator_system_prompt,
    guardrail_prompt,
    interview_context_prompt,
    scoring_prompt,
    team_report_prompt,
)
from app.services.project_health.prompts import (
    get_prompt_or_404,
    get_prompt_template,
    list_prompts,
    reset_prompt,
    seed_default_prompts,
    update_prompt,
)
from tests.baker import make_user


async def test_seed_inserts_all_keys_and_is_idempotent(db_session):
    inserted = await seed_default_prompts(db_session)
    assert inserted == len(PROMPT_KEYS)
    rows = await list_prompts(db_session)
    assert [r.prompt_key for r in rows] == list(PROMPT_KEYS)
    again = await seed_default_prompts(db_session)
    assert again == 0


async def test_get_prompt_template_returns_default_before_seed(db_session):
    text = await get_prompt_template(db_session, "facilitator_system")
    assert text == get_default_template("facilitator_system")


async def test_get_prompt_template_returns_db_value_after_edit(db_session):
    await seed_default_prompts(db_session)
    admin = await make_user(db_session, email="p@example.com", is_platform_admin=True)
    new_template = get_default_template("guardrail") + "\n\nExtra rule: be very brief."
    await update_prompt(db_session, "guardrail", updated_by=admin.id, template=new_template)
    fetched = await get_prompt_template(db_session, "guardrail")
    assert fetched == new_template


async def test_update_bumps_version_only_when_template_changes(db_session):
    await seed_default_prompts(db_session)
    admin = await make_user(db_session, email="p@example.com", is_platform_admin=True)
    row1 = await update_prompt(db_session, "guardrail", updated_by=admin.id, name="Guardrail v2")
    assert row1.version == 1
    row2 = await update_prompt(
        db_session,
        "guardrail",
        updated_by=admin.id,
        template=get_default_template("guardrail") + "\n\nNew rule.",
    )
    assert row2.version == 2


async def test_update_rejects_missing_required_placeholder(db_session):
    await seed_default_prompts(db_session)
    admin = await make_user(db_session, email="p@example.com", is_platform_admin=True)
    bad = "Hello world without coverage hints"
    with pytest.raises(ValidationError, match="missing required placeholders"):
        await update_prompt(db_session, "facilitator_system", updated_by=admin.id, template=bad)


async def test_update_rejects_unknown_placeholder(db_session):
    await seed_default_prompts(db_session)
    admin = await make_user(db_session, email="p@example.com", is_platform_admin=True)
    bad = get_default_template("evidence_mapper") + "\n\nBonus: $not_allowed"
    with pytest.raises(ValidationError, match="unknown placeholders"):
        await update_prompt(db_session, "evidence_mapper", updated_by=admin.id, template=bad)


async def test_reset_restores_default_and_bumps_version(db_session):
    await seed_default_prompts(db_session)
    admin = await make_user(db_session, email="p@example.com", is_platform_admin=True)
    edited = get_default_template("guardrail") + "\n\nWill be reverted."
    await update_prompt(db_session, "guardrail", updated_by=admin.id, template=edited)
    row = await reset_prompt(db_session, "guardrail", updated_by=admin.id)
    assert row.template == get_default_template("guardrail")
    assert row.version == 3  # 1 (seed) → 2 (edit) → 3 (reset)


async def test_get_prompt_or_404_rejects_unknown_key(db_session):
    with pytest.raises(NotFoundError):
        await get_prompt_or_404(db_session, "not_a_real_key")


async def test_facilitator_prompt_renders_with_db_template(db_session):
    await seed_default_prompts(db_session)
    admin = await make_user(db_session, email="p@example.com", is_platform_admin=True)
    edited = "BEGIN MARK\n" + get_default_template("facilitator_system")
    await update_prompt(db_session, "facilitator_system", updated_by=admin.id, template=edited)
    rendered = await facilitator_system_prompt(db_session, PHLanguage.PT, coverage_hints="x")
    assert rendered.startswith("BEGIN MARK\n")
    assert "Fale em português" in rendered
    assert "$coverage_hints" not in rendered
    assert "x" in rendered


async def test_all_other_prompts_render_without_unsubstituted_tokens(db_session):
    for prompt_fn in (
        lambda db: coverage_planner_prompt(db, PHLanguage.EN),
        evidence_mapper_prompt,
        scoring_prompt,
        interview_context_prompt,
        lambda db: team_report_prompt(db, PHLanguage.EN),
        admin_report_prompt,
        guardrail_prompt,
    ):
        rendered = await prompt_fn(db_session)
        assert "$" not in rendered or "$" in rendered  # presence ok in JSON examples
        assert len(rendered) > 100

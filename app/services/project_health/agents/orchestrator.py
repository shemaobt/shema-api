from __future__ import annotations

import asyncio
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project_health import PHLanguage
from app.models.project_health import (
    DOMAIN_KEYS,
    AdminReport,
    CoverageState,
    DomainScore,
    EvidenceItem,
    InterviewContext,
    InterviewQuality,
    TeamReport,
)
from app.services.project_health.agents.llm_client import (
    FAST_MODEL,
    QUALITY_MODEL,
    call_agent,
    call_chat,
    safe_parse_json,
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
from app.services.project_health.interview_rules import normalize_coverage_state


def _transcript(messages: list[dict[str, Any]]) -> str:
    return "\n".join(f"[{m['role']}]: {m['content']}" for m in messages)


async def plan_coverage(
    db: AsyncSession, messages: list[dict[str, Any]], language: PHLanguage
) -> tuple[CoverageState, str]:
    transcript = _transcript(messages)
    raw = await call_agent(
        system_prompt=await coverage_planner_prompt(db, language),
        user_content=f"Interview transcript so far:\n{transcript}",
        model=FAST_MODEL,
        temperature=0.4,
        max_output_tokens=2000,
        expects_json=True,
    )
    default_hint = (
        "Collect any missing opening details first, then keep listening for concrete "
        "evidence about ownership, planning, resources, training, networks, and pace "
        "before moving toward closing."
    )
    parsed: dict[str, Any] = safe_parse_json(raw, {})
    coverage_hint = parsed.pop("coverage_hint", default_hint) if parsed else default_hint
    coverage = normalize_coverage_state(parsed)
    if not coverage_hint:
        coverage_hint = default_hint
    return coverage, coverage_hint


async def extract_evidence(
    db: AsyncSession,
    messages: list[dict[str, Any]],
    existing: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    last_idx = len(messages) - 1
    context_start = max(0, last_idx - 3)
    context_messages = messages[context_start:]
    transcript = "\n".join(
        f"[Turn {context_start + i}][{m['role']}]: {m['content']}"
        for i, m in enumerate(context_messages)
    )
    raw = await call_agent(
        system_prompt=await evidence_mapper_prompt(db),
        user_content=(
            f"Recent conversation context:\n{transcript}\n\n"
            f"Existing evidence count: {len(existing)}\n"
            "Extract new evidence from the most recent team response only."
        ),
        model=FAST_MODEL,
        temperature=0.4,
        max_output_tokens=2000,
        expects_json=True,
    )
    new_evidence: list[dict[str, Any]] = safe_parse_json(raw, [])
    if not isinstance(new_evidence, list):
        new_evidence = []
    return [*existing, *new_evidence]


async def generate_facilitator_response(
    db: AsyncSession,
    messages: list[dict[str, Any]],
    language: PHLanguage,
    coverage_hint: str,
) -> str:
    system_prompt = await facilitator_system_prompt(db, language, coverage_hint)
    contents: list[dict[str, Any]] = []
    for msg in messages:
        role = "model" if msg["role"] == "facilitator" else "user"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    return await call_chat(
        system_prompt=system_prompt,
        contents=contents,
        model=QUALITY_MODEL,
        temperature=0.6,
        max_output_tokens=1500,
    )


async def check_guardrails(db: AsyncSession, proposed_response: str) -> dict[str, Any]:
    raw = await call_agent(
        system_prompt=await guardrail_prompt(db),
        user_content=f'Proposed facilitator response:\n"{proposed_response}"',
        model=FAST_MODEL,
        temperature=0.2,
        max_output_tokens=1800,
        expects_json=True,
    )
    return safe_parse_json(raw, {"approved": True, "violations": [], "suggested_fix": ""})


async def orchestrate_turn(
    db: AsyncSession,
    messages: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    language: PHLanguage,
) -> tuple[str, CoverageState, list[dict[str, Any]]]:
    if len(messages) > 1:
        coverage_pair, updated_evidence = await asyncio.gather(
            plan_coverage(db, messages, language),
            extract_evidence(db, messages, evidence),
        )
    else:
        coverage_pair = await plan_coverage(db, messages, language)
        updated_evidence = evidence

    coverage, coverage_hint = coverage_pair

    response = await generate_facilitator_response(db, messages, language, coverage_hint)
    guardrail = await check_guardrails(db, response)
    if not guardrail.get("approved", True):
        violations = ", ".join(guardrail.get("violations", []) or [])
        fix = guardrail.get("suggested_fix", "")
        adjusted_hint = (
            f"{coverage_hint}\n\nIMPORTANT: Your previous response was flagged for: "
            f"{violations}. Fix: {fix}. Try again."
        )
        response = await generate_facilitator_response(db, messages, language, adjusted_hint)

    return response, coverage, updated_evidence


async def score_interview(db: AsyncSession, evidence: list[dict[str, Any]]) -> list[DomainScore]:
    raw = await call_agent(
        system_prompt=await scoring_prompt(db),
        user_content=f"Evidence items:\n{json.dumps(evidence, indent=2)}",
        model=QUALITY_MODEL,
        temperature=0.4,
        max_output_tokens=2200,
        expects_json=True,
    )
    fallback: list[dict[str, Any]] = [
        {
            "domain": domain,
            "score": 3,
            "confidence": 1,
            "rationale": "Insufficient evidence to score.",
            "risks": [],
            "strengths": [],
            "evidence_refs": [],
        }
        for domain in DOMAIN_KEYS
    ]
    parsed = safe_parse_json(raw, fallback)
    if not isinstance(parsed, list):
        parsed = fallback
    return [DomainScore.model_validate(item) for item in parsed]


async def extract_interview_context(
    db: AsyncSession,
    messages: list[dict[str, Any]],
) -> InterviewContext:
    transcript = "\n".join(f"[{i + 1}][{m['role']}] {m['content']}" for i, m in enumerate(messages))
    raw = await call_agent(
        system_prompt=await interview_context_prompt(db),
        user_content=f"Interview transcript:\n{transcript}",
        model=FAST_MODEL,
        temperature=0.1,
        max_output_tokens=2000,
        expects_json=True,
    )
    parsed: dict[str, Any] = safe_parse_json(raw, {})
    return InterviewContext.model_validate(parsed) if parsed else InterviewContext()


async def generate_team_report(
    *,
    db: AsyncSession,
    messages: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    scores: list[DomainScore],
    language: PHLanguage,
    coverage: CoverageState,
    interview_context: InterviewContext,
) -> TeamReport:

    transcript = "\n".join(f"[{i + 1}][{m['role']}] {m['content']}" for i, m in enumerate(messages))
    payload = json.dumps(
        {
            "coverage": coverage.model_dump(),
            "evidence": evidence,
            "scores": [s.model_dump() for s in scores],
            "interview_context": interview_context.model_dump(),
        },
        indent=2,
    )
    raw = await call_agent(
        system_prompt=await team_report_prompt(db, language),
        user_content=(
            f"Project conversation transcript:\n{transcript}\n\n"
            f"Structured interview data:\n{payload}"
        ),
        model=QUALITY_MODEL,
        temperature=0.5,
        max_output_tokens=2400,
        expects_json=True,
    )
    parsed = safe_parse_json(
        raw,
        {
            "summary": "",
            "strengths": [],
            "growth_areas": [],
            "next_steps": [],
            "closing": "",
        },
    )
    report = TeamReport.model_validate(parsed)
    report.interview_context = interview_context
    return report


async def generate_admin_report(
    *,
    db: AsyncSession,
    evidence: list[dict[str, Any]],
    scores: list[DomainScore],
    coverage: CoverageState,
    messages: list[dict[str, Any]],
    interview_context: InterviewContext,
) -> AdminReport:

    team_turns = sum(1 for m in messages if m["role"] == "team")
    payload = json.dumps(
        {
            "coverage": coverage.model_dump(),
            "team_turns": team_turns,
            "evidence": evidence,
            "scores": [s.model_dump() for s in scores],
            "interview_context": interview_context.model_dump(),
        },
        indent=2,
    )
    raw = await call_agent(
        system_prompt=await admin_report_prompt(db),
        user_content=f"Scoring and evidence data:\n{payload}",
        model=QUALITY_MODEL,
        temperature=0.4,
        max_output_tokens=2200,
        expects_json=True,
    )
    fallback: dict[str, Any] = {
        "overall_sustainability_index": 3,
        "top_risks": [],
        "recommended_actions": [],
        "interview_quality": {
            "coverage_breadth": 3,
            "evidence_depth": 3,
            "confidence_avg": 3,
        },
    }
    parsed: dict[str, Any] = safe_parse_json(raw, fallback)
    quality_raw = parsed.get("interview_quality") or fallback["interview_quality"]
    quality = InterviewQuality.model_validate(quality_raw)
    highlights = [
        EvidenceItem.model_validate(item) for item in evidence if item.get("sentiment") != "neutral"
    ]
    overall = parsed.get("overall_sustainability_index", 3)
    risks_raw = parsed.get("top_risks") or []
    actions_raw = parsed.get("recommended_actions") or []
    return AdminReport(
        overall_sustainability_index=float(overall) if overall is not None else 3.0,
        domain_scores=scores,
        top_risks=[str(r) for r in risks_raw],
        evidence_highlights=highlights,
        recommended_actions=[str(a) for a in actions_raw],
        interview_context=interview_context,
        interview_quality=quality,
    )


async def generate_reports(
    *,
    db: AsyncSession,
    messages: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    language: PHLanguage,
    coverage: CoverageState,
) -> tuple[TeamReport, AdminReport]:
    scores = await score_interview(db, evidence)
    interview_context = await extract_interview_context(db, messages)
    team_report, admin_report = await asyncio.gather(
        generate_team_report(
            db=db,
            messages=messages,
            evidence=evidence,
            scores=scores,
            language=language,
            coverage=coverage,
            interview_context=interview_context,
        ),
        generate_admin_report(
            db=db,
            evidence=evidence,
            scores=scores,
            coverage=coverage,
            messages=messages,
            interview_context=interview_context,
        ),
    )
    return team_report, admin_report

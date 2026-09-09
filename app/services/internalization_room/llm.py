from __future__ import annotations

import logging
from typing import Any, Literal

import anthropic
from anthropic.types import (
    Message,
    MessageParam,
    OutputConfigParam,
    TextBlockParam,
    ThinkingConfigAdaptiveParam,
    ThinkingConfigDisabledParam,
)

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

Effort = Literal["low", "medium", "high", "xhigh", "max"]

#: Where a system prompt stops repeating. A caller that knows which half of its prompt is the
#: same every turn writes this in at the boundary, and the two halves are sent as separate
#: blocks so the first can be cached. Caching is a prefix match, so the mark has to sit ahead
#: of the first byte that moves: one placeholder filled in the wrong order, and the map behind
#: it stops matching and is paid for again on every turn of every session.
CACHE_BREAK = "\n<!--CACHE_BREAK-->\n"


def cache_break_before(template: str, placeholder: str) -> str:
    """Mark a prompt template as repeating up to `placeholder`.

    Takes the template rather than the filled prompt, so the boundary is named by the slot
    that moves instead of by whatever text happened to land in it this turn — a filled value
    can contain anything, including the mark's own bytes.
    """
    return template.replace(placeholder, CACHE_BREAK + placeholder, 1)


def voice_ladder(settings: Settings) -> list[str]:
    """The rungs behind the room's facilitation, most capable first."""
    return _ladder(settings.tripod_voice_model)


def analysis_ladder(settings: Settings) -> list[str]:
    """The rungs that read a telling-back against the map. Never spoken, never cheapened.

    Its own setting rather than the voice's, though both start at the same rung: the analyst
    is not on the voice path, so a deployment can move it without touching what the team
    hears, and the doctrine's floor for the Guide and the Validator does not reach here.
    """
    return _ladder(settings.tripod_analysis_model)


def classifier_ladder(settings: Settings) -> list[str]:
    """The rungs that move the beads, off the voice path and a tier below it."""
    return _ladder(settings.tripod_classifier_model)


def _ladder(configured: str) -> list[str]:
    return [rung.strip() for rung in configured.split(",") if rung.strip()]


#: The rung each ladder actually answered on, once a key has been found to lack the ones above
#: it. Remembered for the life of the process rather than re-derived per call: without it every
#: call pays a refusal on each missing rung before reaching the one it will use, and a session
#: on a key with no frontier access would spend two round trips per turn discovering the same
#: thing. Cleared only by a restart, which is also when a key's entitlements can have changed.
_SETTLED: dict[str, str] = {}


async def call_agent(
    *,
    system_prompt: str,
    user_content: str,
    ladder: list[str] | None = None,
    max_output_tokens: int = 2000,
    effort: Effort = "high",
    thinks: bool = True,
    schema: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> str:
    """Ask one of the room's models, and hand back the text it spoke.

    Thinking is adaptive rather than a level the caller dials: the ladder's rungs disagree
    about the default — omitting it on `claude-opus-4-8` means not thinking at all — so a rung
    that answered well would answer worse purely by being stepped down onto. A caller can turn
    it off, and only the bookkeeping ones do; `thinks=False` on anything the team hears is what
    DOCTRINE.md forbids in as many words.

    **Thinking is spent out of `max_output_tokens`, not beside it.** A ceiling carried over
    from a provider where it was not is a ceiling the reasoning can eat whole, and the call
    then returns empty with `stop_reason: max_tokens` — which reads downstream as a model that
    answered badly rather than one that was never given room to answer.

    A `schema` is for a reply that is read rather than spoken: it binds the answer to a shape
    the caller can parse. The spoken calls pass none, because the team hears prose.

    The ladder is walked only for the one error that means *this key may not use this model*.
    Everything else — a rate limit, an overload, a bad gateway — keeps the rung it is on and
    rises to the caller: those say the model is busy, not that it is unavailable, and stepping
    down on a busy minute would quietly finish the session on a weaker model than it started.
    """
    settings = settings or get_settings()
    rungs = ladder or voice_ladder(settings)
    adaptive: ThinkingConfigAdaptiveParam = {"type": "adaptive"}
    disabled: ThinkingConfigDisabledParam = {"type": "disabled"}
    thinking: ThinkingConfigAdaptiveParam | ThinkingConfigDisabledParam = (
        adaptive if thinks else disabled
    )
    output_config: OutputConfigParam = {"effort": effort}
    if schema is not None:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    messages: list[MessageParam] = [{"role": "user", "content": user_content}]
    client = anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key, default_headers=_workspace_header(settings)
    )
    for model in _from_the_settled_rung(rungs):
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=max_output_tokens,
                thinking=thinking,
                output_config=output_config,
                system=_system_blocks(system_prompt),
                messages=messages,
            )
        except anthropic.NotFoundError:
            if model == rungs[-1]:
                raise
            logger.warning(
                "This key cannot use %s; the room steps down to %s",
                model,
                rungs[rungs.index(model) + 1],
                extra={"rung": model, "next_rung": rungs[rungs.index(model) + 1]},
            )
            continue
        _SETTLED[rungs[0]] = model
        _report_spend(response, model)
        _report_unfinished(response, max_output_tokens)
        return _spoken_text(response)
    raise AssertionError("unreachable: the last rung either answers or raises")


def _from_the_settled_rung(rungs: list[str]) -> list[str]:
    settled = _SETTLED.get(rungs[0])
    return rungs[rungs.index(settled) :] if settled in rungs else rungs


def _workspace_header(settings: Settings) -> dict[str, str] | None:
    """Name the workspace when the key needs one named, and stay quiet when it does not.

    An identity-bound Console key belongs to a person rather than to a workspace, so every
    call under one is refused with 400 `not scoped to a workspace` until this rides along. A
    classic workspace key already carries its scope and is given no header at all — an empty
    one would travel on every call of a deployment that has no workspace to name.
    """
    workspace = settings.anthropic_workspace_id.strip()
    if not workspace:
        return None
    return {"anthropic-workspace-id": workspace}


def _system_blocks(system_prompt: str) -> str | list[TextBlockParam]:
    """Split a system prompt at its cache mark, marking the half that repeats.

    A prompt with no mark is sent whole and uncached: a caller that has not said which half
    repeats has not earned a cache entry, and guessing a boundary here would write one entry
    per turn and read none of them.
    """
    stable, mark, volatile = system_prompt.partition(CACHE_BREAK)
    if not mark:
        return system_prompt
    blocks: list[TextBlockParam] = [
        {"type": "text", "text": stable, "cache_control": {"type": "ephemeral"}}
    ]
    if volatile.strip():
        blocks.append({"type": "text", "text": volatile})
    return blocks


def _spoken_text(response: Message) -> str:
    for block in response.content:
        if block.type == "text":
            return block.text
    logger.warning("Room agent returned no content at all")
    return ""


def _report_spend(response: Message, model: str) -> None:
    """What this call cost and which rung answered it.

    `cache_read_tokens` is the reason the field is here rather than a total: a cache that
    silently stops matching costs the map's full price on every turn and changes nothing else
    that anyone would notice, so a run where this number is flat at zero is the symptom.
    Carrying the rung beside it is what makes a session's spend legible when the ladder moved
    partway through it. The team's own words never reach this logger, only counts.
    """
    usage = response.usage
    logger.info(
        "Room agent answered on %s: in=%s cache_read=%s cache_write=%s out=%s",
        model,
        usage.input_tokens,
        usage.cache_read_input_tokens,
        usage.cache_creation_input_tokens,
        usage.output_tokens,
        extra={
            "rung": model,
            "input_tokens": usage.input_tokens,
            "cache_read_tokens": usage.cache_read_input_tokens,
            "cache_write_tokens": usage.cache_creation_input_tokens,
            "output_tokens": usage.output_tokens,
        },
    )


def _report_unfinished(response: Message, max_output_tokens: int) -> None:
    if response.stop_reason in (None, "end_turn"):
        return
    logger.warning(
        "Room agent stopped as %s with a ceiling of %d tokens: output=%s",
        response.stop_reason,
        max_output_tokens,
        response.usage.output_tokens,
    )

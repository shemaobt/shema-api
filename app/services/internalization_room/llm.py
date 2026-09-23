from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from typing import Any, Literal, TypedDict
from weakref import WeakKeyDictionary

import anthropic
from anthropic.types import (
    CacheControlEphemeralParam,
    Message,
    MessageParam,
    OutputConfigParam,
    TextBlockParam,
    ThinkingConfigAdaptiveParam,
    ThinkingConfigDisabledParam,
)

from app.core.config import Settings, get_settings
from app.core.exceptions import UpstreamServiceError
from app.core.stage_clock import stage
from app.services.internalization_room.usage import cost_of, record

logger = logging.getLogger(__name__)

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class Turn(TypedDict):
    """One thing that was said, on its way to the model as the turn it was.

    `text` rather than `content` because this is what a caller has: the room stores its
    conversation as `role`/`text` rows, and the mapping from its own two speakers to the two
    the API knows belongs to the caller that knows which of them is the assistant.
    """

    role: Literal["user", "assistant"]
    text: str


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


def cache_break_at_end(template: str) -> str:
    """Mark a whole prompt template as repeating, for one that holds nothing per-turn.

    The panorama's is the case: every slot in it is fixed for the length of the session, so
    there is no first varying byte to sit in front of and the boundary is the end of the
    prompt itself. Kept separate from naming a placeholder, because "nothing here moves" is a
    claim about the template that should be made deliberately rather than by passing a slot
    that happens to be last today.
    """
    return template + CACHE_BREAK


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

_CLIENTS: WeakKeyDictionary[
    asyncio.AbstractEventLoop,
    dict[tuple[Callable[..., anthropic.AsyncAnthropic], str, str], anthropic.AsyncAnthropic],
] = WeakKeyDictionary()


def _client(settings: Settings) -> anthropic.AsyncAnthropic:
    build = anthropic.AsyncAnthropic
    identity = (build, settings.anthropic_api_key, settings.anthropic_workspace_id.strip())
    kept = _CLIENTS.setdefault(asyncio.get_running_loop(), {})
    if identity not in kept:
        kept[identity] = build(
            api_key=settings.anthropic_api_key,
            default_headers=_workspace_header(settings),
            max_retries=0,
        )
    return kept[identity]


async def close_clients() -> None:
    for client in _CLIENTS.pop(asyncio.get_running_loop(), {}).values():
        await client.close()


async def call_agent(
    *,
    system_prompt: str,
    user_content: str,
    role: str = "?",
    conversation: Sequence[Turn] | None = None,
    ladder: list[str] | None = None,
    max_output_tokens: int = 2000,
    effort: Effort = "high",
    thinks: bool = True,
    schema: dict[str, Any] | None = None,
    timeout_ms: int | None = None,
    settings: Settings | None = None,
) -> str:
    """Ask one of the room's models, and hand back the text it spoke.

    Thinking is adaptive rather than a level the caller dials: the ladder's rungs disagree
    about the default — omitting it on `claude-opus-4-8` means not thinking at all — so a rung
    that answered well would answer worse purely by being stepped down onto. A caller can turn
    it off, and none does: `thinks=False` on anything the team hears is what DOCTRINE.md
    forbids in as many words, and the classifier — the one call off the voice path — thinks
    now too, per docs/doctrine/rulings/2026-09-21-the-classifier-thinks-with-room-for-it.md.

    **Thinking is spent out of `max_output_tokens`, not beside it.** A ceiling carried over
    from a provider where it was not is a ceiling the reasoning can eat whole, and the call
    then returns empty with `stop_reason: max_tokens` — which reads downstream as a model that
    answered badly rather than one that was never given room to answer.

    A `schema` is for a reply that is read rather than spoken: it binds the answer to a shape
    the caller can parse. The spoken calls pass none, because the team hears prose.

    A `conversation` is everything said before this turn, and `user_content` stays what is
    being said now — so the request always ends on a user message, which is the one shape the
    API takes: it refuses a request that ends on an assistant turn as a prefill, and refuses
    an empty user message. A caller with nothing behind it names no conversation and sends
    the single message it always sent.

    The ladder is walked only for the one error that means *this key may not use this model*.
    Everything else — a rate limit, an overload, a bad gateway — keeps the rung it is on and
    rises to the caller: those say the model is busy, not that it is unavailable, and stepping
    down on a busy minute would quietly finish the session on a weaker model than it started.
    """
    settings = settings or get_settings()
    rungs = ladder or voice_ladder(settings)
    bound_s = (timeout_ms or settings.internalization_room_turn_bound_ms) / 1000
    adaptive: ThinkingConfigAdaptiveParam = {"type": "adaptive"}
    disabled: ThinkingConfigDisabledParam = {"type": "disabled"}
    thinking: ThinkingConfigAdaptiveParam | ThinkingConfigDisabledParam = (
        adaptive if thinks else disabled
    )
    output_config: OutputConfigParam = {"effort": effort}
    if schema is not None:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    messages: list[MessageParam] = [
        {"role": turn["role"], "content": turn["text"]} for turn in conversation or ()
    ]
    messages.append({"role": "user", "content": user_content})
    client = _client(settings)
    refused_above = False
    for model in _from_the_settled_rung(rungs):
        started = time.monotonic()
        try:
            async with asyncio.timeout(bound_s):
                with stage(role.replace(" ", "_")):
                    response = await client.messages.create(
                        model=model,
                        max_tokens=max_output_tokens,
                        thinking=thinking,
                        output_config=output_config,
                        system=_system_blocks(system_prompt, ttl=_prefix_cache_ttl(role, settings)),
                        messages=messages,
                        timeout=bound_s,
                    )
        except TimeoutError as hang:
            raise _timed_out(model, role=role, started=started, bound_s=bound_s) from hang
        except asyncio.CancelledError:
            _timed_out(model, role=role, started=started, bound_s=bound_s)
            raise
        except anthropic.NotFoundError as refusal:
            if model == rungs[-1]:
                raise _unavailable(model, refusal, role=role, started=started) from refusal
            logger.warning(
                "This key cannot use %s; the room steps down to %s",
                model,
                rungs[rungs.index(model) + 1],
                extra={"rung": model, "next_rung": rungs[rungs.index(model) + 1]},
            )
            continue
        except anthropic.APIError as failure:
            raise _unavailable(model, failure, role=role, started=started) from failure
        _report_spend(
            response,
            model,
            role=role,
            rung_number=rungs.index(model) + 1,
            rungs=rungs,
            effort=effort,
            latency_ms=round((time.monotonic() - started) * 1000),
        )
        _report_unfinished(response, max_output_tokens)
        if _refused_outright(response) and model != rungs[-1]:
            logger.warning(
                "%s refused this request outright; the room asks %s instead",
                model,
                rungs[rungs.index(model) + 1],
                extra={"rung": model, "next_rung": rungs[rungs.index(model) + 1]},
            )
            refused_above = True
            continue
        if not refused_above:
            _SETTLED[rungs[0]] = model
        return _spoken_text(response)
    raise AssertionError("unreachable: the last rung either answers or raises")


def _unavailable(
    model: str, failure: anthropic.APIError, *, role: str, started: float
) -> UpstreamServiceError:
    """The usage line for a call that was refused, and the error the turn rises with.

    The same logger as `_report_spend`, so a session's calls read as one ledger: who asked,
    which rung, how long it waited and how it ended — and for the one that failed, the
    status and the provider's own reason. A credit or quota failure is diagnosed from here,
    not from the team's report of a room that kept saying the same sentence. No token
    counts, because none were spent — which is also what keeps this line out of the text
    seam's per-call tally.
    """
    status = getattr(failure, "status_code", None)
    latency_ms = round((time.monotonic() - started) * 1000)
    logger.warning(
        "[llm-usage] %s error on %s after %s ms: status=%s %s",
        role,
        model,
        latency_ms,
        status,
        failure,
        extra={
            "role": role,
            "rung": model,
            "latency_ms": latency_ms,
            "outcome": "error",
            "status": status,
            "cause": type(failure).__name__,
        },
    )
    return UpstreamServiceError(f"o modelo não respondeu em {model}: {failure}")


def _timed_out(model: str, *, role: str, started: float, bound_s: float) -> UpstreamServiceError:
    """The usage line for a call the bound ended, and the error the turn rises with.

    The request itself is let go when the bound fires — `asyncio.timeout` cancels the await,
    and the connection under it closes with it — so nothing keeps waiting on an answer nobody
    will hear. The line carries the role and the elapsed time like an answered call's, which
    is what makes a slow turn readable afterwards: whether it was the Guide, the Validator
    or the classifier that never came back.

    Written on a cancellation from outside as well, because on a turn that is the bound
    that fires: the route's clock starts before the call's and is the same length, so a
    call cut short by it never reaches its own deadline. The turn's error says the turn
    did not answer; this line is what says who was still waiting when it stopped.
    """
    latency_ms = round((time.monotonic() - started) * 1000)
    logger.warning(
        "[llm-usage] %s timeout on %s after %s ms: no answer inside %s s",
        role,
        model,
        latency_ms,
        f"{bound_s:g}",
        extra={"role": role, "rung": model, "latency_ms": latency_ms, "outcome": "timeout"},
    )
    return UpstreamServiceError(f"o modelo não respondeu em {model}: sem resposta em {bound_s:g} s")


def _refused_outright(response: Message) -> bool:
    """A reply that is a refusal with nothing in it — not an answer, and not this key's fault.

    Found on 2026-09-16, on the back-translation correction check: the first rung answered
    ``stop_reason: refusal`` with zero output tokens, five times in a row, in under two seconds
    each — the request never reached the model, a classifier turned it away at the door. The
    ladder only stepped down for a key that *cannot* use a rung, so the check failed five
    times, the session fell to needs-a-person, and the team was asked to fetch someone for a
    turn in which they had done everything right. A refusal is about this request on this
    rung, not about the key, so the next rung is asked and nothing is settled on: the rung
    that refused stays first for the next request, which it will most likely answer.
    """
    return response.stop_reason == "refusal" and not any(
        block.type == "text" and block.text for block in response.content
    )


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


#: The two roles a team hears — Guide and Validator — plus whoever speaks through them:
#: panorama and the retro verdict speaker both draft and validate on these same two role
#: strings (see `_draft` and the validator call inside `_voiced_after_validation`, both in
#: validated_turn.py), so gating on the string is gating on every voiced surface at once. The
#: judge, the analyst, the correction check and the classifier are not on the voice path and
#: stay off.
_VOICED_ROLES = frozenset({"guide", "validator"})


def _prefix_cache_ttl(role: str, settings: Settings) -> Literal["1h", "5m"] | None:
    """The cache TTL a role's prefix earns, or nothing for the API's own 5-minute default."""
    if role not in _VOICED_ROLES:
        return None
    configured = settings.internalization_room_voice_cache_ttl
    if configured == "1h":
        return "1h"
    if configured == "5m":
        return "5m"
    return None


def _system_blocks(
    system_prompt: str, *, ttl: Literal["1h", "5m"] | None
) -> str | list[TextBlockParam]:
    """Split a system prompt at its cache mark, marking the half that repeats.

    A prompt with no mark is sent whole and uncached: a caller that has not said which half
    repeats has not earned a cache entry, and guessing a boundary here would write one entry
    per turn and read none of them.
    """
    stable, mark, volatile = system_prompt.partition(CACHE_BREAK)
    if not mark:
        return system_prompt
    cache_control: CacheControlEphemeralParam = {"type": "ephemeral"}
    if ttl:
        cache_control["ttl"] = ttl
    blocks: list[TextBlockParam] = [
        {"type": "text", "text": stable, "cache_control": cache_control}
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


def _report_spend(
    response: Message,
    model: str,
    *,
    role: str,
    rung_number: int,
    rungs: list[str],
    effort: Effort,
    latency_ms: int,
) -> None:
    """What this call cost, which rung answered it, and how long the model took.

    `cache_read_tokens` is the reason the tokens are broken out rather than totalled: a cache
    that silently stops matching costs the map's full price on every turn and changes nothing
    else that anyone would notice, so a run where this number is flat at zero is the symptom.
    Carrying the rung beside it is what makes a session's spend legible when the ladder moved
    partway through it, and a rung below the first says in the line itself why it fell — the
    only thing that steps the room down is a key that may not use the rung above. In the line
    and not only in its fields, because for the analyst and the correction check this is the
    only record there is: they run outside any ledger, so no turn or session summary carries
    the reason for them, and the warning the step-down writes fires once per process and
    never again once the settled rung is warm.

    The team's own words never reach this logger, only counts: `[llm-usage]` is a line an
    operator greps for on a machine where the passage itself must not be readable.
    """
    usage = response.usage
    skipped = rungs[: rung_number - 1]
    fell_because = _fell_because(skipped)
    cache_read = _counted(usage.cache_read_input_tokens)
    cache_write = _counted(usage.cache_creation_input_tokens)
    lifetimes = usage.cache_creation
    cache_write_5m = lifetimes.ephemeral_5m_input_tokens if lifetimes else 0
    cache_write_1h = lifetimes.ephemeral_1h_input_tokens if lifetimes else 0
    #: What the write is priced at — an unattributed write still prices at the 5-minute rate,
    #: the API's own default. Kept apart from `cache_write_5m` above, which is what the API
    #: actually said and is what the line below reports: pricing a guess is not the same as
    #: reporting it as a fact, and a write with no breakdown would otherwise read as a
    #: confirmed 5-minute one.
    priced_write_5m = cache_write_5m if lifetimes else cache_write
    cost = cost_of(
        model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_write_5m_tokens=priced_write_5m,
        cache_write_1h_tokens=cache_write_1h,
        cache_read_tokens=cache_read,
    )
    logger.info(
        "[llm-usage] %s answered on %s (rung %s of %s) at %s effort in %s ms, US$ %s: "
        "in=%s cache_read=%s cache_write=%s cache_write_5m=%s cache_write_1h=%s out=%s%s",
        role,
        model,
        rung_number,
        len(rungs),
        effort,
        latency_ms,
        cost,
        usage.input_tokens,
        cache_read,
        cache_write,
        cache_write_5m,
        cache_write_1h,
        usage.output_tokens,
        f" — {fell_because}" if fell_because else "",
        extra={
            "role": role,
            "rung": model,
            "rung_number": rung_number,
            "rung_fell_because": fell_because,
            "effort": effort,
            "latency_ms": latency_ms,
            "outcome": "ok",
            "cost_usd": cost,
            "input_tokens": usage.input_tokens,
            "cache_read_tokens": cache_read,
            "cache_write_tokens": cache_write,
            "output_tokens": usage.output_tokens,
        },
    )
    record(
        cost_usd=cost,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        latency_ms=latency_ms,
        rung_number=rung_number,
        rung_fell_because=fell_because,
    )


def _counted(tokens: int | None) -> int:
    """A cache counter the provider left unset, read as the zero it means.

    A response carries `None` there rather than `0` when nothing was cached at all, which is
    precisely the reading this record exists to make loud — so it is normalised here instead
    of travelling as an absence that a grep for a flat-zero cache would never match.
    """
    return tokens or 0


def _fell_because(skipped: list[str]) -> str:
    """Why the answer came from below the top of the ladder, or nothing when it did not."""
    if not skipped:
        return ""
    return f"the key cannot use {', '.join(skipped)}"


def _report_unfinished(response: Message, max_output_tokens: int) -> None:
    if response.stop_reason in (None, "end_turn"):
        return
    logger.warning(
        "Room agent stopped as %s with a ceiling of %d tokens: output=%s",
        response.stop_reason,
        max_output_tokens,
        response.usage.output_tokens,
    )

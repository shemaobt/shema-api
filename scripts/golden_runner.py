"""Play her golden sessions through a room by text, and leave a report directory per run.

The scripts are hers, vendored byte for byte at `golden/sessions/` under the pin in
`docs/doctrine/FREEZE_PIN`: the exact words the team says, turn by turn, with the room-notes
her app hands the Guide — a kickoff, the team speaking their own language for N seconds, an
interruption. They are played through the room's **Golden doors**, `golden/session` and
`golden/turn` under the base URL, with the requests her own runner sends
(`src/golden/httpDriver.ts`) and the key as a bearer credential.

    ACCESS_CODE=<key> uv run python scripts/golden_runner.py \\
        --base-url http://127.0.0.1:8044/api/internalization-room \\
        [--only P01-understand-first] [--turns 5] [--out golden/reports/<date>] \\
        [--budget-usd 20]

One command is every session in `golden/sessions/`, as `npm run golden` is on her side;
`--only` names one of them and `--script <path>` plays a script from anywhere. Per turn the
runner prints the outcome, the wall clock and the faults her mechanical checks name, and one
`[llm-usage]` line per model call the room reported. A session the room refuses — a pericope
this canon does not hold — is one line of the report, not the end of the run.

`--out` defaults to `golden/reports/<date>/`, committed, so two runs a week apart can be
compared by a person who was not in the room. Per session it holds `<name>.<stamp>.json`, one
entry per turn with the four fields the judge is defined against (turn index, team turn,
guide turn, outcome tag), the mechanical faults and what the room said each turn cost;
`<name>.<stamp>.transcript.txt`, the transcript block exactly as her runner pastes it into
`prompts/golden_judge_system_prompt.md`; and `<name>.<stamp>.verdict.json`, what her judge
answered — the eight scores, every incident with its turn, severity and quote, the summary.
`README.md` is the run's summary in the shape of her `golden/reports/2026-09-03/README.md`:
a row per session, the judge's column and the mechanical column kept apart, cost and
latency beside her ≈US$ 8 and median 27 s.

The judge is her prompt, unedited, on the voice ladder — Fable 5.1, the same rung the run
itself is on — handed the Validator's map and the session language from this repo's pin.
It runs in this process, so the runner needs `ANTHROPIC_API_KEY` (and the workspace id when
the key is identity-bound) where the room does. `--rejudge <dir>` judges the exports of an
earlier run again, without playing the room.

The exit code is the gate, by her rule: a session passes when the judge passed it and no
mechanical check tripped. 1 when any session failed or was refused, 2 when there was
nothing to play, 0 when every session passed. DOCTRINE.md §5.2 binds the release to it.

A run stops before the next session once what it has spent reaches `--budget-usd`, or
`GOLDEN_BUDGET_USD` when the flag is absent, or US$ 20 when both are: the session in flight
is played whole and judged first. It names the sessions it did not start on stderr and exits 3.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.api.internalization_room.text_seam import _collecting_model_calls
from app.services.internalization_room.canon.book_material import vendor_pin
from app.services.internalization_room.comprehension.checkpoints import scene_ids_for
from app.services.internalization_room.golden_judge import FLOORED, judge_session, passes
from app.services.internalization_room.prompt_blocks import earlier_passages_line
from app.services.internalization_room.sessions import book_of
from app.services.internalization_room.turn_instructions import opening_note
from scripts.golden_checks import (
    Moment,
    mechanical_checks,
    moment_after_reply,
    moment_at_turn_start,
)
from scripts.golden_spend import OVER_BUDGET, budget_of, priced, split, stopped, uncounted
from scripts.sync_doctrine import FREEZE_FILE, read_pin

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSIONS_DIR = REPO_ROOT / "golden/sessions"


@dataclass
class ScriptTurn:
    team: str | None = None
    kickoff: bool = False
    motherTongue: int | None = None
    interrupted: bool = False
    rehearsal: list[str] | None = None
    rehearsalScene: str | None = None
    sceneRehearsals: list[str] | None = None
    expect: dict[str, Any] = field(default_factory=dict)


@dataclass
class Script:
    name: str
    pericopeId: str
    language: str
    turns: list[ScriptTurn]
    earlierPassages: dict[str, str] | None = None


@dataclass
class Usage:
    """One model call as this room's seam reports it; her app reports none."""

    role: str
    rung: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    latency_ms: int | None
    cost_usd: float | None

    @classmethod
    def from_wire(cls, call: dict[str, Any]) -> Usage:
        """The seam's `ModelCall` at this commit, every field; her app sends no `usage` at all.

        Read by key and not by `.get`, so a room that reports usage in another shape — a
        deployment older than the seam's `role` and `cost_usd` — is a `KeyError` on turn 0 and
        not a README that silently prices the run wrong. The runner and the room it tallies
        move together.
        """
        return cls(
            role=call["role"],
            rung=call["rung"],
            input_tokens=call["input_tokens"],
            output_tokens=call["output_tokens"],
            cache_read_tokens=call["cache_read_tokens"],
            cache_write_tokens=call["cache_write_tokens"],
            latency_ms=call["latency_ms"],
            cost_usd=call["cost_usd"],
        )


@dataclass
class Played:
    idx: int
    team: str
    guide: str
    outcome: str
    interrupted: bool = False
    turnMs: int = 0
    usage: list[Usage] = field(default_factory=list)
    mechanical: list[str] = field(default_factory=list)
    appStatus: list[str] = field(default_factory=list)


@dataclass
class SessionResult:
    """One session of the run, as the README reads it: played, or refused with the reason."""

    name: str
    session_id: str | None
    played: list[Played]
    refused: str | None = None
    verdict: dict[str, Any] | None = None
    unjudged: str | None = None
    judge_usage: list[Usage] = field(default_factory=list)

    @property
    def faults(self) -> list[str]:
        return [f"turn {turn.idx}: {fault}" for turn in self.played for fault in turn.mechanical]

    @property
    def judged(self) -> str:
        """The judge's column: her verdict by her rule, or a dash where no verdict was reached."""
        if self.verdict is None:
            return "—"
        return "PASS" if passes(self.verdict) else "FAIL"

    @property
    def objections(self) -> list[str]:
        """Why the judge closed the gate, in the row: the score under its floor, the blocker quoted.

        The whole verdict is in the file beside the transcript; this is the part of it that
        decided, so a reader of the README knows what to open.
        """
        if self.verdict is None:
            return [f"juiz sem veredito: {self.unjudged}"] if self.unjudged else []
        scores: dict[str, int] = self.verdict["scores"]
        under = [
            f"juiz: {dimension} {score}"
            for dimension, score in scores.items()
            if score == 0 or (dimension in FLOORED and score < 3)
        ]
        blockers = [
            f"juiz: turn {incident['turn']} · blocker · {incident['kind']}"
            for incident in self.verdict["incidents"]
            if incident["severity"] == "blocker"
        ]
        return under + blockers

    @property
    def passed(self) -> bool:
        """Her rule for the run's own line: the judge approved and nothing mechanical tripped."""
        return self.judged == "PASS" and not self.faults and not self.refused


def load_script(path: Path) -> Script:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Script(
        name=raw["name"],
        pericopeId=raw["pericopeId"],
        language=raw["language"],
        turns=[
            ScriptTurn(
                team=turn.get("team"),
                kickoff=bool(turn.get("kickoff")),
                motherTongue=turn.get("motherTongue"),
                interrupted=bool(turn.get("interrupted")),
                rehearsal=turn["rehearsal"]["pieces"] if "rehearsal" in turn else None,
                rehearsalScene=turn["rehearsal"].get("sceneId") if "rehearsal" in turn else None,
                sceneRehearsals=turn.get("sceneRehearsals"),
                expect=turn.get("expect", {}),
            )
            for turn in raw["turns"]
        ],
        earlierPassages=raw.get("earlierPassages"),
    )


def _portuguese(language: str) -> bool:
    return re.search("portugu", language, re.I) is not None


def mother_tongue_note(language: str, seconds: int) -> str:
    if _portuguese(language):
        return (
            f"[A equipe falou na língua materna por cerca de {seconds} segundos; sem "
            "transcrição — nenhuma palavra chegou até você.]"
        )
    return (
        f"[The team spoke in their own language for about {seconds} seconds; no "
        "transcription — no words reached you.]"
    )


def rehearsal_team_text(language: str, transcripts: list[str]) -> str:
    pieces = [piece.strip() for piece in transcripts if piece.strip()]
    if len(pieces) == 1:
        note = (
            "[A equipe ensaiou esta cena na língua materna e traduziu o ensaio da cena. Segue a "
            "tradução:]"
            if _portuguese(language)
            else "[The team rehearsed this scene in their own language and translated the scene "
            "rehearsal. The translation follows:]"
        )
    elif _portuguese(language):
        note = (
            "[A equipe ensaiou esta cena na língua materna e traduziu o ensaio da cena frase por "
            f"frase ({len(pieces)} frases). Segue a tradução, na ordem:]"
        )
    else:
        note = (
            "[The team rehearsed this scene in their own language and translated the scene "
            f"rehearsal phrase by phrase ({len(pieces)} phrases). The translation follows, in "
            "order:]"
        )
    return f"{note} {' '.join(pieces)}"


def carried_scene_rehearsals(script: Script) -> list[list[str] | None]:
    current: list[str] | None = None
    carried = []
    for turn in script.turns:
        if turn.sceneRehearsals is not None:
            current = list(turn.sceneRehearsals)
        carried.append(current)
    return carried


def scene_rehearsals_fact(scene_ids: list[str], sent: list[str]) -> str:
    def listed(ids: list[str]) -> str:
        return ", ".join(ids) if ids else "none"

    reached = [scene for scene in scene_ids if scene in sent]
    missing = [scene for scene in scene_ids if scene not in sent]
    return (
        "SCENE REHEARSALS: parts whose recorded and translated scene rehearsal has reached you: "
        f"{listed(reached)}. Parts with none: {listed(missing)}."
    )


def interrupted_note(language: str) -> str:
    if _portuguese(language):
        return "[A equipe interrompeu a sua fala anterior neste ponto.]"
    return "[The team interrupted your previous turn at this point.]"


def request_for(
    turn: ScriptTurn,
    script: Script,
    session_id: str,
    scene_rehearsals: list[str] | None = None,
) -> tuple[dict[str, Any], str]:
    """The request her `turnRequest` builds for one scripted turn, and the team side she expects.

    The team side is what her runner hands the judge when the room sends no transcript: the
    words or the note, behind her interrupted note when the team cut in.
    """
    body: dict[str, Any] = {"sessionId": session_id}
    said = ""
    if turn.kickoff:
        said = opening_note(script.pericopeId, "pt" if _portuguese(script.language) else "en")
        body.update(roomNote="session_start", noteText=said)
    elif turn.motherTongue:
        said = mother_tongue_note(script.language, turn.motherTongue)
        body.update(roomNote="mother_tongue", seconds=turn.motherTongue, noteText=said)
    elif turn.rehearsal is not None:
        said = rehearsal_team_text(script.language, turn.rehearsal)
        body["teamText"] = said
    elif turn.team:
        said = turn.team
        body["teamText"] = said
    elif turn.interrupted:
        body.update(roomNote="interrupted", noteText=interrupted_note(script.language))
    else:
        body["teamText"] = ""
    if turn.interrupted:
        body["interrupted"] = True
    if scene_rehearsals is not None:
        body["sceneRehearsals"] = scene_rehearsals
    cut = interrupted_note(script.language) if turn.interrupted else ""
    return body, " ".join(part for part in (cut, said) if part)


async def open_session(script: Script, client: httpx.AsyncClient) -> str:
    body: dict[str, Any] = {"pericopeId": script.pericopeId, "language": script.language}
    if script.earlierPassages:
        body["earlierPassages"] = script.earlierPassages
    opened = await client.post("golden/session", json=body)
    opened.raise_for_status()
    return str(opened.json()["sessionId"])


async def play(
    script: Script,
    client: httpx.AsyncClient,
    *,
    session_id: str,
    played: list[Played],
    turns: int | None = None,
) -> None:
    """Play the script's turns, appending each one to `played` as it lands.

    Appended as it lands and not returned at the end, so a turn that fails still leaves the
    turns before it in the caller's hands — and what they cost — instead of taking the whole
    run's transcript down with the error.
    """
    previous_guide = played[-1].guide if played else ""
    carried = carried_scene_rehearsals(script)
    scene_ids = scene_ids_for(script.pericopeId)
    earlier = earlier_passages_line(
        script.pericopeId, book_of(script.pericopeId), script.earlierPassages
    )
    moment: Moment | None = None
    heard = 2 * len(played)
    for idx, turn in enumerate(script.turns[:turns]):
        body, expected = request_for(turn, script, session_id, carried[idx])
        started = time.monotonic()
        answered = await client.post("golden/turn", json=body)
        answered.raise_for_status()
        reply = answered.json()
        line = Played(
            idx=idx,
            team=reply.get("transcript") or expected,
            guide=reply["guideText"],
            outcome=reply["outcome"],
            interrupted=turn.interrupted,
            turnMs=int(reply.get("latencyMs") or round((time.monotonic() - started) * 1000)),
            usage=[Usage.from_wire(call) for call in reply.get("usage") or []],
            appStatus=[
                fact
                for fact in (
                    scene_rehearsals_fact(scene_ids, carried[idx])
                    if carried[idx] is not None
                    else "",
                    earlier,
                )
                if fact
            ],
        )
        arriving = (
            scene_ids.index(turn.rehearsalScene) + 1 if turn.rehearsalScene in scene_ids else None
        )
        before = moment_at_turn_start(moment, heard=heard, parts=len(scene_ids), arriving=arriving)
        after = (
            moment_after_reply(
                before,
                line.guide,
                outcome=line.outcome,
                parts=len(scene_ids),
                came_back=[
                    scene_ids.index(scene) + 1 for scene in carried[idx] or [] if scene in scene_ids
                ],
                unmarked_now=turn.rehearsal is not None and turn.rehearsalScene is None,
            )
            if before
            else None
        )
        moment, heard = after, heard + 2
        line.mechanical = mechanical_checks(
            guide=line.guide,
            outcome=line.outcome,
            expect=turn.expect,
            previous_guide=previous_guide,
            earlier_guides=[earlier_turn.guide for earlier_turn in played],
            parts=len(scene_ids),
            moment_before=before,
            moment_after=after,
        )
        previous_guide = line.guide
        played.append(line)
        for call in line.usage:
            print(f"    {usage_line(call)}")
        flag = f" ⚠ {'; '.join(line.mechanical)}" if line.mechanical else ""
        print(f"  [{idx}] {line.outcome:<9} {line.turnMs} ms  {line.guide[:90]}…{flag}")


def usage_line(call: Usage) -> str:
    """One model call, spelled the way her `[llm-usage]` line is: who, on what, and the tokens.

    Her line ends at the tokens and a person prices the run from a table afterwards; this
    room's seam already prices the call at list price and times it, so both ride along.
    """
    priced = f" US$ {call.cost_usd}" if call.cost_usd is not None else ""
    took = f" {call.latency_ms} ms" if call.latency_ms is not None else ""
    return (
        f"[llm-usage] {call.role} {call.rung} in={call.input_tokens} "
        f"cache_read={call.cache_read_tokens or 0} cache_write={call.cache_write_tokens or 0} "
        f"out={call.output_tokens}{priced}{took}"
    )


def judge_transcript(played: list[Played]) -> str:
    """The transcript block, spelled exactly as her runner hands it to the judge."""
    return "\n\n".join(
        f"[turn {turn.idx}]\n"
        + "".join(
            f"APP STATUS (what the app told the guide this turn): {fact}\n"
            for fact in turn.appStatus
        )
        + f"TEAM: {turn.team}\nGUIDE ({turn.outcome}): {turn.guide}"
        for turn in played
    )


def export(
    script: Script,
    *,
    session_id: str,
    base_url: str,
    played: list[Played],
    out: Path,
    stamp: str,
    refused: str | None = None,
) -> tuple[Path, Path]:
    out.mkdir(parents=True, exist_ok=True)
    report = out / f"{script.name}.{stamp}.json"
    transcript = out / f"{script.name}.{stamp}.transcript.txt"
    report.write_text(
        json.dumps(
            {
                "name": script.name,
                "pericopeId": script.pericopeId,
                "language": script.language,
                "baseUrl": base_url,
                "sessionId": session_id,
                "refused": refused,
                "turns": [asdict(turn) for turn in played],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    transcript.write_text(judge_transcript(played) + "\n", encoding="utf-8")
    return report, transcript


def scripts_to_play(args: argparse.Namespace) -> list[Path]:
    if args.script:
        return [Path(args.script)]
    vendored = sorted(Path(args.sessions).glob("*.json"))
    return [path for path in vendored if not args.only or path.stem == args.only]


async def play_session(
    script: Script,
    client: httpx.AsyncClient,
    *,
    base_url: str,
    out: Path,
    stamp: str,
    turns: int | None,
) -> SessionResult:
    """One session, opened and played, and its two files written whatever happened after turn 0.

    A refusal is a result, not an exception: the pericope a room does not hold, the key it
    does not accept, the turn it could not run all come back as the status and the body the
    room answered with, and the run goes on to the next script. The export sits in a
    `finally` for the same reason `play` appends as it goes — the turns already paid for
    survive the turn that failed.
    """
    print(f"\n▶ {script.name} ({script.pericopeId}, {script.language}) — {len(script.turns)} turns")
    played: list[Played] = []
    try:
        session_id = await open_session(script, client)
    except httpx.HTTPStatusError as refused:
        print(f"  refused: {refused.response.status_code} {refused.response.text}")
        return SessionResult(script.name, None, [], _refusal(refused))
    result = SessionResult(script.name, session_id, played)
    try:
        await play(script, client, session_id=session_id, played=played, turns=turns)
    except httpx.HTTPStatusError as refused:
        print(f"  refused: {refused.response.status_code} {refused.response.text}")
        result.refused = _refusal(refused)
    finally:
        report, transcript = export(
            script,
            session_id=session_id,
            base_url=base_url,
            played=played,
            out=out,
            stamp=stamp,
            refused=result.refused,
        )
        print(f"  {report}\n  {transcript}")
    if result.refused is None:
        await judge(script, result, out=out, stamp=stamp)
    return result


async def judge(script: Script, result: SessionResult, *, out: Path, stamp: str) -> None:
    """Her judge on the session, and its verdict written beside the transcript — or the reason not.

    A judge that fails — a provider down, a reply outside the shape it was bound to — is a
    session without a verdict, which her runner treats as a session that did not pass, and
    the run goes on to the next script: the transcript already paid for is on disk, and the
    row says what the judge did not say. A verdict that never came is not written.

    The call's cost is read the way the seam reads a turn's: off the one usage line
    `call_agent` writes, through the seam's own collector, so the judge is priced into the
    run beside the Guide and the Validator — as her US$ 8 counted it — and not from a
    second ledger. The line is written at INFO and this process configures no logging, so
    the logger is opened to that level here or the call is silently free.
    """
    logging.getLogger("app.services.internalization_room.llm").setLevel(logging.INFO)
    with _collecting_model_calls() as calls:
        try:
            result.verdict = await judge_session(
                pericope=script.pericopeId,
                language=script.language,
                transcript=judge_transcript(result.played),
            )
        except Exception as failed:
            result.unjudged = str(failed)
            print(f"  [judge] failed — no verdict for this session: {failed}")
    result.judge_usage = [Usage.from_wire(call.model_dump()) for call in calls]
    for call in result.judge_usage:
        print(f"    {usage_line(call)}")
    if result.verdict is None:
        return
    verdict = out / f"{script.name}.{stamp}.verdict.json"
    verdict.write_text(
        json.dumps(result.verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"  {verdict}")


def _refusal(refused: httpx.HTTPStatusError) -> str:
    return f"{refused.response.status_code} {refused.response.text}"


def _pins() -> str:
    freeze = read_pin(FREEZE_FILE).commit[:7]
    return f"roteiros e doutrina no pin `{freeze}` · cânon `{vendor_pin()[:7]}`"


def _tip() -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "?"


def _seconds(values: list[int]) -> str:
    if not values:
        return "—"
    low, high = min(values) / 1000, max(values) / 1000
    return f"{low:.0f} a {high:.0f} s (mediana ≈ {statistics.median(values) / 1000:.0f} s)"


def _paid(results: list[SessionResult]) -> list[tuple[str, str, float | None]]:
    calls = [call for result in results for turn in result.played for call in turn.usage]
    calls += [call for result in results for call in result.judge_usage]
    return [(call.role, call.rung, call.cost_usd) for call in calls]


def _spent(results: list[SessionResult]) -> float:
    return sum(priced(_paid(results))[0].values())


def summary(
    results: list[SessionResult],
    *,
    base_url: str,
    stamp: str,
    tip: str,
    pins: str,
    halted: str = "",
) -> str:
    """The run's README, in the shape of hers: the verdict line, the table, the money, the clock.

    Two columns, as her reports keep them: the judge's PASS or FAIL by her rule, and the
    mechanical count, each read from its own source so a warning is never laundered into a
    judge failure nor a judge failure into a warning, in either direction. What her table's
    last column says by hand, ours says by listing the faults, the judge's objections, or
    the room's refusal.
    """
    played = [turn for result in results for turn in result.played]
    faults = sum(len(result.faults) for result in results)
    refused = [result for result in results if result.refused]
    approved = sum(1 for result in results if result.judged == "PASS")
    fail_safes = sum(1 for turn in played if turn.outcome == "fail_safe")
    by_role, unpriced = priced(_paid(results))
    voice = [
        sum(call.latency_ms or 0 for call in turn.usage if call.role in ("guide", "validator"))
        for turn in played
        if turn.usage
    ]
    lines = [
        f"# Sessões-ouro — {stamp[:10]}, esta sala em `{tip}`, `{base_url}`",
        "",
        f"Rodada `{stamp}` de `scripts/golden_runner.py` sobre os roteiros dela ({pins}): "
        f"**{approved}/{len(results)} aprovadas pelo juiz, {faults} avisos mecânicos, "
        f"{fail_safes} fail-safes em {len(played)} turnos reais"
        f"{f', {len(refused)} sessões recusadas' if refused else ''}.**",
        "",
        "Este portão vale para o release, não só para o CI (DOCTRINE §5.2): nada que toque "
        "prompt, laço de turno, modelo ou tela chega à equipe sem as sessões-ouro aprovadas "
        "pelo juiz e sem aviso mecânico — uma suíte verde não basta para publicar uma mudança "
        "de prompt.",
        "",
        "| Sessão | Juiz | Mecânico | Observação |",
        "|---|---|---|---|",
    ]
    for result in results:
        column = "recusada" if result.refused else str(len(result.faults))
        if result.refused and result.faults:
            column = f"recusada · {len(result.faults)}"
        noted = "; ".join(
            ([result.refused] if result.refused else []) + result.faults + result.objections
        )
        lines.append(f"| {result.name} | {result.judged} | {column} | {noted} |")
    lines.append("")
    if by_role:
        total = sum(by_role.values())
        free = (
            f"; {len(unpriced)} chamada{'s' if len(unpriced) > 1 else ''} sem preço de tabela "
            f"({', '.join(sorted(set(unpriced)))}), fora da soma"
            if unpriced
            else ""
        )
        lines.append(
            f"Custo da rodada (linhas `[llm-usage]`, preços de tabela): ≈ US$ {total:.2f} "
            f"— {split(by_role)}{free}."
        )
    else:
        lines.append("A sala não informou custo por chamada nesta rodada.")
    if voice:
        lines.append(
            f"Latência Guia+Validador por turno: {_seconds(voice)}; turno inteiro, com o "
            f"classificador em linha: {_seconds([turn.turnMs for turn in played])}."
        )
    if halted:
        lines.append(halted)
    return "\n".join(lines) + "\n"


async def run(args: argparse.Namespace) -> int:
    if args.rejudge:
        return await rejudge(args)
    scripts = [load_script(path) for path in scripts_to_play(args)]
    if not scripts:
        print(f"golden: no session named {args.only}", file=sys.stderr)
        return 2
    base_url = args.base_url.rstrip("/") + "/"
    headers = {"Authorization": f"Bearer {args.access_code}"} if args.access_code else {}
    out = Path(args.out)
    stamp = args.stamp or datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    budget = budget_of(args)
    results: list[SessionResult] = []
    not_started: list[str] = []
    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=600) as client:
        for position, script in enumerate(scripts):
            if _spent(results) >= budget:
                not_started = [later.name for later in scripts[position:]]
                break
            results.append(
                await play_session(
                    script, client, base_url=base_url, out=out, stamp=stamp, turns=args.turns
                )
            )
    return finish(
        results,
        out=out,
        base_url=base_url,
        stamp=stamp,
        budget=budget,
        not_started=not_started,
    )


def finish(
    results: list[SessionResult],
    *,
    out: Path,
    base_url: str,
    stamp: str,
    budget: float,
    not_started: list[str],
) -> int:
    if not not_started:
        return close(results, out=out, base_url=base_url, stamp=stamp)
    by_role, unpriced = priced(_paid(results))
    spent = sum(by_role.values())
    halted = (
        f"Rodada parada pelo orçamento de US$ {budget:.2f}, já em US$ {spent:.2f}. "
        f"Sessões que não começaram: {', '.join(not_started)}."
    )
    close(results, out=out, base_url=base_url, stamp=stamp, halted=halted)
    message = stopped(
        "golden", budget=budget, spent=spent, not_started=not_started, unpriced=unpriced
    )
    print(message, file=sys.stderr)
    return OVER_BUDGET


def exported(path: Path) -> tuple[Script, SessionResult, str]:
    """A session as a run left it: the script's head, the turns played, the room it was played on.

    The turns' usage is left out on purpose: those calls were paid for by the run that
    exported them and are already in its README, and a re-judgement's money is the judge's.
    A refusal comes back with the session, so a run cut short by the room is not rebuilt
    as a whole one; an export older than the field is read as played whole, which is what
    those runs were.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    script = Script(raw["name"], raw["pericopeId"], raw["language"], turns=[])
    played = [
        Played(
            idx=turn["idx"],
            team=turn["team"],
            guide=turn["guide"],
            outcome=turn["outcome"],
            interrupted=turn["interrupted"],
            turnMs=turn["turnMs"],
            mechanical=turn["mechanical"],
            appStatus=turn.get("appStatus", []),
        )
        for turn in raw["turns"]
    ]
    result = SessionResult(script.name, raw["sessionId"], played, refused=raw.get("refused"))
    return script, result, raw["baseUrl"]


async def rejudge(args: argparse.Namespace) -> int:
    """Her judge over a run already on disk, with the room left alone.

    A judge prompt that changes, or a rung that does, changes the verdict and not the
    transcript; and a run's verdict can be asked for twice without paying for the sessions
    again. Each `<name>.<stamp>.json` of the earlier run is read back, judged with the map its
    pericope names today, and its verdict written under the same name and stamp into `--out`,
    so the file still says which transcript it judged. The mechanical column is the one the
    run exported; the judge's column is this call's. A session the room refused is not
    judged here either, and its row stays `recusada`. Writing into the directory being read
    is refused: `--out` defaults to today's date, which on the day of the run is that very
    directory, and `close` would replace the README that records what the run cost.
    """
    out = Path(args.out)
    if out.resolve() == Path(args.rejudge).resolve():
        print(
            f"golden: --out is the run being judged again ({args.rejudge}); its README records "
            "what that run cost and a re-judgement would write over it — name another --out",
            file=sys.stderr,
        )
        return 2
    exports = [
        path
        for path in sorted(Path(args.rejudge).glob("*.json"))
        if not path.name.endswith(".verdict.json")
    ]
    if not exports:
        print(f"golden: nothing exported under {args.rejudge}", file=sys.stderr)
        return 2
    budget = budget_of(args)
    results: list[SessionResult] = []
    not_started: list[str] = []
    base_url = ""
    for position, path in enumerate(exports):
        if _spent(results) >= budget:
            not_started = [exported(later)[0].name for later in exports[position:]]
            break
        script, result, base_url = exported(path)
        print(f"\n▶ {script.name} — judging {path.name} again")
        out.mkdir(parents=True, exist_ok=True)
        if result.refused is None:
            await judge(script, result, out=out, stamp=path.stem[len(script.name) + 1 :])
        results.append(result)
    stamp = args.stamp or datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    return finish(
        results,
        out=out,
        base_url=base_url,
        stamp=stamp,
        budget=budget,
        not_started=not_started,
    )


def close(
    results: list[SessionResult], *, out: Path, base_url: str, stamp: str, halted: str = ""
) -> int:
    out.mkdir(parents=True, exist_ok=True)
    (out / "README.md").write_text(
        summary(results, base_url=base_url, stamp=stamp, tip=_tip(), pins=_pins(), halted=halted),
        encoding="utf-8",
    )
    passed = sum(1 for result in results if result.passed)
    for result in results:
        verdict = "REFUSED" if result.refused else ("PASS" if result.passed else "FAIL")
        print(
            f"  {verdict} · {result.name} · judge={result.judged.lower().replace('—', 'n/a')} "
            f"· mechanical={len(result.faults)} · cost US$ {_spent([result]):.2f}"
        )
    by_role, unpriced = priced(_paid(results))
    if by_role:
        print(f"\ncost US$ {sum(by_role.values()):.2f} — {split(by_role)}{uncounted(unpriced)}")
    print(f"\n{passed}/{len(results)} golden sessions pass · {out / 'README.md'}")
    return 0 if passed == len(results) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--rejudge", default=None)
    parser.add_argument("--script", default=None)
    parser.add_argument("--sessions", default=str(SESSIONS_DIR))
    parser.add_argument("--only", default=None)
    parser.add_argument(
        "--out", default=str(REPO_ROOT / "golden/reports" / datetime.now(UTC).strftime("%Y-%m-%d"))
    )
    parser.add_argument("--turns", type=int, default=None)
    parser.add_argument("--budget-usd", type=float, default=None)
    parser.add_argument("--stamp", default=None)
    parser.add_argument("--access-code", default=os.environ.get("ACCESS_CODE", ""))
    args = parser.parse_args()
    if not args.base_url and not args.rejudge:
        parser.error("--base-url names the room to play, or --rejudge <dir> a run to judge again")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())

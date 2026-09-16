"""Play her golden sessions through a room by text, and leave a report directory per run.

The scripts are hers, vendored byte for byte at `golden/sessions/` under the pin in
`docs/doctrine/DOCTRINE_PIN`: the exact words the team says, turn by turn, with the room-notes
her app hands the Guide — a kickoff, the team speaking their own language for N seconds, an
interruption. The base URL is the only thing that says which room is being judged: her app
takes `https://<her-app>/api`, this room takes `http://<host>/api/internalization-room/text-seam`,
and the requests are the same.

    ACCESS_CODE=<key> uv run python scripts/golden_runner.py \\
        --base-url http://127.0.0.1:8044/api/internalization-room/text-seam \\
        [--only P01-understand-first] [--turns 5] [--out golden/reports/<date>]

One command is the five, as `npm run golden` is on her side; `--only` names one of them and
`--script <path>` plays a script from anywhere. Per turn the runner prints the outcome, the
wall clock and the faults her mechanical checks name, and one `[llm-usage]` line per model
call the room reported. A session the room refuses — a pericope this canon does not hold — is
one line of the report, not the end of the run.

`--out` defaults to `golden/reports/<date>/`, committed, so two runs a week apart can be
compared by a person who was not in the room. Per session it holds `<name>.<stamp>.json`, one
entry per turn with the four fields the judge is defined against (turn index, team turn,
guide turn, outcome tag), the mechanical faults and what the room said each turn cost; and
`<name>.<stamp>.transcript.txt`, the transcript block exactly as her runner pastes it into
`prompts/golden_judge_system_prompt.md`. `README.md` is the run's summary in the shape of
her `golden/reports/2026-09-03/README.md`: a row per session, the mechanical column, cost
and latency beside her ≈US$ 8 and median 27 s. The judge's column waits for the judge.

The exit code is the gate: 1 when any session tripped a check or was refused, 2 when there was
nothing to play, 0 when every session played clean.
"""

from __future__ import annotations

import argparse
import asyncio
import json
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

from scripts.golden_checks import mechanical_checks

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSIONS_DIR = REPO_ROOT / "golden/sessions"


@dataclass
class ScriptTurn:
    team: str | None = None
    kickoff: bool = False
    motherTongue: int | None = None
    interrupted: bool = False
    expect: dict[str, Any] = field(default_factory=dict)


@dataclass
class Script:
    name: str
    pericopeId: str
    language: str
    turns: list[ScriptTurn]


@dataclass
class Played:
    idx: int
    team: str
    guide: str
    outcome: str
    interrupted: bool = False
    turnMs: int = 0
    usage: list[dict[str, Any]] = field(default_factory=list)
    mechanical: list[str] = field(default_factory=list)


@dataclass
class SessionResult:
    """One session of the run, as the README reads it: played, or refused with the reason."""

    name: str
    session_id: str | None
    played: list[Played]
    refused: str | None = None

    @property
    def faults(self) -> list[str]:
        return [f"turn {turn.idx}: {fault}" for turn in self.played for fault in turn.mechanical]


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
                expect=turn.get("expect", {}),
            )
            for turn in raw["turns"]
        ],
    )


def _portuguese(language: str) -> bool:
    return re.search("portugu", language, re.I) is not None


def opening_note(pericope_id: str, language: str) -> str:
    """Her server-owned opening note, so both exports read the same turn 0."""
    if _portuguese(language):
        return (
            f"[A sessão acabou de começar. A equipe abriu a passagem {pericope_id} e está à "
            "mesa, pronta para começar. Fale primeiro.]"
        )
    return (
        f"[The session has just begun. The team opened passage {pericope_id} and is at the "
        "table, ready to begin. Speak first.]"
    )


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


def request_for(turn: ScriptTurn, script: Script, session_id: str) -> dict[str, Any]:
    body: dict[str, Any] = {"sessionId": session_id}
    if turn.kickoff:
        body["kickoff"] = True
    elif turn.motherTongue:
        body["text"] = mother_tongue_note(script.language, turn.motherTongue)
        body["motherTongue"] = turn.motherTongue
    else:
        body["text"] = turn.team or ""
    if turn.interrupted:
        body["interrupted"] = True
    return body


async def open_session(script: Script, client: httpx.AsyncClient) -> str:
    opened = await client.post(
        "session", json={"pericopeId": script.pericopeId, "language": script.language}
    )
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
    for idx, turn in enumerate(script.turns[:turns]):
        body = request_for(turn, script, session_id)
        started = time.monotonic()
        answered = await client.post("turn", json=body)
        answered.raise_for_status()
        reply = answered.json()
        line = Played(
            idx=idx,
            team=reply.get("transcript")
            or body.get("text")
            or opening_note(script.pericopeId, script.language),
            guide=reply["guideText"],
            outcome=reply["outcome"],
            interrupted=turn.interrupted,
            turnMs=int(reply.get("turnMs") or round((time.monotonic() - started) * 1000)),
            usage=list(reply.get("usage") or []),
        )
        line.mechanical = mechanical_checks(
            guide=line.guide,
            outcome=line.outcome,
            expect=turn.expect,
            previous_guide=previous_guide,
        )
        previous_guide = line.guide
        played.append(line)
        for call in line.usage:
            print(f"    {usage_line(call)}")
        flag = f" ⚠ {'; '.join(line.mechanical)}" if line.mechanical else ""
        print(f"  [{idx}] {line.outcome:<9} {line.turnMs} ms  {line.guide[:90]}…{flag}")


def usage_line(call: dict[str, Any]) -> str:
    """One model call, spelled the way her `[llm-usage]` line is: who, on what, and the tokens.

    Her line ends at the tokens and a person prices the run from a table afterwards; this
    room's seam already prices the call at list price and times it, so both ride along.
    """
    cost = call.get("cost_usd")
    priced = f" US$ {cost}" if cost is not None else ""
    took = f" {call['latency_ms']} ms" if call.get("latency_ms") is not None else ""
    return (
        f"[llm-usage] {call.get('role', '?')} {call.get('rung', '?')} "
        f"in={call.get('input_tokens', 0)} cache_read={call.get('cache_read_tokens') or 0} "
        f"cache_write={call.get('cache_write_tokens') or 0} out={call.get('output_tokens', 0)}"
        f"{priced}{took}"
    )


def judge_transcript(played: list[Played]) -> str:
    """The transcript block, spelled exactly as her runner hands it to the judge."""
    return "\n\n".join(
        f"[turn {turn.idx}]\nTEAM: {turn.team}\nGUIDE ({turn.outcome}): {turn.guide}"
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
            script, session_id=session_id, base_url=base_url, played=played, out=out, stamp=stamp
        )
        print(f"  {report}\n  {transcript}")
    return result


def _refusal(refused: httpx.HTTPStatusError) -> str:
    return f"{refused.response.status_code} {refused.response.text}"


def _pins() -> str:
    doctrine = next(
        line.split()[1]
        for line in (REPO_ROOT / "docs/doctrine/DOCTRINE_PIN").read_text().splitlines()
        if line.startswith("commit ")
    )
    canon = (REPO_ROOT / "app/services/internalization_room/canon/vendor/VENDOR_PIN").read_text()
    return f"roteiros e doutrina no pin `{doctrine[:7]}` · cânon `{canon.strip()[:7]}`"


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


def summary(results: list[SessionResult], *, base_url: str, stamp: str, tip: str, pins: str) -> str:
    """The run's README, in the shape of hers: the verdict line, the table, the money, the clock.

    The judge's column is a dash on every row until the judge is wired; the mechanical column
    is hers exactly, a count kept apart from any verdict so a warning is never laundered into
    a judge failure in either direction. What her table's last column says by hand, ours says
    by listing the faults, or the room's refusal.
    """
    played = [turn for result in results for turn in result.played]
    faults = sum(len(result.faults) for result in results)
    refused = [result for result in results if result.refused]
    clean = sum(1 for result in results if not result.faults and not result.refused)
    fail_safes = sum(1 for turn in played if turn.outcome == "fail_safe")
    calls = [call for turn in played for call in turn.usage]
    by_role: dict[str, float] = {}
    for call in calls:
        if call.get("cost_usd") is not None:
            by_role[call["role"]] = by_role.get(call["role"], 0.0) + call["cost_usd"]
    voice = [
        sum(
            call.get("latency_ms") or 0
            for call in turn.usage
            if call["role"] in ("guide", "validator")
        )
        for turn in played
        if turn.usage
    ]
    lines = [
        f"# Sessões-ouro — {stamp[:10]}, esta sala em `{tip}`, `{base_url}`",
        "",
        f"Rodada `{stamp}` de `scripts/golden_runner.py` sobre os roteiros dela ({pins}): "
        f"**{clean}/{len(results)} sem aviso mecânico (juiz ainda não ligado), {faults} avisos "
        f"mecânicos, {fail_safes} fail-safes em {len(played)} turnos reais"
        f"{f', {len(refused)} sessões recusadas' if refused else ''}.**",
        "",
        "| Sessão | Juiz | Mecânico | Observação |",
        "|---|---|---|---|",
    ]
    for result in results:
        if result.refused:
            lines.append(f"| {result.name} | — | recusada | {result.refused} |")
        else:
            lines.append(
                f"| {result.name} | — | {len(result.faults)} | {'; '.join(result.faults)} |"
            )
    if by_role:
        total = sum(by_role.values())
        split = " · ".join(f"{role} US$ {cost:.2f}" for role, cost in sorted(by_role.items()))
        lines += [
            "",
            f"Custo da rodada (linhas `[llm-usage]`, preços de tabela): ≈ US$ {total:.2f} "
            f"— {split}.",
            f"Latência Guia+Validador por turno: {_seconds(voice)}; turno inteiro, com o "
            f"classificador em linha: {_seconds([turn.turnMs for turn in played])}.",
        ]
    else:
        lines += ["", "A sala não informou custo por chamada nesta rodada."]
    return "\n".join(lines) + "\n"


async def run(args: argparse.Namespace) -> int:
    scripts = [load_script(path) for path in scripts_to_play(args)]
    if not scripts:
        print(f"golden: no session named {args.only}", file=sys.stderr)
        return 2
    base_url = args.base_url.rstrip("/") + "/"
    headers = {"X-Access-Code": args.access_code} if args.access_code else {}
    out = Path(args.out)
    stamp = args.stamp or datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    results: list[SessionResult] = []
    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=600) as client:
        for script in scripts:
            results.append(
                await play_session(
                    script, client, base_url=base_url, out=out, stamp=stamp, turns=args.turns
                )
            )
    out.mkdir(parents=True, exist_ok=True)
    (out / "README.md").write_text(
        summary(results, base_url=base_url, stamp=stamp, tip=_tip(), pins=_pins()),
        encoding="utf-8",
    )
    passed = sum(1 for result in results if not result.faults and not result.refused)
    for result in results:
        verdict = "REFUSED" if result.refused else ("PASS" if not result.faults else "FAIL")
        print(f"  {verdict} · {result.name} · mechanical={len(result.faults)}")
    print(f"\n{passed}/{len(results)} golden sessions pass · {out / 'README.md'}")
    return 0 if passed == len(results) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--script", default=None)
    parser.add_argument("--sessions", default=str(SESSIONS_DIR))
    parser.add_argument("--only", default=None)
    parser.add_argument(
        "--out", default=str(REPO_ROOT / "golden/reports" / datetime.now(UTC).strftime("%Y-%m-%d"))
    )
    parser.add_argument("--turns", type=int, default=None)
    parser.add_argument("--stamp", default=None)
    parser.add_argument("--access-code", default=os.environ.get("ACCESS_CODE", ""))
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())

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

from app.api.internalization_room.text_seam import _collecting_model_calls, _language_code
from app.services.internalization_room.golden_judge import FLOORED, judge_session, passes
from app.services.internalization_room.turn.speech import mother_tongue_note
from scripts.golden_checks import mechanical_checks, unported_checks
from scripts.sync_doctrine import read_pin

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
    pending: list[str] = field(default_factory=list)


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


def request_for(turn: ScriptTurn, script: Script, session_id: str) -> dict[str, Any]:
    body: dict[str, Any] = {"sessionId": session_id}
    if turn.kickoff:
        body["kickoff"] = True
    elif turn.motherTongue:
        body["text"] = mother_tongue_note(_language_code(script.language), turn.motherTongue * 1000)
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
            usage=[Usage.from_wire(call) for call in reply.get("usage") or []],
        )
        line.mechanical = mechanical_checks(
            guide=line.guide,
            outcome=line.outcome,
            expect=turn.expect,
            previous_guide=previous_guide,
        )
        line.pending = unported_checks(turn.expect)
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
    canon = (REPO_ROOT / "app/services/internalization_room/canon/vendor/VENDOR_PIN").read_text()
    return f"roteiros e doutrina no pin `{read_pin().commit[:7]}` · cânon `{canon.strip()[:7]}`"


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
    by_role: dict[str, float] = {}
    unpriced: list[str] = []
    spent = [call for turn in played for call in turn.usage]
    spent += [call for result in results for call in result.judge_usage]
    for call in spent:
        if call.cost_usd is None:
            unpriced.append(call.rung)
        else:
            by_role[call.role] = by_role.get(call.role, 0.0) + call.cost_usd
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
    pending = [
        f"{result.name} turn {turn.idx}: {', '.join(turn.pending)}"
        for result in results
        for turn in result.played
        if turn.pending
    ]
    if pending:
        lines.append(
            "Checagens dela que esta sala ainda não porta — PENDING, nenhuma conta como "
            f"aprovada: {'; '.join(pending)}."
        )
        lines.append("")
    if by_role:
        total = sum(by_role.values())
        split = " · ".join(f"{role} US$ {cost:.2f}" for role, cost in sorted(by_role.items()))
        free = (
            f"; {len(unpriced)} chamada{'s' if len(unpriced) > 1 else ''} sem preço de tabela "
            f"({', '.join(sorted(set(unpriced)))}), fora da soma"
            if unpriced
            else ""
        )
        lines.append(
            f"Custo da rodada (linhas `[llm-usage]`, preços de tabela): ≈ US$ {total:.2f} "
            f"— {split}{free}."
        )
    else:
        lines.append("A sala não informou custo por chamada nesta rodada.")
    if voice:
        lines.append(
            f"Latência Guia+Validador por turno: {_seconds(voice)}; turno inteiro, com o "
            f"classificador em linha: {_seconds([turn.turnMs for turn in played])}."
        )
    return "\n".join(lines) + "\n"


async def run(args: argparse.Namespace) -> int:
    if args.rejudge:
        return await rejudge(args)
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
    return close(results, out=out, base_url=base_url, stamp=stamp)


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
            pending=turn.get("pending", []),
        )
        for turn in raw["turns"]
    ]
    result = SessionResult(script.name, raw["sessionId"], played, refused=raw.get("refused"))
    return script, result, raw["baseUrl"]


async def rejudge(args: argparse.Namespace) -> int:
    """Her judge over a run already on disk, with the room left alone.

    A judge prompt that changes, or a rung that does, changes the verdict and not the
    transcript; and a run's verdict can be asked for twice without paying the five sessions
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
    results: list[SessionResult] = []
    base_url = ""
    for path in sorted(Path(args.rejudge).glob("*.json")):
        if path.name.endswith(".verdict.json"):
            continue
        script, result, base_url = exported(path)
        print(f"\n▶ {script.name} — judging {path.name} again")
        out.mkdir(parents=True, exist_ok=True)
        if result.refused is None:
            await judge(script, result, out=out, stamp=path.stem[len(script.name) + 1 :])
        results.append(result)
    if not results:
        print(f"golden: nothing exported under {args.rejudge}", file=sys.stderr)
        return 2
    stamp = args.stamp or datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    return close(results, out=out, base_url=base_url, stamp=stamp)


def close(results: list[SessionResult], *, out: Path, base_url: str, stamp: str) -> int:
    out.mkdir(parents=True, exist_ok=True)
    (out / "README.md").write_text(
        summary(results, base_url=base_url, stamp=stamp, tip=_tip(), pins=_pins()),
        encoding="utf-8",
    )
    passed = sum(1 for result in results if result.passed)
    for result in results:
        verdict = "REFUSED" if result.refused else ("PASS" if result.passed else "FAIL")
        print(
            f"  {verdict} · {result.name} · judge={result.judged.lower().replace('—', 'n/a')} "
            f"· mechanical={len(result.faults)}"
        )
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
    parser.add_argument("--stamp", default=None)
    parser.add_argument("--access-code", default=os.environ.get("ACCESS_CODE", ""))
    args = parser.parse_args()
    if not args.base_url and not args.rejudge:
        parser.error("--base-url names the room to play, or --rejudge <dir> a run to judge again")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())

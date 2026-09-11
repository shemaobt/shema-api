"""Drive one of her golden sessions through a room by text, and export what the judge reads.

The script is hers (`golden/sessions/<name>.json` in Tripod-Internalization): the exact words
the team says, turn by turn, with the room-notes her app hands the Guide — a kickoff, the
team speaking their own language for N seconds, an interruption. The base URL is the only
thing that says which room is being judged: her app takes `https://<her-app>/api`, this room
takes `http://<host>/api/internalization-room/text-seam`, and the requests are the same.

    ACCESS_CODE=<key> uv run python scripts/golden_runner.py \\
        --base-url http://127.0.0.1:8044/api/internalization-room/text-seam \\
        --script ../Tripod-Internalization/golden/sessions/P01-understand-first.json \\
        --out golden/reports/2026-09-11 [--turns 5]

Two files land in `--out`: `<name>.<stamp>.json`, one entry per turn with the four fields the
judge is defined against (turn index, team turn, guide turn, outcome tag) and whatever the
room said about cost; and `<name>.<stamp>.transcript.txt`, the transcript block exactly as
her runner pastes it into `prompts/golden_judge_system_prompt.md`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


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
    for idx, turn in enumerate(script.turns[:turns]):
        body = request_for(turn, script, session_id)
        started = time.monotonic()
        answered = await client.post("turn", json=body)
        answered.raise_for_status()
        reply = answered.json()
        played.append(
            Played(
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
        )
        line = played[-1]
        print(f"  [{idx}] {line.outcome:<9} {line.turnMs} ms  {line.guide[:90]}…")


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


async def run(args: argparse.Namespace) -> int:
    script = load_script(Path(args.script))
    base_url = args.base_url.rstrip("/") + "/"
    headers = {"X-Access-Code": args.access_code} if args.access_code else {}
    print(f"▶ {script.name} ({script.pericopeId}, {script.language}) → {base_url}")
    played: list[Played] = []
    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=600) as client:
        session_id = await open_session(script, client)
        try:
            await play(script, client, session_id=session_id, played=played, turns=args.turns)
        finally:
            stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
            report, transcript = export(
                script,
                session_id=session_id,
                base_url=base_url,
                played=played,
                out=Path(args.out),
                stamp=stamp,
            )
            fail_safes = sum(1 for turn in played if turn.outcome == "fail_safe")
            print(f"  {len(played)} turns · {fail_safes} fail-safe · session {session_id}")
            print(f"  {report}\n  {transcript}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--script", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--turns", type=int, default=None)
    parser.add_argument("--access-code", default=os.environ.get("ACCESS_CODE", ""))
    try:
        return asyncio.run(run(parser.parse_args()))
    except httpx.HTTPStatusError as refused:
        print(f"golden: {refused.response.status_code} {refused.response.text}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

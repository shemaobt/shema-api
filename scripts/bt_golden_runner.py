"""Play one of her back-translation golden scripts against a room, and judge it with her checks.

The script is hers (`golden/bt/<name>.json` in Tripod-Internalization), read verbatim and never
forked: a fake draft of clips with durations, and rounds of frases told back over
it. Her own runner calls `runBtCheck` in process and speaks no HTTP, so this is the half that
did not exist — the base URL is the only thing that says which stack is being judged.

    ACCESS_CODE=<key> uv run python scripts/bt_golden_runner.py \\
        --base-url http://localhost:8000/api/internalization-room/text-seam/back-translation/ \\
        --script /tmp/P02-causa-a-mais.json \\
        --out golden/reports/2026-09-11

`--out` is a directory; the convention is `golden/reports/<date>/`, as the Guide-turn runner
writes. Two files land in it: `<name>.<stamp>.json`, one entry per round with the findings, the
voice, the outcome and the checks that failed; and `<name>.<stamp>.transcript.txt`, the same
round by round for a person to read beside one of her `.golden/bt-<name>.md` reports.

The exit code is the gate: 1 when any check failed in any round, 2 when the room refused the
request, 0 when her bar was met. Each run costs real model calls — hers came to roughly
US$ 6-7 for five rounds — so it is never part of the test suite.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from scripts.bt_golden_checks import check_round


@dataclass
class Clip:
    key: str
    durationMs: int


@dataclass
class Round:
    frases: list[dict[str, Any]]
    expect: dict[str, Any]


@dataclass
class Script:
    name: str
    pericopeId: str
    language: str
    clips: list[Clip]
    rounds: list[Round]
    why: str = ""


@dataclass
class Played:
    idx: int
    frases: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    spoken: str
    outcome: str
    conferida: bool
    missingWithoutFrase: int
    checks: list[str]
    roundMs: int = 0
    usage: list[dict[str, Any]] = field(default_factory=list)


def load_script(path: Path) -> Script:
    """Her JSON as it is: every key read, none renamed, none defaulted away."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Script(
        name=raw["name"],
        pericopeId=raw["pericopeId"],
        language=raw["language"],
        why=raw.get("why", ""),
        clips=[Clip(key=one["key"], durationMs=one["durationMs"]) for one in raw["draft"]["clips"]],
        rounds=[Round(frases=one["frases"], expect=one["expect"]) for one in raw["rounds"]],
    )


async def open_session(script: Script, client: httpx.AsyncClient) -> str:
    declared = await client.post(
        "session",
        json={
            "pericopeId": script.pericopeId,
            "language": script.language,
            "clips": [asdict(clip) for clip in script.clips],
        },
    )
    declared.raise_for_status()
    return str(declared.json()["sessionId"])


async def play(
    script: Script, client: httpx.AsyncClient, *, session_id: str, played: list[Played]
) -> None:
    """Play each round, judging and appending it as it lands.

    Appended as it lands and not returned at the end, so a round that fails still leaves the
    rounds before it — and what they cost — in the caller's hands.
    """
    for idx, round_ in enumerate(script.rounds):
        started = time.monotonic()
        answered = await client.post(
            "round", json={"sessionId": session_id, "frases": round_.frases}
        )
        answered.raise_for_status()
        reply = answered.json()
        checks = check_round(reply, round_.expect)
        played.append(
            Played(
                idx=idx,
                frases=round_.frases,
                findings=reply["findings"],
                spoken=reply["spoken"],
                outcome=reply["outcome"],
                conferida=reply["conferida"],
                missingWithoutFrase=reply["missingWithoutFrase"],
                checks=checks,
                roundMs=int(reply.get("roundMs") or round((time.monotonic() - started) * 1000)),
                usage=list(reply.get("usage") or []),
            )
        )
        _announce(played[-1])


def _announce(line: Played) -> None:
    print(
        f"  [round {line.idx + 1}] {line.outcome:<9} {line.roundMs}ms  "
        f"findings={len(line.findings)} conferida={line.conferida}"
    )
    for finding in line.findings:
        frase = "" if finding.get("frase") is None else f" (frase {finding['frase']})"
        print(f"      · {finding['kind']}{frase}: {finding['note']}")
    print(f"      voice: {' '.join(line.spoken.split())}")
    for failed in line.checks:
        print(f"      ✗ {failed}")


def transcript_of(script: Script, played: list[Played]) -> str:
    """The rounds as a person reads them, beside one of her own markdown reports."""
    blocks: list[str] = [f"# Golden bt — {script.name}", ""]
    if script.why:
        blocks += [f"> {script.why}", ""]
    for line in played:
        told = "\n".join(
            f"{number}. [{frase['clipKey']}] {frase['text']}"
            for number, frase in enumerate(line.frases, start=1)
        )
        found = (
            "\n".join(
                f"- {one['kind']}"
                + ("" if one.get("frase") is None else f" · frase {one['frase']}")
                + f" — {one['note']}"
                for one in line.findings
            )
            or "- none"
        )
        checked = "\n".join(f"- ✗ {failed}" for failed in line.checks) or "- all passed"
        blocks += [
            f"## Round {line.idx + 1}",
            "",
            "### The telling (as it was sent)",
            "",
            told,
            "",
            "### Findings",
            "",
            found,
            "",
            f"### Voice ({line.outcome}, conferida={line.conferida})",
            "",
            line.spoken,
            "",
            "### Checks",
            "",
            checked,
            "",
        ]
    return "\n".join(blocks)


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
                "rounds": [asdict(line) for line in played],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    transcript.write_text(transcript_of(script, played) + "\n", encoding="utf-8")
    return report, transcript


async def run(args: argparse.Namespace) -> int:
    """Play her script through one room and answer with what a CI should do about it.

    The one catch in this file, and it is the boundary: the room refusing is not her bar
    failing, and the rounds already paid for in model calls have to reach the report before
    that becomes an exit code.
    """
    script = load_script(Path(args.script))
    base_url = args.base_url.rstrip("/") + "/"
    headers = {"X-Access-Code": args.access_code} if args.access_code else {}
    print(f"▶ {script.name} ({script.pericopeId}, {script.language}) → {base_url}")
    played: list[Played] = []
    refused: httpx.HTTPStatusError | None = None
    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=600) as client:
        session_id = await open_session(script, client)
        try:
            await play(script, client, session_id=session_id, played=played)
        except httpx.HTTPStatusError as stopped:
            refused = stopped
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
            failed = sum(len(line.checks) for line in played)
            verdict = "STOPPED" if refused is not None else ("FAIL" if failed else "PASS")
            print(f"  {verdict} · {failed} check(s) failed · {session_id}")
            print(f"  {report}\n  {transcript}")
    if refused is not None:
        return _refused(refused)
    return 1 if failed else 0


def _refused(stopped: httpx.HTTPStatusError) -> int:
    """The room turned the runner away: not a script that failed her bar, and not the same code."""
    print(f"bt golden: {stopped.response.status_code} {stopped.response.text}", file=sys.stderr)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--script", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--access-code", default=os.environ.get("ACCESS_CODE", ""))
    try:
        return asyncio.run(run(parser.parse_args()))
    except httpx.HTTPStatusError as refused:
        return _refused(refused)


if __name__ == "__main__":
    raise SystemExit(main())

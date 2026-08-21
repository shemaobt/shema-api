"""Render the room's pre-approved lines to audio the app ships with it.

A fail-safe is the sentence the team hears when the model failed or the network did. Paying
ElevenLabs for it at that moment is the worst possible time to need a network call, so these
lines are synthesized once, here, and travel inside the app.

    uv run python scripts/render_fixed_voice_lines.py           # render what is missing
    uv run python scripts/render_fixed_voice_lines.py --check   # fail if the text drifted

`--check` is the guard against silent freezing: edit a line in the authored prompt and the
manifest no longer matches, so the suite refuses until someone renders it again.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services.internalization_room.fail_safe import FailSafe, utterances
from app.services.internalization_room.synthesize_facilitator_speech import (
    synthesize_facilitator_speech,
)

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "internalization-room/assets/audio/fixed"
MANIFEST = "manifest.json"


def catalogue(language_code: str) -> dict[str, str]:
    """Every pre-approved line, by the name the app plays it under."""
    lines: dict[str, str] = {}
    for kind in FailSafe:
        for index, text in enumerate(utterances(kind, language_code)):
            lines[f"{kind}{index}"] = text
    return lines


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def read_manifest(out: Path) -> dict[str, str]:
    path = out / MANIFEST
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def drift(out: Path, language_code: str) -> list[str]:
    recorded = read_manifest(out)
    complaints = []
    for name, text in catalogue(language_code).items():
        if name not in recorded:
            complaints.append(f"{name}: never rendered")
        elif recorded[name] != fingerprint(text):
            complaints.append(f"{name}: text changed since it was rendered")
        elif not (out / f"{name}.mp3").exists():
            complaints.append(f"{name}: manifest lists it but the audio is missing")
    for name in recorded.keys() - catalogue(language_code).keys():
        complaints.append(f"{name}: rendered but no longer in the prompt")
    return complaints


async def render(out: Path, language_code: str, *, force: bool) -> None:
    out.mkdir(parents=True, exist_ok=True)
    manifest = {} if force else read_manifest(out)
    for name, text in catalogue(language_code).items():
        clip = out / f"{name}.mp3"
        if not force and clip.exists() and manifest.get(name) == fingerprint(text):
            print(f"  = {name}")
            continue
        speech, _ = await synthesize_facilitator_speech(text)
        clip.write_bytes(speech.audio)
        manifest[name] = fingerprint(text)
        print(f"  + {name}  {len(speech.audio) // 1024} KB  {text[:56]}")
    (out / MANIFEST).write_text(
        json.dumps(dict(sorted(manifest.items())), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift, render nothing")
    parser.add_argument("--force", action="store_true", help="re-render every line")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    language = get_settings().internalization_room_language_code.split("-")[0]

    if args.check:
        complaints = drift(args.out, language)
        for complaint in complaints:
            print(f"drift: {complaint}")
        print("fixed lines match the prompt" if not complaints else "run without --check")
        return 1 if complaints else 0

    asyncio.run(render(args.out, language, force=args.force))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

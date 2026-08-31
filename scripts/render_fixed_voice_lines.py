"""Render the room's pre-approved lines to audio the app ships with it.

A fail-safe is the sentence the team hears when the model failed or the network did. Paying
ElevenLabs for it at that moment is the worst possible time to need a network call, so these
lines are synthesized once, here, and travel inside the app.

    uv run python scripts/render_fixed_voice_lines.py                    # what is missing
    uv run python scripts/render_fixed_voice_lines.py --check            # did the text drift
    uv run python scripts/render_fixed_voice_lines.py --language pt      # one language only

`--check` is the guard against silent freezing: edit a line in the authored prompt and the
manifest no longer matches, so the suite refuses until someone renders it again. It covers
every language the room claims, because a line edited in one of them is as frozen as a line
edited in any other.

One bundle per language, each rendered in that language's own voice. A team never hears two
languages in one session, so a language whose lines are unwritten is not filled in from
another one here — it is the claim in `ROOM_LANGUAGES` that has to wait.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.internalization_room.fail_safe import FailSafe, utterances
from app.services.internalization_room.languages import ROOM_LANGUAGES
from app.services.internalization_room.synthesize_facilitator_speech import (
    synthesize_facilitator_speech,
)

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "internalization-room/assets/audio"
MANIFEST = "manifest.json"

#: Lines the app plays outside a turn: they are not fail-safes and do not live in the prompt,
#: but they must be in the bundle, because the room says them before it can do anything at all.
#:
#: `sem_conexao` and `toque_para_comecar` ship beside them and are deliberately absent here.
#: Their audio was rendered before this script existed and their wording was never written
#: down, so declaring a guess would make the next render overwrite approved audio with it.
#:
#: A language with none written renders none, rather than borrowing another language's words.
STANDALONE: dict[str, dict[str, str]] = {
    "pt": {
        "gravacao_presa": (
            "Tem uma gravação de vocês que eu ainda não consegui guardar. "
            "Ela não se perdeu, está aqui comigo. "
            "Peçam a alguém para dar uma olhada quando puder."
        ),
        "microfone": (
            "Eu preciso ouvir vocês para trabalhar, e o microfone está desligado para mim. "
            "Peçam a alguém para liberar o microfone nos ajustes do aparelho. "
            "Enquanto isso eu não consigo continuar."
        ),
    },
    "en": {
        "gravacao_presa": (
            "There is a recording of yours I have not been able to store yet. "
            "It is not lost, it is here with me. "
            "Ask someone to take a look when they can."
        ),
        "microfone": (
            "I need to hear you to work, and the microphone is switched off for me. "
            "Ask someone to allow the microphone in this tablet's settings. "
            "Until then I cannot carry on."
        ),
    },
}

#: The one family that is spoken and never shipped. The supplement says so of it in bold —
#: *"This one is spoken, not shipped."* — and the app names no H line, so rendering it would
#: put a clip in the bundle that nothing plays and hold `--check` red forever.
NEVER_SHIPPED = frozenset({FailSafe.UNTOLD_STRETCH})


def catalogue(language_code: str) -> dict[str, str]:
    """Every pre-approved line the app ships, by the name it plays it under."""
    lines: dict[str, str] = {}
    for kind in FailSafe:
        if kind in NEVER_SHIPPED:
            continue
        for index, text in enumerate(utterances(kind, language_code)):
            lines[f"{kind}{index}"] = text
    lines.update(STANDALONE.get(language_code, {}))
    return lines


class _NoCache:
    """Synthesis for a build, not for a room.

    The room's synthesis writes through the platform bucket so a line is paid for once
    across every replica. A script that renders files into the app has no business needing
    production storage — and would fail on any machine without the bucket configured.
    """

    async def get(self, key: str) -> bytes | None:
        return None

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        return None


def _bundle(out: Path, language_code: str) -> Path:
    """Where one language's bundle lives.

    The language is the top of the path rather than a suffix on the fixed folder, because the
    standalone lines need it too — the very first thing the room ever says is one of them.
    """
    return out / language_code


def _clip_path(out: Path, language_code: str, name: str) -> Path:
    """Standalone lines sit beside the fixed folder, where the app already looks for them."""
    bundle = _bundle(out, language_code)
    if name in STANDALONE.get(language_code, {}):
        return bundle / f"{name}.mp3"
    return bundle / "fixed" / f"{name}.mp3"


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def read_manifest(out: Path, language_code: str) -> dict[str, str]:
    path = _bundle(out, language_code) / MANIFEST
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def drift(out: Path, language_code: str) -> list[str]:
    recorded = read_manifest(out, language_code)
    lines = catalogue(language_code)
    complaints = []
    for name, text in lines.items():
        if name not in recorded:
            complaints.append(f"{language_code}/{name}: never rendered")
        elif recorded[name] != fingerprint(text):
            complaints.append(f"{language_code}/{name}: text changed since it was rendered")
        elif not _clip_path(out, language_code, name).exists():
            complaints.append(f"{language_code}/{name}: manifest lists it but the audio is missing")
    for name in recorded.keys() - lines.keys():
        complaints.append(f"{language_code}/{name}: rendered but no longer in the prompt")
    return complaints


async def render(out: Path, language_code: str, *, force: bool) -> None:
    bundle = _bundle(out, language_code)
    (bundle / "fixed").mkdir(parents=True, exist_ok=True)
    manifest = {} if force else read_manifest(out, language_code)
    for name, text in catalogue(language_code).items():
        clip = _clip_path(out, language_code, name)
        if not force and clip.exists() and manifest.get(name) == fingerprint(text):
            print(f"  = {language_code}/{name}")
            continue
        speech, _ = await synthesize_facilitator_speech(
            text, language=language_code, store=_NoCache()
        )
        clip.write_bytes(speech.audio)
        manifest[name] = fingerprint(text)
        print(f"  + {language_code}/{name}  {len(speech.audio) // 1024} KB  {text[:48]}")
    (bundle / MANIFEST).write_text(
        json.dumps(dict(sorted(manifest.items())), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift, render nothing")
    parser.add_argument("--force", action="store_true", help="re-render every line")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--language",
        default=",".join(ROOM_LANGUAGES),
        help="comma-separated; defaults to every language the room claims",
    )
    args = parser.parse_args()

    spoken = [tag.strip() for tag in args.language.split(",") if tag.strip()]
    unknown = [tag for tag in spoken if tag not in ROOM_LANGUAGES]
    if unknown:
        print(f"the room does not claim to speak {unknown}")
        return 1

    if args.check:
        complaints = [c for language in spoken for c in drift(args.out, language)]
        for complaint in complaints:
            print(f"drift: {complaint}")
        print("fixed lines match the prompt" if not complaints else "run without --check")
        return 1 if complaints else 0

    for language in spoken:
        asyncio.run(render(args.out, language, force=args.force))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

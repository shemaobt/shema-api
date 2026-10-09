"""Render the notices the app speaks before it can reach the room, to audio it ships with it.

Her fixed and process lines no longer travel inside the app: the room voices each one from
the text it was deployed with (`GET /fixed-lines/{line}`), so a line she re-rules is heard on
the next load. What stays in the bundle are the three notices the room has to say when it
cannot reach the server at all, and those are rendered here.

Every run is told where the app's bundle is; there is nothing here that could know it.

    OUT=<app checkout>/assets/audio
    uv run python scripts/render_fixed_voice_lines.py --out "$OUT"              # what is missing
    uv run python scripts/render_fixed_voice_lines.py --out "$OUT" --check      # did it drift
    uv run python scripts/render_fixed_voice_lines.py --out "$OUT" --language pt

`--check` is the guard against silent freezing: edit a notice, or change the voice or the model
it is rendered with, and the manifest no longer matches, so it reports the drift and exits
non-zero until someone renders it again. It covers every language the room claims.
Re-rendering is a person's job: nothing in the suite does it, and nothing in the suite reads
the bundle.

A run also writes the app's `clip_hashes.json` beside each language's manifest, or under
`--clip-hashes DIR/<language>/`: the sha256 of every mp3 in the folder, with the ones the manifest
does not vouch for as current listed as `unrendered`: a line that failed, or a clip approved by
hand like `sem_conexao.mp3`, but not a line skipped because it was already up to date.
A run that cannot name the api commit renders nothing.

One bundle per language, each rendered in that language's own voice. A team never hears two
languages in one session, so a language whose notices are unwritten is not filled in from
another one here — it is the claim in `ROOM_LANGUAGES` that has to wait.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
from contextlib import aclosing
from datetime import UTC, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services.internalization_room.languages import ROOM_LANGUAGES
from app.services.internalization_room.synthesize_facilitator_speech import (
    render_facilitator_speech,
)
from app.services.internalization_room.voices import voice_for
from app.services.platform import tts

MANIFEST = "manifest.json"
CLIP_HASHES = "clip_hashes.json"

#: Lines the app plays outside a turn: they are not fail-safes and do not live in the prompt,
#: but they must be in the bundle, because the room says them before it can do anything at all.
#:
#: `sem_conexao` is absent from Portuguese and only from Portuguese. Its Portuguese audio was
#: rendered before this script existed and its wording was never written down, so declaring a
#: guess here would make the next render overwrite approved audio with it. The other languages
#: have no approved audio to overwrite, so theirs is written here like any other line — a room
#: that cannot say it has no connection is a room that opens in silence.
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
        "sem_conexao": (
            "I cannot reach the room right now. "
            "It is not anything you did — we just have no connection. "
            "We can wait a moment and try again."
        ),
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


def catalogue(language_code: str) -> dict[str, str]:
    return dict(STANDALONE.get(language_code, {}))


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
    return _bundle(out, language_code) / f"{name}.mp3"


def _voice_of(language_code: str) -> str:
    return voice_for(language_code, settings=get_settings())


def fingerprint(text: str, *, language_code: str) -> str:
    """What a rendered line was made from: its words, the voice that said them and the model."""
    made_of = "\n".join(
        (text, _voice_of(language_code), get_settings().internalization_room_tts_model)
    )
    return hashlib.sha256(made_of.encode("utf-8")).hexdigest()[:16]


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
        elif recorded[name] != fingerprint(text, language_code=language_code):
            complaints.append(
                f"{language_code}/{name}: text, voice or model changed since it was rendered"
            )
        elif not _clip_path(out, language_code, name).exists():
            complaints.append(f"{language_code}/{name}: manifest lists it but the audio is missing")
    for name in recorded.keys() - lines.keys():
        complaints.append(f"{language_code}/{name}: rendered but no longer in the prompt")
    return complaints


def _api_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _write_clip_hashes(
    bundle: Path,
    language_code: str,
    manifest: dict[str, str],
    *,
    api_commit: str,
    into: Path,
) -> None:
    current = {
        f"{name}.mp3"
        for name, text in catalogue(language_code).items()
        if manifest.get(name) == fingerprint(text, language_code=language_code)
    }
    clips = {
        clip.name: hashlib.sha256(clip.read_bytes()).hexdigest()
        for clip in sorted(bundle.glob("*.mp3"))
    }
    hashes = {
        "api_commit": api_commit,
        "clips": clips,
        "rendered_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "unrendered": sorted(clips.keys() - current),
        "voice_id": _voice_of(language_code),
    }
    into.mkdir(parents=True, exist_ok=True)
    (into / CLIP_HASHES).write_text(
        json.dumps(hashes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


async def render(
    out: Path,
    language_code: str,
    *,
    force: bool,
    api_commit: str,
    client: httpx.AsyncClient | None = None,
    clip_hashes: Path | None = None,
) -> None:
    bundle = _bundle(out, language_code)
    bundle.mkdir(parents=True, exist_ok=True)
    manifest = {} if force else read_manifest(out, language_code)
    try:
        for name, text in catalogue(language_code).items():
            clip = _clip_path(out, language_code, name)
            made_of = fingerprint(text, language_code=language_code)
            if not force and clip.exists() and manifest.get(name) == made_of:
                print(f"  = {language_code}/{name}")
                continue
            manifest.pop(name, None)
            speech = await render_facilitator_speech(
                text, language=language_code, store=_NoCache(), client=client
            )
            clip.write_bytes(speech.audio)
            manifest[name] = made_of
            print(f"  + {language_code}/{name}  {len(speech.audio) // 1024} KB  {text[:48]}")
    finally:
        (bundle / MANIFEST).write_text(
            json.dumps(dict(sorted(manifest.items())), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        hashes_into = bundle if clip_hashes is None else clip_hashes / language_code
        _write_clip_hashes(bundle, language_code, manifest, api_commit=api_commit, into=hashes_into)


async def render_all(
    out: Path, languages: list[str], *, force: bool, clip_hashes: Path | None
) -> None:
    api_commit = _api_commit()
    async with aclosing(tts._make_client()) as client:
        for language_code in languages:
            await render(
                out,
                language_code,
                force=force,
                api_commit=api_commit,
                client=client,
                clip_hashes=clip_hashes,
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift, render nothing")
    parser.add_argument("--force", action="store_true", help="re-render every line")
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="the audio folder of the app checkout the bundle ships in",
    )
    parser.add_argument(
        "--clip-hashes",
        type=Path,
        help="where each language's clip_hashes.json goes, as DIR/<language>/; "
        "defaults to beside its manifest",
    )
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

    asyncio.run(render_all(args.out, spoken, force=args.force, clip_hashes=args.clip_hashes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

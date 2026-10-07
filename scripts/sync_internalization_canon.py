"""Vendor the internalization canon at a pinned commit, or check it for drift.

The room reads canon only from the vendored directory — never over the network at request
time, and never writing back. Canon changes through the project's own governed process; this
script is the one door, and it is deliberate.

What is vendored is worked out from the pin: a book is a candidate when `_spec/pins.json` lists
its aliases list, a passage counts when its map, its Meaning Coordinates and its Compilation Log
all exist at the pin, and a book is published when it is a candidate with a whole passage and
its aliases list is in `_spec/registry/`. Only the published books named in `SERVED_BOOKS`
reach the copy. Whatever is left out — an incomplete passage, a book without its names list, a
book that is not served — is named on stderr, never dropped silently.

`--sync` overwrites the vendored directory wholesale — including deleting every locally
vendored file that is not in that published-and-served set, whether it left her repo, belongs
to a passage that is no longer whole, or sits in a book outside `SERVED_BOOKS` — so nothing of
ours may live inside it. The facilitator-facing element labels are the case that already
exists: they sit in `canon/element-labels/`, a sibling of `canon/vendor/`, precisely so a
re-pin cannot delete them without a word.

`--sync` refuses, exits 1 and writes nothing when the pin it was given is not on the
compiler's main line, and when the pin leaves no consumable passage at all.

    uv run python scripts/sync_internalization_canon.py --check      # drift/extra, exits 1
    uv run python scripts/sync_internalization_canon.py --sync       # re-pin to current main
    uv run python scripts/sync_internalization_canon.py --sync --pin <sha>   # re-pin to <sha>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from app.core.served_books import SERVED_BOOKS

SHA_RE = re.compile(r"[0-9a-f]{40}")

REPO = "MarciaSuzuki/tripod_compiler"
VENDOR = Path(__file__).resolve().parents[1] / ("app/services/internalization_room/canon/vendor")
PIN_FILE = VENDOR / "VENDOR_PIN"
KINDS = {
    "meaning-map": "fixtures/meaning-map",
    "meaning-coordinates": "fixtures/meaning-coordinates",
    "compilation-log": "fixtures/compilation-log",
    "registry": "_spec/registry",
}
ALIASES_KEY = re.compile(r"registry/(\w+)\.aliases\.json")
PASSAGE_SUFFIX = {
    "meaning-map": ".md",
    "meaning-coordinates": "-MEANING-COORDINATES.md",
    "compilation-log": "-COMPILATION-LOG.md",
}


def _get(url: str) -> bytes:
    headers = {}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def _head_sha() -> str:
    payload = json.loads(_get(f"https://api.github.com/repos/{REPO}/commits/main"))
    return payload["sha"]


def _on_main_line(sha: str) -> bool:
    url = f"https://api.github.com/repos/{REPO}/compare/{sha}...main"
    try:
        status = json.loads(_get(url))["status"]
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        return False
    return status in ("identical", "ahead")


def _listing(kind: str, sha: str) -> list[str]:
    url = f"https://api.github.com/repos/{REPO}/contents/{KINDS[kind]}?ref={sha}"
    return sorted(entry["name"] for entry in json.loads(_get(url)))


def _listed_books(sha: str) -> set[str]:
    url = f"https://raw.githubusercontent.com/{REPO}/{sha}/_spec/pins.json"
    sources = json.loads(_get(url))["sources"]
    return {found[1] for key in sources if (found := ALIASES_KEY.fullmatch(key))}


def _published(sha: str) -> tuple[dict[str, list[str]], list[str]]:
    listed = {kind: _listing(kind, sha) for kind in KINDS}
    listed_books = _listed_books(sha)
    stems = {
        kind: {name.removesuffix(suffix): name for name in listed[kind]}
        for kind, suffix in PASSAGE_SUFFIX.items()
    }
    complete: dict[str, list[str]] = {}
    skipped: list[str] = []
    for stem in sorted(set().union(*stems.values())):
        missing = [kind for kind in PASSAGE_SUFFIX if stem not in stems[kind]]
        if missing:
            skipped.append(f"skipped {stem}: missing {', '.join(missing)}")
            continue
        complete.setdefault(stem.split("-")[1], []).append(stem)
    published: dict[str, list[str]] = {kind: [] for kind in KINDS}
    for book, book_stems in complete.items():
        if book not in SERVED_BOOKS:
            skipped.append(f"skipped book {book}: not served in this release")
            continue
        if book.lower() not in listed_books:
            skipped.append(
                f"skipped book {book}: its aliases list is not listed by the compiler at the pin"
            )
            continue
        if f"{book.lower()}.aliases.json" not in listed["registry"]:
            skipped.append(
                f"skipped book {book}: its aliases list is not in the registry at the pin"
            )
            continue
        for stem in book_stems:
            for kind in PASSAGE_SUFFIX:
                published[kind].append(stems[kind][stem])
        published["registry"].append(f"{book.lower()}.aliases.json")
    return published, skipped


def _raw(kind: str, sha: str, name: str) -> bytes:
    return _get(f"https://raw.githubusercontent.com/{REPO}/{sha}/{KINDS[kind]}/{name}")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def sync(pin: str | None = None) -> int:
    if pin and not _on_main_line(pin):
        print(
            f"pin {pin} is not on the compiler's main line — "
            "refusing to vendor an unpublished commit",
            file=sys.stderr,
        )
        return 1
    sha = pin if pin else _head_sha()
    published, skipped = _published(sha)
    for line in skipped:
        print(line, file=sys.stderr)
    if not published["meaning-map"]:
        print(f"nothing consumable at pin {sha} — refusing to empty the canon", file=sys.stderr)
        return 1
    for kind in KINDS:
        target = VENDOR / kind
        target.mkdir(parents=True, exist_ok=True)
        names = published[kind]
        for name in names:
            (target / name).write_bytes(_raw(kind, sha, name))
            print(f"  {kind}/{name}")
        for existing in sorted(p.name for p in target.iterdir() if p.is_file()):
            if existing not in names:
                (target / existing).unlink()
                print(f"  removed {kind}/{existing}")
    PIN_FILE.write_text(sha + "\n")
    print(f"pinned at {sha}")
    return 0


def check() -> int:
    if not PIN_FILE.exists():
        print("no VENDOR_PIN — run with --sync", file=sys.stderr)
        return 1
    sha = PIN_FILE.read_text().strip()
    drifted: list[str] = []
    published, _ = _published(sha)
    for kind in KINDS:
        names = published[kind]
        for name in names:
            local = VENDOR / kind / name
            upstream = _raw(kind, sha, name)
            if not local.exists():
                drifted.append(f"missing: {kind}/{name}")
            elif _digest(local.read_bytes()) != _digest(upstream):
                drifted.append(f"changed: {kind}/{name}")

        target = VENDOR / kind
        if target.is_dir():
            for existing in sorted(p.name for p in target.iterdir() if p.is_file()):
                if existing not in names:
                    drifted.append(f"extra: {kind}/{existing}")

    if drifted:
        print(f"canon drifted from pin {sha}:", file=sys.stderr)
        for line in drifted:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(f"canon matches pin {sha}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sync", action="store_true")
    group.add_argument("--check", action="store_true")
    parser.add_argument("--pin", metavar="<sha>")
    args = parser.parse_args()
    if args.pin and not args.sync:
        parser.error("--pin needs --sync")
    if args.pin and not SHA_RE.fullmatch(args.pin):
        parser.error("--pin needs a full 40-character sha, not a ref")
    return sync(pin=args.pin) if args.sync else check()


if __name__ == "__main__":
    raise SystemExit(main())

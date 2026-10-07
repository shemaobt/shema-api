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
from datetime import UTC, datetime
from pathlib import Path

from app.core.canon_pin import pinned_commit
from app.core.served_books import SERVED_BOOKS

SHA_RE = re.compile(r"[0-9a-f]{40}")

REPO = "MarciaSuzuki/tripod_compiler"
VENDOR = Path(__file__).resolve().parents[1] / ("app/services/internalization_room/canon/vendor")
PIN_FILE = VENDOR / "VENDOR_PIN"
MANIFEST = "VENDOR_MANIFEST.json"
PROVENANCE = "registry/PROVENANCE.md"
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


def _committed(sha: str) -> str:
    payload = json.loads(_get(f"https://api.github.com/repos/{REPO}/commits/{sha}"))
    return payload["commit"]["committer"]["date"][:10]


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
    return hashlib.sha256(data).hexdigest()


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
    files = []
    for kind in KINDS:
        target = VENDOR / kind
        target.mkdir(parents=True, exist_ok=True)
        names = published[kind]
        for name in names:
            data = _raw(kind, sha, name)
            (target / name).write_bytes(data)
            files.append({"path": f"{kind}/{name}", "sha256": _digest(data)})
            print(f"  {kind}/{name}")
        for existing in sorted(p.name for p in target.iterdir() if p.is_file()):
            if existing not in names:
                (target / existing).unlink()
                print(f"  removed {kind}/{existing}")
    record = {
        "pin_commit": sha,
        "books": sorted(name.removesuffix(".aliases.json") for name in published["registry"]),
        "passages": sorted(name.split("-")[0] for name in published["meaning-map"]),
        "files": files,
    }
    (VENDOR / MANIFEST).write_text(json.dumps(record, indent=2) + "\n")
    PIN_FILE.write_text(_pin_record(sha, published["meaning-map"]))
    print(f"pinned at {sha}")
    return 0


def _pin_record(sha: str, maps: list[str]) -> str:
    ids: dict[str, list[str]] = {}
    for name in sorted(maps):
        ids.setdefault(name.split("-")[1], []).append(name.split("-")[0])
    books = " + ".join(f"{book} ({found[0]}-{found[-1]})" for book, found in sorted(ids.items()))
    fields = {
        "source_repo": REPO,
        "pin_commit": sha,
        "pin_ref": "main",
        "pin_committed": _committed(sha),
        "vendored_on": datetime.now(UTC).date().isoformat(),
        "published_books": f"{books} = {len(maps)} pericopes",
    }
    return "".join(f"{key + ':':<18}{value}\n" for key, value in fields.items())


def _held() -> dict[str, bytes]:
    return {
        f"{kind}/{path.name}": path.read_bytes()
        for kind in KINDS
        if (VENDOR / kind).is_dir()
        for path in sorted((VENDOR / kind).iterdir())
        if path.is_file() and f"{kind}/{path.name}" != PROVENANCE
    }


def _drift(expected: dict[str, str], held: dict[str, bytes]) -> list[str]:
    drifted = []
    for path, sha256 in expected.items():
        if path not in held:
            drifted.append(f"missing: {path}")
        elif _digest(held[path]) != sha256:
            drifted.append(f"changed: {path}")
    drifted.extend(f"extra: {path}" for path in held if path not in expected)
    return drifted


def check() -> int:
    if not PIN_FILE.exists():
        print("no VENDOR_PIN — run with --sync", file=sys.stderr)
        return 1
    sha = pinned_commit(PIN_FILE.read_text())
    manifest = VENDOR / MANIFEST
    if manifest.exists():
        files = json.loads(manifest.read_text())["files"]
        drifted = _drift({file["path"]: file["sha256"] for file in files}, _held())
    else:
        drifted = [f"missing: {MANIFEST}"]
    if drifted:
        print(f"canon drifted from pin {sha}:", file=sys.stderr)
        for line in drifted:
            print(f"  {line}", file=sys.stderr)
        print(
            f"Re-vendor with `uv run python scripts/sync_internalization_canon.py --sync --pin "
            f"{sha}` — never edit vendored files (or the manifest) by hand.",
            file=sys.stderr,
        )
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

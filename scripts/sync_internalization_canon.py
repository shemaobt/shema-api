"""Vendor the internalization canon at a pinned commit, or check it for drift.

The room reads canon only from the vendored directory — never over the network at request
time, and never writing back. Canon changes through the project's own governed process; this
script is the one door, and it is deliberate.

`--sync` overwrites the vendored directory wholesale — including deleting a locally vendored
file whose name the upstream listing no longer has — so nothing of ours may live inside it.
The facilitator-facing element labels are the case that already exists: they sit in
`canon/element-labels/`, a sibling of `canon/vendor/`, precisely so a re-pin cannot delete
them without a word.

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
import urllib.request
from pathlib import Path

SHA_RE = re.compile(r"[0-9a-f]{40}")

REPO = "MarciaSuzuki/tripod_compiler"
BOOKS = ("Ruth",)
VENDOR = Path(__file__).resolve().parents[1] / ("app/services/internalization_room/canon/vendor")
PIN_FILE = VENDOR / "VENDOR_PIN"
KINDS = {
    "meaning-map": "fixtures/meaning-map",
    "compilation-log": "fixtures/compilation-log",
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


def _listing(kind: str, sha: str) -> list[str]:
    url = f"https://api.github.com/repos/{REPO}/contents/{KINDS[kind]}?ref={sha}"
    names = [entry["name"] for entry in json.loads(_get(url))]
    return sorted(n for n in names if any(book in n for book in BOOKS))


def _raw(kind: str, sha: str, name: str) -> bytes:
    return _get(f"https://raw.githubusercontent.com/{REPO}/{sha}/{KINDS[kind]}/{name}")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def sync(pin: str | None = None) -> int:
    sha = pin if pin else _head_sha()
    for kind in KINDS:
        target = VENDOR / kind
        target.mkdir(parents=True, exist_ok=True)
        names = _listing(kind, sha)
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
    for kind in KINDS:
        names = _listing(kind, sha)
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

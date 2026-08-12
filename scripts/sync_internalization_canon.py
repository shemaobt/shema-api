"""Vendor the internalization canon at a pinned commit, or check it for drift.

The room reads canon only from the vendored directory — never over the network at request
time, and never writing back. Canon changes through the project's own governed process; this
script is the one door, and it is deliberate.

    uv run python scripts/sync_internalization_canon.py --check   # drift only, exits 1
    uv run python scripts/sync_internalization_canon.py --sync    # re-pin to current main
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

REPO = "MarciaSuzuki/tripod_compiler"
BOOKS = ("Ruth",)
VENDOR = Path(__file__).resolve().parents[1] / ("app/services/internalization_room/canon/vendor")
PIN_FILE = VENDOR / "VENDOR_PIN"
KINDS = {
    "meaning-map": "fixtures/meaning-map",
    "compilation-log": "fixtures/compilation-log",
}


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as response:
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


def sync() -> int:
    sha = _head_sha()
    for kind in KINDS:
        target = VENDOR / kind
        target.mkdir(parents=True, exist_ok=True)
        for name in _listing(kind, sha):
            (target / name).write_bytes(_raw(kind, sha, name))
            print(f"  {kind}/{name}")
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
        for name in _listing(kind, sha):
            local = VENDOR / kind / name
            upstream = _raw(kind, sha, name)
            if not local.exists():
                drifted.append(f"missing: {kind}/{name}")
            elif _digest(local.read_bytes()) != _digest(upstream):
                drifted.append(f"changed: {kind}/{name}")

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
    args = parser.parse_args()
    return sync() if args.sync else check()


if __name__ == "__main__":
    raise SystemExit(main())

"""A compiler repository the canon sync can be pointed at, served through the one network door.

Every file the sync reads lives in a dict keyed by its path at the pin; the directory listings the
contents API would give and the raw bytes are both answered from it, so a test states what the
compiler holds and nothing about how the sync asks for it.
"""

from __future__ import annotations

import json
import re
import urllib.error
from pathlib import Path
from typing import Any

import pytest

REPO = "MarciaSuzuki/tripod_compiler"
SHA = "5b5c8d2b3ae7632279c07017224f861ae369b0d7"

_CONTENTS = re.compile(
    rf"^https://api\.github\.com/repos/{REPO}/contents/(?P<path>.+)\?ref=(?P<sha>\w+)$"
)
_RAW = re.compile(rf"^https://raw\.githubusercontent\.com/{REPO}/(?P<sha>\w+)/(?P<path>.+)$")
_COMPARE = re.compile(rf"^https://api\.github\.com/repos/{REPO}/compare/(?P<sha>\w+)\.\.\.main$")


class Compiler:
    def __init__(self, sha: str = SHA) -> None:
        self.sha = sha
        self.files: dict[str, bytes] = {}
        self.listed: list[str] = []
        self.relation = "identical"
        self.requests: list[str] = []

    def passage(
        self, stem: str, *, coordinates: bool = True, log: bool = True, map: bool = True
    ) -> None:
        if map:
            self.files[f"fixtures/meaning-map/{stem}.md"] = f"map {stem}".encode()
        if coordinates:
            self.files[f"fixtures/meaning-coordinates/{stem}-MEANING-COORDINATES.md"] = (
                f"coordinates {stem}".encode()
            )
        if log:
            self.files[f"fixtures/compilation-log/{stem}-COMPILATION-LOG.md"] = (
                f"log {stem}".encode()
            )

    def book(self, name: str, *, listed: bool = True, aliases: bool = True) -> None:
        if listed:
            self.listed.append(name)
        if aliases:
            self.files[f"_spec/registry/{name}.aliases.json"] = f"aliases {name}".encode()

    def get(self, url: str) -> bytes:
        self.requests.append(url)
        if found := _COMPARE.match(url):
            return json.dumps({"status": self.relation}).encode()
        if found := _CONTENTS.match(url):
            prefix = found["path"].rstrip("/") + "/"
            names = [path[len(prefix) :] for path in self.files if path.startswith(prefix)]
            if not names:
                raise _not_found(url)
            return json.dumps([{"name": name} for name in names if "/" not in name]).encode()
        if found := _RAW.match(url):
            if found["path"] == "_spec/pins.json":
                return json.dumps(self._pins()).encode()
            if found["path"] not in self.files:
                raise _not_found(url)
            return self.files[found["path"]]
        raise _not_found(url)

    def _pins(self) -> dict[str, Any]:
        return {
            "sources": {
                f"registry/{name}.aliases.json": {"version": "aliases-0.1.6", "sha256": "0"}
                for name in self.listed
            }
        }


def _not_found(url: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, 404, "Not Found", None, None)  # type: ignore[arg-type]


def point_the_sync_at(
    monkeypatch: pytest.MonkeyPatch, canon: Any, compiler: Compiler, tmp_path: Path
) -> Path:
    vendor = tmp_path / "vendor"
    monkeypatch.setattr(canon, "VENDOR", vendor)
    monkeypatch.setattr(canon, "PIN_FILE", vendor / "VENDOR_PIN")
    monkeypatch.setattr(canon, "_get", compiler.get)
    return vendor


def what_is_vendored(vendor: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(vendor)): path.read_bytes()
        for path in sorted(vendor.rglob("*"))
        if path.is_file() and path.name != "VENDOR_PIN"
    }

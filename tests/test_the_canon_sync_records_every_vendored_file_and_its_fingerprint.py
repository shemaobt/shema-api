from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at


def test_the_record_beside_the_canon_names_the_pin_the_book_the_passage_and_each_files_fingerprint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.passage("P01-Ruth-1-1-5")
    vendor = point_the_sync_at(monkeypatch, canon, compiler, tmp_path)

    canon.sync(pin=SHA)

    assert json.loads((vendor / "VENDOR_MANIFEST.json").read_text()) == {
        "pin_commit": SHA,
        "books": ["ruth"],
        "passages": ["P01"],
        "files": [
            {
                "path": "meaning-map/P01-Ruth-1-1-5.md",
                "sha256": "13f22c98feabe5a6f7be9035a0322d283c3c9860f597e09b476c6ffbd46df1bf",
            },
            {
                "path": "meaning-coordinates/P01-Ruth-1-1-5-MEANING-COORDINATES.md",
                "sha256": "29df7605e23abae46e842954c17be1ec1a35de0bbfcaf865d9e925ba8f9ed68d",
            },
            {
                "path": "compilation-log/P01-Ruth-1-1-5-COMPILATION-LOG.md",
                "sha256": "7e4b0976355d76d736d8c084d11c39ff44d6958243b7ba05aa3593766676f410",
            },
            {
                "path": "registry/ruth.aliases.json",
                "sha256": "b145c922029922411d97bdc453b58509640f8a5a9d262cf70b536b6b61fc8c01",
            },
        ],
    }

"""The canon a session opened with, kept under its pin until its passage is approved."""

from __future__ import annotations

from pathlib import Path

from app.core.canon_pin import pinned_commit

CANON_DIR = Path(__file__).parent
KEPT_DIR = CANON_DIR / "kept"
DEPLOYED_PIN = CANON_DIR / "vendor" / "VENDOR_PIN"


def deployed_pin() -> str:
    return pinned_commit(DEPLOYED_PIN.read_text(encoding="utf-8"))

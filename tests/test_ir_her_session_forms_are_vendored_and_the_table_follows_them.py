from __future__ import annotations

import json
import re

from app.services.internalization_room.name_check import SESSION_FORMS
from scripts.sync_doctrine import FREEZE_FILE, FROZEN, REPO_ROOT, digest, read_pin

HERS = "src/coverage/sessionForms.ts"
_ENTRY = re.compile(r'(?:"([^"]+)"|([A-Za-z_]\w*))\s*:\s*\[([^\]]*)\]')
_FORM = re.compile(r'"([^"]*)"')
_COMMENT = re.compile(r"//[^\n]*")


def _her_table(source: str) -> dict[str, list[str]]:
    literal = source.split("const FORMS: Record<string, string[]> = {", 1)[1].split("\n};", 1)[0]
    return {
        quoted or bare: _FORM.findall(forms)
        for quoted, bare, forms in _ENTRY.findall(_COMMENT.sub("", literal))
    }


def test_her_session_forms_are_vendored_at_the_freeze_with_their_digest() -> None:
    assert HERS in FROZEN, "as formas dela eram copiadas sem pino, e uma forma nova não avisava"
    vendored = REPO_ROOT / FROZEN[HERS]

    assert read_pin(FREEZE_FILE).digests[FROZEN[HERS]] == digest(vendored.read_bytes())


def test_the_forms_the_room_reads_are_her_table_entry_for_entry() -> None:
    vendored = (REPO_ROOT / FROZEN[HERS]).read_text(encoding="utf-8")

    assert json.loads(SESSION_FORMS.read_text(encoding="utf-8")) == _her_table(vendored), (
        "a tabela de formas da sala se afastava da dela e um nome deixava de contar sem aviso"
    )

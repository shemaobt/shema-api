"""No feature may name a Gemini model in its own source.

All nine were literals, and all nine named a preview. A preview is withdrawn without
notice, and with no alerting in front of them the first sign would have been Translation
Helper, Project Health, the Internalization Room, Sound Necklace and i18n failing at the
same moment — with the remedy being a nine-file edit and a deploy, under exactly the
pressure that makes that go wrong.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import Settings
from app.services.i18n.back_translate_content import back_translation_model
from app.services.i18n.translate_content import translation_model as i18n_translation_model
from app.services.internalization_room.llm import room_model
from app.services.platform.disfluency import disfluency_model
from app.services.platform.translation import translation_model
from app.services.project_health.agents.llm_client import fast_model, quality_model
from app.services.translation_helper.send_message import chat_model, title_model

APP = Path(__file__).resolve().parent.parent / "app"

#: A bare Gemini model id. `config.py` is where they are allowed to appear.
_MODEL_ID = re.compile(r'"gemini-[\w.\-]+"')


def test_no_module_outside_config_names_a_gemini_model() -> None:
    offenders = {
        str(path.relative_to(APP)): _MODEL_ID.findall(path.read_text())
        for path in APP.rglob("*.py")
        if path.name != "config.py" and _MODEL_ID.search(path.read_text())
    }
    assert not offenders, (
        f"these modules pin a Gemini model in source: {offenders}. "
        f"Add a Settings field instead, so moving off a withdrawn model is an "
        f"environment variable rather than a deploy."
    )


def test_every_feature_reads_the_model_from_settings() -> None:
    """Each accessor answers with what Settings says, not with what it was written with."""
    settings = Settings(
        database_url="sqlite+aiosqlite:///./test.db",
        gemini_fast_model="model-fast-under-test",
        gemini_quality_model="model-quality-under-test",
    )

    assert fast_model(settings) == "model-fast-under-test"
    assert quality_model(settings) == "model-quality-under-test"
    for accessor in (
        chat_model,
        title_model,
        room_model,
        translation_model,
        disfluency_model,
        i18n_translation_model,
        back_translation_model,
    ):
        assert accessor(settings) == "model-fast-under-test", accessor.__name__

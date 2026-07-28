"""Deterministic filename and storage-key builders.

The export filenames here are a hard contract with the analysis notebooks
(`xeus_layerwise_annotated.py` / `data_loader.py`): Tier A is parsed as
`{word}_{speaker}_{rep}.wav`, Tier B as `pair{NN}_{a|b}_{rep}.wav`, and Tier C
clip ids are matched WITHOUT an extension. Tokens that flow into these names
(`word_label`, `speaker_label`) are validated to contain no separators so the
underscore-split parsing in the guide stays unambiguous.
"""

from __future__ import annotations

import re

from app.core.as_enums import AsAudioFormat, AsPairSide

LABEL_PATTERN = re.compile(r"^[a-z0-9]+$")

# Concrete-noun glyphs from the design Icon set that may serve as picture prompts
# for elicited words (matches the common-noun list in annotation_guide.md).
ALLOWED_EMBLEMS = frozenset(
    {
        "droplet",
        "flame",
        "sun",
        "moon",
        "hand",
        "eye",
        "user",
        "baby",
        "home",
        "tree",
        "bird",
        "fish",
        "paw",
        "cloudRain",
        "wind",
        "mountain",
        "route",
        "bowl",
        "tag",
        "heart",
        "music",
        "waves",
    }
)


def is_valid_label(label: str) -> bool:
    return bool(LABEL_PATTERN.fullmatch(label))


def is_valid_emblem(emblem: str) -> bool:
    return emblem in ALLOWED_EMBLEMS


def tier_a_filename(word_label: str, speaker_label: str, rep_index: int) -> str:
    return f"{word_label}_{speaker_label}_{rep_index:02d}.wav"


def tier_b_filename(pair_number: int, side: AsPairSide | str, rep_index: int) -> str:
    return f"pair{pair_number:02d}_{AsPairSide(side).value}_{rep_index:02d}.wav"


def tier_c_clip_id(clip_number: int) -> str:
    return f"clip_{clip_number:03d}"


def tier_c_filename(clip_number: int) -> str:
    return f"{tier_c_clip_id(clip_number)}.wav"


def raw_object_key(
    language_code: str, tier_dir: str, entity_id: str, fmt: AsAudioFormat | str
) -> str:
    return f"{language_code}/{tier_dir}/raw/{entity_id}.{AsAudioFormat(fmt).value}"


def export_bundle_key(language_code: str, export_id: str) -> str:
    return f"{language_code}/exports/{export_id}.zip"


def result_plot_key(language_code: str, result_id: str, plot_name: str) -> str:
    return f"{language_code}/results/{result_id}/{plot_name}"

from __future__ import annotations

import re

from app.core.exceptions import ValidationError

_PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")


def render(template: str, **values: str) -> str:
    """Fill a prompt's placeholders, refusing to ship one that is still empty.

    A `{{MEANING_MAP}}` that reaches the model as literal text is worse than an error:
    the model would answer anyway, ungrounded, and nothing downstream would notice.
    """
    filled = template
    for name, value in values.items():
        filled = filled.replace(f"{{{{{name}}}}}", value)

    unfilled = sorted(set(_PLACEHOLDER.findall(filled)))
    if unfilled:
        raise ValidationError(f"Prompt placeholders left unfilled: {', '.join(unfilled)}")
    return filled

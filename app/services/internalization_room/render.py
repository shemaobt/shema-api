from __future__ import annotations

import re

from app.core.exceptions import ValidationError

_PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")


def render(template: str, **values: str) -> str:
    """Fill a prompt's placeholders, refusing to ship one that is still empty.

    A `{{MEANING_MAP}}` that reaches the model as literal text is worse than an error:
    the model would answer anyway, ungrounded, and nothing downstream would notice.
    """
    unfilled = sorted({name for name in _PLACEHOLDER.findall(template) if name not in values})
    if unfilled:
        raise ValidationError(f"Prompt placeholders left unfilled: {', '.join(unfilled)}")
    return _PLACEHOLDER.sub(lambda slot: values[slot.group(1)], template)

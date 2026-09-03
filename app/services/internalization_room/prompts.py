from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt


async def get_prompt_text(key: IRPromptKey) -> str:
    """The room's prompt for `key`, read from its committed file."""
    return default_prompt(key)["prompt"]

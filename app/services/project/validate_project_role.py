from app.core.enums import ProjectRole
from app.core.exceptions import ValidationError


def validate_project_role(role: str) -> str:
    """The one gate on what ``project_user_access.role`` may be set to.

    Called from every write path rather than expressed as a database constraint. A CHECK
    would have to be reconciled against whatever production rows already hold, and
    rewriting somebody's data to fit a new enum is not a migration to make blind — so the
    column stays a free String(30) and this is what keeps new writes honest.

    Exact match, no casing or whitespace forgiveness. ``"Facilitator"`` is a different
    string from ``"facilitator"``, the read path compares exactly, and a value that
    silently passed here while failing there would grant nothing and explain nothing.
    """
    if role not in tuple(ProjectRole):
        accepted = ", ".join(sorted(ProjectRole))
        raise ValidationError(f"Invalid project role '{role}'. Accepted roles are: {accepted}")
    return role

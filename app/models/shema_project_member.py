"""Project members on the wire — ``ProjectMember``, ``ProjectRef`` and the one body a write takes.

The spelling is camelCase by alias over the house's snake_case attributes, which is
``app/models/shema_session.py``'s mechanism and for its reason: the Python side stays the
repository's and FastAPI serialises by alias.

**``role`` is ``str`` and not a ``Literal``.** The word is ``_scope.EQUIPE_ROLE`` and the table's
CHECK, and ``tests/test_app_boots.py::test_no_dto_module_reaches_up_into_the_service_layer`` forbids
this package from importing the service layer; a second spelling of the vocabulary here is what
would first disagree the day the client names a second role.

**``addedAt`` is a day,** ``YYYY-MM-DD`` — FE-44 §9.0's rule for every date on the wire, and the UTC
day, as ``IntercessorEntry.addedAt`` and the org chart's ``changedAt`` are. The stored moment keeps
its time for ordering; the roster shows when somebody joined, not at what minute.

**``name`` is the account's display name, else its e-mail** — ``_audit.author_name``, the house's
one rule for naming a person. The roster is a coordination surface and redacts nothing
(OBT-524: *a lista de membros é superfície de coordenação e não redige nada*); no field here is a
place, a base or a project contact, which is why ``test_privacy_owners.py``'s route audit asks
nothing of these shapes.

**``userId`` travels** because it is the key ``DELETE …/members/{userId}`` takes, and the audience
of the roster is only whoever reaches the project.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ProjectMemberCreate(BaseModel):
    """``POST /api/shema/projects/{id}/members`` — the account, and nothing else.

    ``extra="forbid"``: the role is the server's to stamp, so a body naming one is refused rather
    than silently ignored.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    user_id: str = Field(alias="userId", min_length=1, max_length=36)


class ProjectMember(BaseModel):
    """One live member of a project, as the roster and the add answer it."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="userId")
    name: str
    role: str
    added_at: date = Field(alias="addedAt")


class ProjectRef(BaseModel):
    """A project an account is a live member of — ``GET /api/shema/me/projects``."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    language_name: str = Field(alias="languageName")

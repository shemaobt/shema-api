import math
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, model_validator


def _non_finite_as_text(value: object) -> object:
    """Hand ``NaN`` and the infinities on as text, so the refusal can be written back.

    ``json.loads`` reads ``NaN`` and ``Infinity`` into floats, and FastAPI's 422 echoes the
    input it refused. The response encoder will not write a non-finite float, so the refusal
    itself would die as a 500. As text the value still fails ``allow_inf_nan=False`` — the
    float parser reads ``"nan"`` back — and the 422 can carry it.

    It sits after the ``Field`` in the ``Annotated`` on purpose: there the bounds are pushed
    into the float schema it wraps. Put first, the bounds run after the parse instead, ``ge``
    meets the float ``NaN`` before ``allow_inf_nan`` does, and the 500 is back.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


#: Degrees north, on the globe: ``-90`` to ``90`` inclusive, never ``NaN`` or infinite.
Latitude = Annotated[
    float, Field(ge=-90, le=90, allow_inf_nan=False), BeforeValidator(_non_finite_as_text)
]
#: Degrees east, on the globe: ``-180`` to ``180`` inclusive, never ``NaN`` or infinite.
Longitude = Annotated[
    float, Field(ge=-180, le=180, allow_inf_nan=False), BeforeValidator(_non_finite_as_text)
]


def _assert_whole_pair(latitude: float | None, longitude: float | None) -> None:
    """A coordinate is both numbers or neither; the location can still be only a name.

    Half a pair is no point on any map, and storing it leaves every reader to guess whether
    the other half was lost or never known. The console refuses it on its side too.
    """
    if (latitude is None) != (longitude is None):
        raise ValueError("Send latitude and longitude together: both numbers, or both null")


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    language_id: str
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    location_display_name: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _coordinates_are_a_pair(self) -> "ProjectCreate":
        _assert_whole_pair(self.latitude, self.longitude)
        return self


class ProjectMemberPreview(BaseModel):
    user_id: str
    display_name: str | None
    avatar_url: str | None


class ProjectBaseResponse(BaseModel):
    id: str
    name: str
    description: str | None
    language_id: str
    latitude: float | None
    longitude: float | None
    location_display_name: str | None
    journey_id: str | None = None
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectResponse(ProjectBaseResponse):
    team_size: int = 0
    phases_completed: int = 0
    phases_total: int = 0
    members_preview: list[ProjectMemberPreview] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    language_id: str | None = None
    image_url: str | None = Field(default=None, max_length=500)


class ProjectLocationUpdate(BaseModel):
    """A partial write of the location: a field left out is kept, a field sent as null is cleared.

    The pair is judged on what was sent, not on what the project would end up holding. Only
    the name, with neither coordinate, leaves the coordinates alone; both coordinates, as
    numbers or as nulls, set or clear them; one coordinate on its own — a number or a null —
    is refused. Merging a lone half with the stored other half was the alternative, and it
    was rejected: it makes the answer depend on a row the client may not have read, and a
    client that means to move a point always knows both halves of it.
    """

    latitude: Latitude | None = None
    longitude: Longitude | None = None
    location_display_name: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _coordinates_are_a_pair(self) -> "ProjectLocationUpdate":
        sent = {"latitude", "longitude"} & self.model_fields_set
        if sent and sent != {"latitude", "longitude"}:
            raise ValueError("Send latitude and longitude together: both numbers, or both null")
        _assert_whole_pair(self.latitude, self.longitude)
        return self


class ProjectGrantUserAccess(BaseModel):
    user_id: str
    role: str = Field(default="member", max_length=30)


class ProjectUserAccessRoleUpdate(BaseModel):
    role: Literal["member", "manager"]


class ProjectGrantOrganizationAccess(BaseModel):
    organization_id: str


class ProjectUserAccessResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    role: str = "member"
    granted_at: datetime

    model_config = {"from_attributes": True}


class ProjectOrganizationAccessResponse(BaseModel):
    id: str
    project_id: str
    organization_id: str
    granted_at: datetime

    model_config = {"from_attributes": True}


class ProjectUserAccessDetailResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    email: str
    display_name: str | None
    avatar_url: str | None = None
    role: str = "member"
    granted_at: datetime


class ProjectOrganizationAccessDetailResponse(BaseModel):
    id: str
    project_id: str
    organization_id: str
    name: str
    slug: str
    granted_at: datetime

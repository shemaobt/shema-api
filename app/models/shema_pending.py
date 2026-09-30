"""A project the mesa's approval filed, on the wire — what the Admin reads, confirms or discards.

OBT-547. Four shapes and two bodies, camelCase by alias over the house's snake_case attributes
(``app/models/shema_session.py``'s mechanism).

**The pending project is a** :class:`~app.models.shema_privacy.LeavingShape`. It names the place
the team typed and the base the Admin will type, so the boundary applies to it like to every
other shape that can: the service builds it for the Admin's reader, and a reader that is not
coordination would read the region. The Admin reads it as coordination today — that is
``COORDINATION_EVERYWHERE``'s hypothesis (OBT-528), and removing ``admin`` from it would make this
list read the region too, with no edit here.

**The confirmation's answer names no place.** It says which requests now point at the project,
who joined its team, who was invited and who was left out for want of an address — the
invitation links once, as ``SentInvite`` hands them over. ``test_privacy_owners.py``'s route
audit asks nothing of it, because no field is a place, a base or a contact.

**``sensitiveCountry`` has no default in the body.** The flag is the Admin's decision at the
conference — the project was filed with it false, because the form asks no such thing — and a
client that forgets to send it is refused rather than taken to mean *not sensitive*.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, validate_email

from app.models.shema_privacy import LeavingShape

_REQUEST = ConfigDict(populate_by_name=True, extra="forbid")
_RESPONSE = ConfigDict(populate_by_name=True)


class PendingMember(BaseModel):
    """One person the project proposes: a row of the form's team table, or the link's holder."""

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    name: str
    role: str
    email: str


class PendingProject(LeavingShape):
    """A project waiting for the Admin: what the form carried and whom it proposes."""

    id: str
    language_name: str = Field(alias="languageName")
    language_code: str = Field(alias="languageCode")
    location: str
    team: str
    request_id: str = Field(default="", alias="requestId")
    request_name: str = Field(default="", alias="requestName")
    #: When the approval filed it — the row's own ``created_at``, read under the name it means here.
    created_at: datetime = Field(alias="filedAt")
    members: list[PendingMember] = Field(default_factory=list)


class ConfirmedMemberIn(BaseModel):
    """A person the Admin keeps on the list. A blank ``email`` is kept out, and said so."""

    model_config = _REQUEST

    name: str = Field(default="", max_length=300)
    email: str = Field(default="", max_length=320)

    @field_validator("email")
    @classmethod
    def _an_address_or_nothing(cls, value: str) -> str:
        """Lower-cased, so one address typed twice in two spellings is one person."""
        value = value.strip().lower()
        if value:
            validate_email(value)
        return value


class ProjectConfirmation(BaseModel):
    """``POST /projects/{id}/confirm`` — the Admin's adjustments, the flag and the list.

    ``languageCode``, ``location`` and ``team`` left out keep what was filed; sent, even blank,
    they are the Admin's value.
    """

    model_config = _REQUEST

    language_name: str = Field(alias="languageName", min_length=1, max_length=200)
    language_code: str = Field(default="", alias="languageCode", max_length=50)
    location: str = Field(default="", max_length=500)
    team: str = Field(default="", max_length=300)
    sensitive_country: bool = Field(alias="sensitiveCountry")
    members: list[ConfirmedMemberIn] = Field(default_factory=list, max_length=200)


class ProjectDiscard(BaseModel):
    """``POST /projects/{id}/reject`` — why the Admin discards it, which is required."""

    model_config = _REQUEST

    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def _said_something(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("a discard needs a reason")
        return value


class JoinedMember(BaseModel):
    """An address that had an account, now on the project's team."""

    model_config = _RESPONSE

    email: str
    user_id: str = Field(alias="userId")


class InvitedMember(BaseModel):
    """An address with no account, invited to the team — the link once, as ``SentInvite``."""

    model_config = _RESPONSE

    email: str
    invite_id: str = Field(alias="inviteId")
    invite_url: str = Field(alias="inviteUrl")
    email_sent: bool = Field(alias="emailSent")


class ConfirmedProject(BaseModel):
    """What confirming did: the requests stamped, who joined, who was invited, who was left out."""

    model_config = _RESPONSE

    id: str
    language_name: str = Field(alias="languageName")
    request_ids: list[str] = Field(alias="requestIds")
    joined: list[JoinedMember]
    invited: list[InvitedMember]
    without_email: list[str] = Field(alias="withoutEmail")


class DiscardedProject(BaseModel):
    """What discarding did — and what it left alone: the request stays approved, with no project.

    ``requestProjectId`` is read off the request after the commit, so the answer states what is
    stored rather than what was meant; ``detail`` says it in a sentence for whoever reads the
    body without the screen.
    """

    model_config = _RESPONSE

    id: str
    reason: str
    discarded_at: datetime = Field(alias="discardedAt")
    request_id: str = Field(alias="requestId")
    request_project_id: str | None = Field(alias="requestProjectId")
    detail: str

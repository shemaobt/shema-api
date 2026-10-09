"""The wire shape of the audit feed — OBT-577. Camel-case keys, like every Shemá model."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditEntry(BaseModel):
    """One act on the PME: who, when, to what, and the keys it touched — never the values.

    The two ledgers it reads are told apart by :attr:`source`: ``record`` is a field of a
    project's own record (``shema_record_edits``) and ``log`` is any other act
    (``shema_change_log``). ``oldValue``/``newValue`` exist only on the first, and are ``None``
    for a guarded field and for every reader who may not read that field.
    """

    model_config = ConfigDict(populate_by_name=True)

    source: str
    subject: str
    subject_id: str | None = Field(default=None, alias="subjectId")
    action: str
    project_id: str | None = Field(default=None, alias="projectId")
    region_key: str | None = Field(default=None, alias="regionKey")
    fields: list[str] = []
    old_value: str | None = Field(default=None, alias="oldValue")
    new_value: str | None = Field(default=None, alias="newValue")
    changed_by: str = Field(alias="changedBy")
    changed_at: datetime = Field(alias="changedAt")

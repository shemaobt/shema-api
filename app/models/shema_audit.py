"""The wire shape of the audit feed (OBT-577), camel-case outward like the other read models."""

from datetime import datetime

from pydantic import AliasGenerator, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

_OUTWARD = ConfigDict(
    populate_by_name=True,
    alias_generator=AliasGenerator(serialization_alias=to_camel),
)


class AuditEntry(BaseModel):
    """One act on the PME: who, when, to what, and the keys it touched — never the values.

    The two ledgers it reads are told apart by :attr:`source`: ``record`` is a field of a
    project's own record (``shema_record_edits``) and ``log`` is any other act
    (``shema_change_log``). ``old_value``/``new_value`` exist only on the first, and are ``None``
    for a guarded field.
    """

    model_config = _OUTWARD

    source: str
    subject: str
    subject_id: str | None = None
    action: str
    project_id: str | None = None
    region_key: str | None = None
    fields: list[str] = []
    old_value: str | None = None
    new_value: str | None = None
    changed_by: str
    changed_at: datetime

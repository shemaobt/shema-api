"""The list of sensitive countries — the Admin's, read by the write path (OBT-616).

Karina, via Daniel, 19/out/2026: India, China, Iran, Iraq and the Middle East are sensitive, and a
project in one of them is sensitive **by its country** — nobody has to remember to tick the flag.
A project whose country is not on the list can still be marked on its own (the north of Brazil);
that is ``shema_projects.sensitive_country``, the coordination's as before.

**One row per country, named as the list names it, with the other ways a place may write it.**
``location`` is free text the teams type in Portuguese, English or Spanish, and the region's map
(``app/utils/shema_derivations.py``) knows the spellings of 25 countries — only three of which are
on this list. So the list carries its own spellings (*Irã*, *Iran*, *Irão*) for the countries the
map does not know, and the comparison goes through the map's synonyms too for the ones it does
(:class:`~app.utils.shema_derivations.SensitiveCountries`). A table and not a constant, because
the Admin edits it in the console; revision ``20261027_shema616`` seeded Karina's nineteen.

**Nothing reads it but** ``app/services/shema/_sensitive_list.py`` — *lida pelo servidor num
lugar só* — and ``tests/test_shema/test_sensitive_countries.py`` holds that line. Who changed it
and when is in ``shema_change_log``; what it held is not, because that log is read by the
coordination and the list is the Admin's.
"""

from __future__ import annotations

from sqlalchemy import JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ShemaSensitiveCountry(Base):
    """One country on the list: its name in the list's words, and its other spellings."""

    __tablename__ = "shema_sensitive_countries"

    #: The country as the list names it — Portuguese, as Karina wrote it.
    name: Mapped[str] = mapped_column(String(120), primary_key=True)
    #: Every other way a ``location`` may write it — English, Portuguese of Portugal, Spanish.
    spellings: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )

"""The name the console prints where a withheld name is the region key — vendored, read once.

``shema_sensitive_project_names.json`` beside this file is ``src/utils/__tests__/
sensitiveProjectNames.json`` of ``shemaobt/project-management-ecosystem``, copied byte for byte at
:data:`VENDORED_FROM`: for every region, in each of the console's two languages, what
``getLanguageNameDisplay`` prints where a withheld record carries the region key as its name
(OBT-560) — *Projeto sensível — África*, *Sensitive project — Africa*. It is data, never edited
here. Re-vendor by running ``npm run emit:sensitive-names`` over there and copying the file
across; ``sensitiveProjectNames.test.ts`` fails over there the day the console prints something
the file does not say, and ``tests/test_shema/test_name_order.py`` fails here the day the file
misses a region or a language.

**Why the server holds the console's words at all (OBT-657).** OBT-563 orders every list by the
name its reader reads, and a list is ordered where it is cut: the Projetos list is paged here and
the ETEN report is computed here, so the console cannot move a line the server already placed.
The name the reader reads is the one the console prints, and that name sits among the P's in
Portuguese and among the S's in English — no key without a language puts it right in both. So the
console states the language it prints in (``X-Shema-Language``, ``app/api/shema/_deps.py``) and
this file says what it prints in each. Read whole rather than retyped, so the server neither
keeps a second copy of the console's catalogs nor reimplements its interpolation.

**In** ``app/utils/`` because :func:`~app.utils.shema_facets.reading_key` orders by it and
:meth:`~app.models.shema_privacy.LeavingShape.spoken_name` asks :func:`stands_in_for_a_name`, and
a utility may not import a model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from app.db.models.shema_enums import ShemaRegionKey

#: The commit of ``shemaobt/project-management-ecosystem`` the file was copied from.
VENDORED_FROM: Final = "47a07c731238c5b535faae6c50456dc27d601b89"

#: The console's language, spelled as ``PulseLanguage`` spells it → the region key → the name
#: the console prints in its place.
PRINTED_NAMES: Final[dict[str, dict[str, str]]] = json.loads(
    (Path(__file__).parent / "shema_sensitive_project_names.json").read_text(encoding="utf-8")
)

_REGION_KEYS: Final = frozenset(region.value for region in ShemaRegionKey)


def stands_in_for_a_name(name: str, *, withheld: bool) -> bool:
    """Whether ``name`` is the region key standing in for a name nobody registered (OBT-560).

    A withheld name is the public one coordination registered or, while none is, the region key,
    and only the second is not a name: the console prints it as words and a sentence says
    something else. The console asks the same question in ``getLanguageNameDisplay``.
    """
    return withheld and name in _REGION_KEYS


def printed_name(name: str, *, withheld: bool, language: str) -> str:
    """``name`` as the console prints it in ``language`` — the region key in words, else itself."""
    if stands_in_for_a_name(name, withheld=withheld):
        return PRINTED_NAMES[language][name]
    return name

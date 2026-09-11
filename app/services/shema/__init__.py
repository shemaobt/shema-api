"""Shemá's service layer — all of this module's logic and **all** of its queries.

Empty until BE-03. One operation per file with a re-export here, which is the newer
house style (``app/services/access_request/``, ``project/``, ``auth/``,
``resource_request/``) rather than the grouped ``*_service.py`` of
``annotation_studio/``.

Three files in here are named before they exist because they are sole owners and a
second reader of what they guard is the defect: ``_scope.py`` (which projects a caller
reaches, from role **and** region), ``_consent.py`` (the only reader of the three
prayer columns) and ``_redaction.py`` (the sensitive-country rule). ``docs/shema.md``
§6 is why each is one file, and §3.3 is where every other concern lands under the
layering rules.
"""

from __future__ import annotations

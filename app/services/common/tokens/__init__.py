"""Link tokens — minted, read and dated in one place (the invite and the reset are not yet).

**Why one module.** Before BE-20 (OBT-525) three tokens were written three ways: the leader
link with ``token_urlsafe(32)``, the access invite and the password reset with
``token_hex(32)``, each deciding its own states — and the access work of OBT-522 adds four
more (the handoff code, the endorsement link, the external request link, the intercessor's
exit link). A token that reinvents its hash and its states is how one of them ends up with
no expiry, so the new ones have one place to be minted and read.

**What is shared is the function, not the row.** There is no table of tokens. Each purpose
keeps its own table with a real foreign key, because each token points at something
different and *used* means something different in each — the first answer on a multi-use
link, the acceptance of an invite, the spend of a handoff code. A table keyed by a kind and a
target id would trade every one of those keys for a string the database cannot check.
``docs/shema.md`` §6.7.

**The raw value leaves once.** :func:`mint` and :func:`mint_code` hand back the raw value and
its digest; the caller stores the digest and returns the raw value in the response that
created the row, and nowhere else.

**The module reads no configuration.** How long a token may live is its purpose's key in
``app/core/config.py``, one key per purpose, read by the service that mints it and passed to
:func:`expiry`. The module is shared; the ceiling is not.
"""

from app.services.common.tokens.digest import digest
from app.services.common.tokens.expiry import expiry
from app.services.common.tokens.mint import mint
from app.services.common.tokens.mint_code import mint_code
from app.services.common.tokens.status import TokenRow, TokenStatus, status

__all__ = [
    "TokenRow",
    "TokenStatus",
    "digest",
    "expiry",
    "mint",
    "mint_code",
    "status",
]

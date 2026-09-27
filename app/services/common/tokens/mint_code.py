import secrets
from typing import Final

from app.services.common.tokens.digest import digest
from app.services.common.tokens.minted import Minted

_CODE_DIGITS: Final = 6


def mint_code() -> Minted:
    """A fresh six-digit confirmation code and its digest.

    Drawn by ``secrets`` from the whole million and zero-padded, so ``000042`` is a code like
    any other; a draw over 100000 to 999999 would leave a tenth of the space unused.

    The digest is the token's, and it is honest to say what it buys: a million values is
    brute-forced offline in no time, so the hash does not protect a code that leaks while it
    is alive. What protects a live code is its short life and the attempt limit — and the
    limit is a column of the table that uses the code, not this module's. It is the trade
    ``app/services/device/claim_code.py`` records for the Room's installation code.
    """
    code = f"{secrets.randbelow(10**_CODE_DIGITS):0{_CODE_DIGITS}d}"
    return Minted(raw=code, digest=digest(code))

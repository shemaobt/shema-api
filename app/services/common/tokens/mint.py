import secrets
from typing import Final

from app.services.common.tokens.digest import digest

#: 256 bits, URL-safe: 43 characters. Shorter than ``token_hex(32)`` for the same entropy,
#: which matters for exactly one reason: every token here travels as a link — in an e-mail,
#: in a WhatsApp message to a phone — and a token that wraps is a token somebody retypes.
_TOKEN_BYTES: Final = 32


def mint() -> tuple[str, str]:
    """A fresh token and its digest — the raw value leaves once and is never stored.

    The caller writes the digest to its own table and hands the raw value back in the
    response that created the row. A holder who loses it gets a new one; nothing can read
    this one back.
    """
    raw = secrets.token_urlsafe(_TOKEN_BYTES)
    return raw, digest(raw)

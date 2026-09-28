from typing import NamedTuple


class Minted(NamedTuple):
    """A fresh secret and the digest that is stored for it, named rather than ordered.

    Both halves are ``str``, so a bare pair would let ``stored, raw = mint()`` type-check and
    write the raw token into ``token_hash`` — the one mistake this module exists to rule out.
    Read them as ``minted.raw`` and ``minted.digest``.
    """

    raw: str
    digest: str

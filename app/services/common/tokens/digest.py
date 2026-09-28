import hashlib


def digest(raw: str) -> str:
    """The value a token row stores and is looked up by — the SHA-256 of the raw token, in hex.

    The same value ``app/services/auth/hash_refresh_token.py`` computes, on purpose: every row
    written before this module was hashed that way, and a link already in someone's hands must
    still open. Computed here rather than imported from ``app/services/auth/`` because this
    module sits below the three that use it — auth, resource requests and Shemá — and
    importing the auth package from it would point the dependency the wrong way.
    ``tests/test_link_tokens.py`` holds the two equal.
    """
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

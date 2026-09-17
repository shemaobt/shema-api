"""The long-lived credential a device gets in exchange for its claim code.

Unlike the claim code, this **is** a credential. It is what the room app authenticates
with for the rest of the device's life, and it is the higher-value secret of the two.

The primitive is the repository's, not a new one: ``secrets.token_hex(32)`` hashed with
SHA-256 into a 64-character column, exactly as ``auth.RefreshToken.token_hash`` and the
password-reset tokens are built. 256 bits of entropy is not guessable, which is why this
one — unlike the claim code, which a human has to read aloud — is not shortened.

**It has no expiry, and as of this slice nothing ends it.** A tablet in a room with no
reliable network cannot be asked to re-authenticate on a schedule, and a credential that
expires mid-session takes the room down — so there is no clock on it.

Be precise about what that leaves, because the first draft of this docstring was not:
right now there is **no way to revoke one**. Claiming the device again is not a way out,
because a spent code is refused as already used, and there is no other path that replaces
the hash. Until something takes that on, an issued credential is good for as long as the
row exists.

Unlinking a device is what ends it, and that arrives in **ENG-444**, which nulls this
column as its revocation. Requiring the credential in place of the shared ``X-Room-Key``
is **ENG-448**. Neither is in this slice.

What limits the damage in the meantime is what the credential can do: it is bound to one
device row and buys nothing but "which project am I".
"""

import hashlib
import secrets

_CREDENTIAL_BYTES = 32


def generate_device_credential() -> str:
    """A fresh credential. Returned to the caller once and never stored."""
    return secrets.token_hex(_CREDENTIAL_BYTES)


def hash_device_credential(credential: str) -> str:
    """The value stored in the row, so that the credential itself never is."""
    return hashlib.sha256(credential.encode("utf-8")).hexdigest()

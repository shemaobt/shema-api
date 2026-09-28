from datetime import datetime, timedelta
from typing import overload


@overload
def expiry(now: datetime, *, days: int) -> datetime: ...
@overload
def expiry(now: datetime, *, seconds: int) -> datetime: ...
def expiry(now: datetime, *, days: int | None = None, seconds: int | None = None) -> datetime:
    """When a token minted at ``now`` dies, given its purpose's life.

    The life is the purpose's key in ``app/core/config.py``, read by the minting service, in
    the unit that key is stated in — days for a link, seconds for a code — and named, never
    positional: ``expiry(now, 60)`` would leave a reader guessing between a minute and two
    months.

    Refused rather than computed, with ``ValueError`` because each is a programming or
    configuration fault and never the client's: no unit or both; a life of zero or less, since
    a token born dead fails every use with a message about expiry nobody can act on; and a
    ``now`` with no offset, since a naive expiry is exactly the ambiguity
    ``app/utils/stored_time.py`` settles on the way back, and it is not reintroduced on the
    way in.
    """
    if now.tzinfo is None:
        raise ValueError("expiry needs a clock with an offset, and this one has none")
    if days is not None and seconds is None:
        life = timedelta(days=days)
    elif seconds is not None and days is None:
        life = timedelta(seconds=seconds)
    else:
        raise ValueError("expiry takes the life in days or in seconds, exactly one of them")
    if life <= timedelta(0):
        raise ValueError(f"a token has to live for some time, and {life} is not any")
    return now + life

"""What counts as a way to reach somebody, and how much of it a list may show.

Two pure functions of a string. They are in ``app/utils/`` and not in
``app/services/shema/_directory.py`` for the reason ``docs/shema.md`` §3.1 gives about the
derivations: both halves of the module need them, and one of the halves is
``app/models/``, which ``test_no_dto_module_reaches_up_into_the_service_layer`` in
``tests/test_app_boots.py`` forbids from importing ``app/services/`` — the inversion that
closed an import cycle once.
``app/models/shema_intercessor.py`` refuses a payload with no usable channel and
``_directory.py`` masks a stored one, and a second spelling of *what is an e-mail* between
them is exactly the defect this module keeps refusing elsewhere.

The column itself stays ``_directory.py``'s and only ``_directory.py``'s. These functions
know nothing about a row: **reading a contact out of the database is the guarded act**, not
deciding whether a string looks like a phone number.

``app/utils/`` is flat (``description_rule.py``, ``stored_time.py``), so the file carries the
module prefix rather than forming a package its siblings do not have.
"""

from __future__ import annotations

import re

#: The console's ``EMAIL`` in ``src/utils/intercessors.ts``, character for character. Not a
#: better address grammar on purpose: a server that refuses what the form accepts refuses a
#: record for a reason neither side can see.
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_NON_DIGITS = re.compile(r"\D")

#: The console's ``MIN_PHONE_DIGITS``. Eight is what lets a national number with no country
#: code still count, and it is the floor the frontend already refuses below.
MIN_PHONE_DIGITS = 8

#: What a hint hides with. A fixed width, so a hint's length says nothing about the
#: contact's — a mask that grew with the string would leak the length of every phone number
#: in the directory.
MASK = "•••"


def contact_channel(contact: str) -> str | None:
    """``email``, ``phone``, or ``None`` for a string nobody can be reached at.

    The console's ``contactChannel``, and the rule behind *at least one usable channel or the
    record is refused* (``docs/shema.md`` §5.7). ``None`` is the refusal and not a third
    channel: a network entry that cannot be reached is not a record, it is retained personal
    data with no purpose.
    """
    value = contact.strip()
    if _EMAIL.match(value):
        return "email"
    if len(_NON_DIGITS.sub("", value)) >= MIN_PHONE_DIGITS:
        return "phone"
    return None


def contact_hint(contact: str) -> str:
    """Enough of a contact to tell two people apart, and not enough to reach either.

    A directory's job is to say who is in it. The Resource Circle member looking at two
    *Maria Santos* in Brazil needs to know which row is which, and that is the whole of what
    this answers. An e-mail keeps its first character and **loses its domain**, which is
    often the employer and so the identifying half; a phone keeps its last two digits, which
    separates a short list and identifies nobody outside one.

    A contact with no channel is not hinted at all. The write refuses such a string, so
    reaching that branch means a row predates the rule — and guessing at the shape of
    something nobody validated is how a mask leaks what it masks.
    """
    value = contact.strip()
    channel = contact_channel(value)
    if channel == "email":
        return f"{value[0]}{MASK}@{MASK}"
    if channel == "phone":
        return f"{MASK}{_NON_DIGITS.sub('', value)[-2:]}"
    return MASK

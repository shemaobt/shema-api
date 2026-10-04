"""A stand-in for the e-mail provider's HTTP client, for the cases that read what was sent.

``send_email`` posts to Resend through ``httpx.AsyncClient``, so a case that has to see what
left — or has to see the provider down — swaps that class for the one built here. The
e-mail infrastructure's own cases (``test_email_infra.py``) and the Admin's invitations
(``test_shema/test_admin_invites.py``) both read the provider this way, which is why it is
here and not in either of them.
"""

from __future__ import annotations


class _OkResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {}


def client_class(recorded: list, error: Exception | None = None):
    """An ``httpx.AsyncClient`` that appends each ``post`` to ``recorded``, or raises ``error``."""

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc) -> bool:
            return False

        async def post(self, url: str, **kwargs):
            if error is not None:
                raise error
            recorded.append((url, kwargs))
            return _OkResponse()

    return _Client

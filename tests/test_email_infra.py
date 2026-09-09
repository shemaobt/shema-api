"""The e-mail infrastructure: one generic send_email, templates, and the guarantee
that a provider outage never rolls back the domain write of whoever sent the mail."""

import logging

import httpx
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.db.models.auth import PasswordResetToken
from app.services.auth.request_password_reset import request_password_reset
from app.services.common.email import render_email, send_email
from tests.baker import make_user


class _OkResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {}


def _client_class(recorded: list, error: Exception | None = None):
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


class _NoNetworkClient:
    def __init__(self, *args, **kwargs) -> None:
        raise AssertionError("provider=log must not open an HTTP client")


async def test_the_default_provider_in_tests_is_log_and_nothing_leaves(monkeypatch, caplog) -> None:
    assert get_settings().email_provider == "log"
    monkeypatch.setattr(httpx, "AsyncClient", _NoNetworkClient)

    with caplog.at_level(logging.INFO):
        sent = await send_email("someone@example.com", "Hello", "<p>Hi</p>")

    assert sent is True
    assert "someone@example.com" in caplog.text


async def test_send_email_hands_recipient_subject_and_sender_to_resend(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "email_provider", "resend")
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    recorded: list = []
    monkeypatch.setattr(httpx, "AsyncClient", _client_class(recorded))

    sent = await send_email(
        "dest@example.com",
        "A subject from outside",
        "<p>body</p>",
        from_name="Resource Circle",
    )

    assert sent is True
    [(url, kwargs)] = recorded
    assert url == "https://api.resend.com/emails"
    payload = kwargs["json"]
    assert payload["to"] == ["dest@example.com"]
    assert payload["subject"] == "A subject from outside"
    assert payload["html"] == "<p>body</p>"
    assert payload["from"] == f"Resource Circle <{settings.email_from_address}>"


def test_the_default_sender_is_the_address_resend_was_always_given() -> None:
    assert Settings.model_fields["email_from_address"].default == "noreply@shemaywam.com"


async def test_a_provider_outage_is_reported_not_raised(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "email_provider", "resend")
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(
        httpx, "AsyncClient", _client_class([], error=httpx.ConnectError("provider down"))
    )

    sent = await send_email("dest@example.com", "Subject", "<p>body</p>")

    assert sent is False


async def test_an_unknown_provider_refuses_quietly(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "email_provider", "carrier-pigeon")

    sent = await send_email("dest@example.com", "Subject", "<p>body</p>")

    assert sent is False


def test_templates_escape_what_the_user_typed() -> None:
    html = render_email(
        "password_reset.html.jinja",
        greeting='<script>alert("x")</script>',
        reset_url="https://app.example.com/reset-password?token=abc",
        app_name="Resource Circle",
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_the_password_reset_email_still_says_everything_it_said() -> None:
    html = render_email(
        "password_reset.html.jinja",
        greeting="Alice",
        reset_url="https://app.example.com/reset-password?token=abc",
        app_name="Resource Circle",
    )

    assert "Hi Alice," in html
    assert 'href="https://app.example.com/reset-password?token=abc"' in html
    assert "Reset Password" in html
    assert "This link expires in 1 hour." in html
    assert "Resource Circle by Shema YWAM" in html


def test_the_access_invite_template_is_ready_for_be17() -> None:
    html = render_email(
        "access_invite.html.jinja",
        greeting="Bob",
        inviter_name="Alice",
        invite_url="https://app.example.com/invite?token=xyz",
        app_name="Resource Circle",
    )

    assert "Hi Bob," in html
    assert "Alice has invited you" in html
    assert 'href="https://app.example.com/invite?token=xyz"' in html
    assert "Accept Invitation" in html


def test_the_access_invite_reads_well_without_an_inviter_or_a_name() -> None:
    html = render_email(
        "access_invite.html.jinja",
        invite_url="https://app.example.com/invite?token=xyz",
        app_name="Resource Circle",
    )

    assert "Hi," in html
    assert "You have been invited" in html


async def test_a_dead_provider_does_not_revert_the_password_reset_token(
    db_session, monkeypatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "email_provider", "resend")
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(
        httpx, "AsyncClient", _client_class([], error=httpx.ConnectError("provider down"))
    )
    await make_user(db_session, email="reset-me@example.com")
    await db_session.commit()

    await request_password_reset(db_session, "reset-me@example.com", "meaning-map-generator")

    tokens = (await db_session.execute(select(PasswordResetToken))).scalars().all()
    assert len(tokens) == 1
    assert tokens[0].used_at is None

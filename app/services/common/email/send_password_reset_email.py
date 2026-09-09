"""First consumer of the e-mail infrastructure: the password reset message."""

from app.services.common.email.render_email import render_email
from app.services.common.email.send_email import send_email


async def send_password_reset_email(
    to_email: str,
    display_name: str | None,
    reset_url: str,
    app_name: str,
) -> bool:
    """Render and send the password reset e-mail; True when handed to the provider."""
    html = render_email(
        "password_reset.html.jinja",
        greeting=display_name or to_email,
        reset_url=reset_url,
        app_name=app_name,
    )
    return await send_email(
        to=to_email,
        subject=f"Reset your password — {app_name}",
        html=html,
        from_name=app_name,
    )

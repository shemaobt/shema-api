"""Second consumer of the e-mail infrastructure: the access invitation.

The ``access_invite.html.jinja`` template shipped with BE-12 waiting for this
call; OBT-477 is what finally sends it. Same contract as the password reset:
render, hand to ``send_email``, and report — never raise — so the invite row the
caller already committed survives a dead provider.
"""

from app.services.common.email.render_email import render_email
from app.services.common.email.send_email import send_email


async def send_access_invite_email(
    to_email: str,
    inviter_name: str | None,
    invite_url: str,
    app_name: str,
) -> bool:
    """Render and send the access invite e-mail; True when handed to the provider."""
    html = render_email(
        "access_invite.html.jinja",
        inviter_name=inviter_name,
        invite_url=invite_url,
        app_name=app_name,
    )
    return await send_email(
        to=to_email,
        subject=f"You're invited to {app_name}",
        html=html,
        from_name=app_name,
    )

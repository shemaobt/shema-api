"""Who is allowed through the Desk's door.

The routes here used to ask only ``facilitates_project`` inside the handler, which answers
"is this team yours" and never "are you a facilitator". Every authenticated user on the
platform reached the handler; the ones without a team were turned away by the team check, and
the ones whose request named no team were not turned away at all.

``facilitator_role`` is bound to a name rather than built inline at each route because the
test that enumerates these routes compares against this object. A gate the test can only
recognise by its spelling is a gate the next route can miss.
"""

from typing import Annotated

from app.core.access_control import require_role
from app.db.models.auth import User

APP_KEY = "internalization-room"

facilitator_role = require_role(APP_KEY, "facilitator")

#: The person at the Desk, and also the person on the other end of a raised hand: the room's
#: facilitator routes annotate with this same object rather than calling ``require_role`` a
#: second time, so both families are guarded by one gate and the audit recognises both.
#:
#: Named for the role rather than ``CurrentUser`` on purpose. Every other app's ``_deps``
#: binds that name to ``require_app_access`` — "any role on this app" — and there is no such
#: thing here: this slice exists because holding *a* role on the room is not holding this
#: one. Reusing the house name for the stricter meaning is how the two get confused.
#:
#: Platform admins pass, since they already hold every other power here and locking them out
#: would leave nobody able to investigate an installation.
FacilitatorUser = Annotated[User, facilitator_role]

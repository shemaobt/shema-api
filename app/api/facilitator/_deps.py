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

#: The person at the Desk. Platform admins pass, since they already hold every other power
#: here and locking them out would leave nobody able to investigate an installation.
FacilitatorUser = Annotated[User, facilitator_role]

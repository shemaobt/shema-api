"""What the coverage states and the element kinds are called, once for the whole Desk.

A route of its own rather than a field on the coverage response. The legend is the same for
every team and every passage, so carrying it on each necklace would repeat ten pairs of names
on every request to say what does not change.

It is mounted under a prefix of its own, like the two routers beside it: `devices.py` and
`teams.py` keep disjoint URL spaces so nothing depends on the order they are mounted in, and
a third router on the bare `/api/facilitator` would be the one that broke that.

Nothing here knows what a state is called. The names live in ENG-442's catalogue and this
module's whole job is to hand them across in the shape the Desk was promised — which is why
a missing name arrives as `ElementLabelsBroken` and leaves as a 500 rather than being papered
over with the raw enum value a facilitator cannot read.
"""

from fastapi import APIRouter, Depends

from app.core.auth_middleware import get_current_user
from app.db.models.auth import User
from app.models.internalization_room import CoverageLegendResponse, LegendName
from app.services.internalization_room.canon.labels import LANGUAGES, legend

facilitator_legend_router = APIRouter()


@facilitator_legend_router.get("", response_model=CoverageLegendResponse)
async def read_coverage_legend_route(
    user: User = Depends(get_current_user),
) -> CoverageLegendResponse:
    """Every coverage state and every element kind, named in the three languages.

    There is no team and no passage in the signature, and there is nothing to gate on beyond
    the door: the answer is the canon's vocabulary and names nothing about the installation.
    It is still behind `get_current_user`, because a single route under this prefix that was
    not is the one somebody points at later to argue the others need not be.

    The set served is whatever the enums hold — `legend()` walks them — so a state added to
    `CoverageStatus` reaches the Desk named, or reaches nobody at all. What it cannot do is
    arrive as `partially_engaged` in front of a facilitator.
    """
    named = legend()
    return CoverageLegendResponse(
        coverage_status=[_named(value, texts) for value, texts in named.coverage_status.items()],
        element_kind=[_named(value, texts) for value, texts in named.element_kind.items()],
    )


def _named(value: str, texts: dict[str, str]) -> LegendName:
    """Spread from `LANGUAGES`, never from three names written out here.

    A fourth language is then a catalogue entry and a field on `LegendName`, and this line is
    not a third place to remember. A guarantee that enumerates the languages it covers is not
    a guarantee about the languages that exist.
    """
    return LegendName(
        value=value, **{f"label_{language}": texts[language] for language in LANGUAGES}
    )

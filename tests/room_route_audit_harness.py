"""ENG-1039 — one walker for every audit that reads the room's mounted routes.

`test_room_credential_never_surfaces.py` and `test_ir_transcript_stays_with_the_facilitator.py`
each need the same thing: every route a tablet can reach, so the guarantee they check holds
over the whole app rather than over a list either file remembered to write. Two copies of that
walker drift — the credential audit's copy learned to also read a gate called directly out of
a route's own body (ENG-993, `voice.py`'s clip route), and the transcript audit's copy did not,
so it silently stopped auditing that route. One walker, shared, is the only way a fix to how
routes are found reaches every audit built on it.
"""

from __future__ import annotations


def _dependency_calls(dependant) -> set:
    calls = {dependant.call}
    for sub in dependant.dependencies:
        calls |= _dependency_calls(sub)
    return calls


def _direct_calls(endpoint) -> set:
    """Gate functions the endpoint's own body calls by name, bypassing ``Depends``.

    `voice.py`'s clip route awaits `require_room_caller` directly so it can run beside the
    GCS read — a call the dependant tree above never sees. Its name still shows up in the
    function's own bytecode, resolved against the module it was imported into.
    """
    names = getattr(getattr(endpoint, "__code__", None), "co_names", ())
    scope = getattr(endpoint, "__globals__", {})
    return {scope[name] for name in names if callable(scope.get(name))}


def room_app_routes() -> list:
    """Every mounted route a tablet can reach, in path order.

    Identified by the room's own gates appearing in the route's dependency tree, or called
    by the endpoint itself. Renaming a gate without updating this set would silently empty
    it, and a gate called by hand would silently drop its route. With one walker there is
    one outcome for every audit built on it, so each of those is guarded once, in
    `test_room_credential_never_surfaces.py`: `test_the_audit_is_not_empty` and
    `test_the_clip_route_stays_in_the_audited_set_even_though_it_calls_its_gate_by_hand`.
    """
    from app.api.internalization_room import _deps
    from app.main import app

    gates = {_deps.require_room_caller, _deps.require_device}
    return sorted(
        (
            route
            for route in app.routes
            if getattr(route, "dependant", None) is not None
            and gates & (_dependency_calls(route.dependant) | _direct_calls(route.endpoint))
        ),
        key=lambda route: (route.path, sorted(route.methods)),
    )

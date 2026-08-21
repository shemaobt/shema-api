"""What the two auth gates remember, and for how long.

Every signed-in request reads two things here: the account, and the roles it holds. Reading
them once and keeping them is what makes `access_control` cheap — a facilitator opening a
team fires six requests in about a second, and none of them should be six trips to the role
tables.

The window is the price of that. While an entry is kept, nothing asks the database again, so
an access that was *taken away* keeps working until the entry ages out. `grant_app_role` and
`revoke_role` call `invalidate_roles`, which closes the door on the next request — but only
for a change written by this process. A revocation from the Tripod Console, from another
Cloud Run instance, or by hand reaches a gate that is not looking, and the window is how long
it stays that way.

Thirty seconds, not the five minutes this started at (ENG-551). Five was a library-shaped
default nobody chose; thirty is a measured trade. The cost has a **ceiling per minute** — two
reloads per user per minute at most, whatever the request rate — so the burst above still
costs nothing, while a withdrawal lands in half a minute instead of five. Checking the
database before granting was measured against it and costs one read per *request* instead,
with no ceiling; that is a separate decision and not this one.

`_user_cache` carries the same window, and for a sharper reason: it holds `is_active`, so its
entry outliving a change means a **deactivated account still getting in**. That is the
strongest withdrawal the Console can make and it reaches every authenticated route on the
platform, not one app's. A short window on the roles and a long one beside it would only be
as short as the longer one.
"""

from typing import Any

from cachetools import TTLCache  # type: ignore[import-untyped]

#: Seconds an authentication answer outlives the row it was read from. See the module
#: docstring: this is the whole of ENG-551, and it is a decision, not a default.
AUTH_CACHE_TTL_SECONDS = 30

_user_cache: TTLCache[str, Any] = TTLCache(maxsize=256, ttl=AUTH_CACHE_TTL_SECONDS)
_roles_cache: TTLCache[str, list[tuple[str, str]]] = TTLCache(
    maxsize=512, ttl=AUTH_CACHE_TTL_SECONDS
)


def get_cached_user(user_id: str) -> Any:
    return _user_cache.get(user_id)


def set_cached_user(user_id: str, user: Any) -> None:
    _user_cache[user_id] = user


def invalidate_user(user_id: str) -> None:
    _user_cache.pop(user_id, None)


def _roles_key(user_id: str, app_key: str | None) -> str:
    return f"{user_id}:{app_key or '*'}"


def get_cached_roles(user_id: str, app_key: str | None) -> list[tuple[str, str]] | None:
    result: list[tuple[str, str]] | None = _roles_cache.get(_roles_key(user_id, app_key))
    return result


def set_cached_roles(user_id: str, app_key: str | None, roles: list[tuple[str, str]]) -> None:
    _roles_cache[_roles_key(user_id, app_key)] = roles


def invalidate_roles(user_id: str) -> None:
    keys_to_remove = [k for k in _roles_cache if k.startswith(f"{user_id}:")]
    for k in keys_to_remove:
        _roles_cache.pop(k, None)

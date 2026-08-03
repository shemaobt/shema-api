from typing import Any

from cachetools import TTLCache  # type: ignore[import-untyped]

_user_cache: TTLCache[str, Any] = TTLCache(maxsize=256, ttl=300)
_roles_cache: TTLCache[str, list[tuple[str, str]]] = TTLCache(maxsize=512, ttl=300)


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

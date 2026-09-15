from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app import UserAppResponse
from app.services.app.list_apps import list_apps
from app.services.app.list_user_apps import list_user_apps


async def list_user_apps_display(
    db: AsyncSession, user_id: str, *, is_admin: bool
) -> list[UserAppResponse]:
    if is_admin:
        all_apps = await list_apps(db)
        user_apps_map: dict[str, list[str]] = {}
        for app, role_keys in await list_user_apps(db, user_id):
            user_apps_map[app.id] = role_keys
        return [
            UserAppResponse(
                id=app.id,
                app_key=app.app_key,
                name=app.name,
                description=app.description,
                icon_url=app.icon_url,
                app_url=app.app_url,
                ios_url=app.ios_url,
                android_url=app.android_url,
                platforms=app.platforms,
                is_active=app.is_active,
                created_at=app.created_at,
                roles=user_apps_map.get(app.id, []),
                is_platform_admin=True,
            )
            for app in all_apps
        ]

    user_apps = await list_user_apps(db, user_id)
    return [
        UserAppResponse(
            id=app.id,
            app_key=app.app_key,
            name=app.name,
            description=app.description,
            icon_url=app.icon_url,
            app_url=app.app_url,
            ios_url=app.ios_url,
            android_url=app.android_url,
            platforms=app.platforms,
            is_active=app.is_active,
            created_at=app.created_at,
            roles=role_keys,
            is_platform_admin=False,
        )
        for app, role_keys in user_apps
    ]

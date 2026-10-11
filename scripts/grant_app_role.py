import argparse
import asyncio
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.db.models.auth import App, Role, User, UserAppRole
from app.services.authorization.grant_app_role import grant_app_role


async def main() -> None:
    parser = argparse.ArgumentParser(description="Grant a role to a user for a specific app.")
    parser.add_argument("email", type=str, help="The email of the user to grant the role to.")
    parser.add_argument(
        "app_key",
        type=str,
        help="The unique key of the app (e.g., 'meaning-map-generator').",
    )
    parser.add_argument(
        "role_key",
        type=str,
        help="The role to grant (e.g., 'admin', 'annotator').",
    )
    parser.add_argument(
        "--add",
        action="store_true",
        help="Keep every role the user holds on the app and add this one, instead of replacing.",
    )

    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == args.email))).scalar_one_or_none()
        if not user:
            print(f"Error: User with email '{args.email}' not found.")
            sys.exit(1)

        app = (
            await db.execute(select(App).where(App.app_key == args.app_key))
        ).scalar_one_or_none()
        if not app:
            print(f"Error: App with key '{args.app_key}' not found.")
            sys.exit(1)

        role = (
            await db.execute(
                select(Role).where(Role.app_id == app.id, Role.role_key == args.role_key)
            )
        ).scalar_one_or_none()
        if not role:
            print(f"Error: Role '{args.role_key}' not found for app '{args.app_key}'.")
            sys.exit(1)

        if args.add:
            await grant_app_role(db, user.id, args.app_key, args.role_key)
            print(f"Added role '{args.role_key}' on {args.app_key} for {args.email}.")
            return

        existing = (
            await db.execute(
                select(UserAppRole).where(
                    UserAppRole.user_id == user.id, UserAppRole.app_id == app.id
                )
            )
        ).scalar_one_or_none()

        if existing:
            existing.role_id = role.id
            print(
                f"Updated existing access for {args.email} "
                f"on {args.app_key} to role '{args.role_key}'."
            )
        else:
            new_role = UserAppRole(user_id=user.id, app_id=app.id, role_id=role.id)
            db.add(new_role)
            print(
                f"Granted new access for {args.email} "
                f"on {args.app_key} with role '{args.role_key}'."
            )

        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())

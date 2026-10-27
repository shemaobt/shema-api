from sqlalchemy import select, update

from app.db.models.auth import App


async def test_a_read_after_a_write_sees_it_without_an_explicit_flush(db_session) -> None:
    await db_session.execute(
        update(App).where(App.app_key == "translation-helper").values(name="Renamed")
    )
    db_session.add(App(app_key="staged-app", name="Staged", is_active=True))

    seen = (await db_session.execute(select(App.app_key).where(App.name == "Staged"))).scalars()

    assert list(seen) == ["staged-app"]

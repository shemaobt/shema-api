from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification import Notification, NotificationMeaningMapDetail


async def create_notification(
    db: AsyncSession,
    *,
    user_id: str,
    app_id: str,
    event_type: str,
    title: str,
    body: str,
    actor_id: str | None = None,
    related_map_id: str | None = None,
    pericope_reference: str | None = None,
    commit: bool = True,
) -> Notification:
    """Write one in-app notification; ``commit=False`` leaves the transaction open.

    **``commit`` exists because this function has two kinds of caller now.** The four that
    predate it — the meaning map's two hooks, the oral collector's, and the Inngest
    helper's — call it *after* their own write is committed, or with no transaction of
    their own at all, and the commit here is what makes the row land. The resource-request
    module's writers control their own transaction: ``save_evaluation`` writes the
    decision, the ledger movement, the stage event and the stage under **one** commit, and
    a commit taken in the middle of that would land a decision whose board move had not
    been written yet. So they stage the notification and let their commit close it, which
    also gives the property worth having: a decision that landed always has its notice, and
    a decision that rolled back leaves none.

    The default is ``True`` so no existing caller changes behaviour — the flag is a
    reconciliation, not a migration. Whoever passes ``False`` owns the commit, and must
    take it before anything leaves the process: e-mail is sent after that commit, never
    inside it (``app/services/resource_request/_notices.py``).
    """
    notif = Notification(
        user_id=user_id,
        app_id=app_id,
        event_type=event_type,
        title=title,
        body=body,
        actor_id=actor_id,
    )
    db.add(notif)
    await db.flush()

    if related_map_id or pericope_reference:
        detail = NotificationMeaningMapDetail(
            notification_id=notif.id,
            related_map_id=related_map_id,
            pericope_reference=pericope_reference,
        )
        db.add(detail)

    if commit:
        await db.commit()
    await db.refresh(notif)
    return notif

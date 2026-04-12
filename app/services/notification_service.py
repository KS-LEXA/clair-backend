from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.models.notification import Notification, NotificationType


def create_notification(
    user_id: int,
    title: str,
    db: Session,
    notification_type: NotificationType = NotificationType.SYSTEM,
    content: Optional[str] = None,
    contract_id: Optional[int] = None,
) -> Notification:
    noti = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        content=content,
        contract_id=contract_id,
    )
    db.add(noti)
    db.commit()
    db.refresh(noti)
    return noti


def get_notifications_grouped(user_id: int, db: Session) -> dict:
    """Today / This week 그룹으로 나눠서 반환."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    all_noti = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.created_at >= week_start)
        .order_by(Notification.created_at.desc())
        .all()
    )

    today = []
    this_week = []
    for n in all_noti:
        created = n.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created >= today_start:
            today.append(n)
        else:
            this_week.append(n)

    return {
        "today": today,
        "this_week": this_week,
        "today_count": len(today),
        "this_week_count": len(this_week),
    }


def get_notifications(user_id: int, db: Session, skip: int = 0, limit: int = 50) -> tuple:
    query = db.query(Notification).filter(Notification.user_id == user_id)
    total = query.count()
    unread_count = query.filter(Notification.is_read == False).count()  # noqa: E712
    notifications = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()
    return total, unread_count, notifications


def get_unread_count(user_id: int, db: Session) -> int:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
        .count()
    )


def mark_as_read(notification_id: int, user_id: int, db: Session) -> Notification:
    noti = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user_id)
        .first()
    )
    if not noti:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="알림을 찾을 수 없습니다.")
    noti.is_read = True
    db.commit()
    db.refresh(noti)
    return noti


def mark_all_as_read(user_id: int, db: Session) -> int:
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
        .update({"is_read": True})
    )
    db.commit()
    return count

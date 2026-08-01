from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.notification import (
    NotificationGroupResponse,
    NotificationListResponse,
    NotificationReadResponse,
    NotificationResponse,
)
from app.services.notification_service import (
    get_notifications_grouped,
    get_notifications,
    get_unread_count,
    mark_as_read,
    mark_all_as_read,
)

router = APIRouter()


@router.get("/grouped", response_model=NotificationGroupResponse, summary="알림 그룹별 조회 (Today / This Week)")
def api_get_notifications_grouped(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_notifications_grouped(user_id=user.id, db=db)


@router.get("", response_model=NotificationListResponse, summary="알림 전체 조회")
def api_get_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total, unread_count, notifications = get_notifications(user_id=user.id, db=db, skip=skip, limit=limit)
    return NotificationListResponse(total=total, unread_count=unread_count, notifications=notifications)


@router.get("/unread-count", summary="읽지 않은 알림 수")
def api_get_unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"unread_count": get_unread_count(user_id=user.id, db=db)}


@router.patch("/{notification_id}/read", response_model=NotificationResponse, summary="알림 읽음 처리")
def api_mark_as_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return mark_as_read(notification_id=notification_id, user_id=user.id, db=db)


@router.patch("/read-all", response_model=NotificationReadResponse, summary="전체 알림 읽음 처리")
def api_mark_all_as_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = mark_all_as_read(user_id=user.id, db=db)
    return NotificationReadResponse(message=f"{count}개의 알림을 읽음 처리했습니다.")

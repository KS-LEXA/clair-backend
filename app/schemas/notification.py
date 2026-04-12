from __future__ import annotations

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class NotificationResponse(BaseModel):
    id: int
    notification_type: str
    title: str
    content: Optional[str] = None
    is_read: bool
    contract_id: Optional[int] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class NotificationGroupResponse(BaseModel):
    """Today / This week 그룹별 알림 응답"""
    today: List[NotificationResponse]
    this_week: List[NotificationResponse]
    today_count: int
    this_week_count: int


class NotificationListResponse(BaseModel):
    total: int
    unread_count: int
    notifications: List[NotificationResponse]


class NotificationReadResponse(BaseModel):
    message: str

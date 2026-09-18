# app/accounts/notification/schema.py

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class DeviceTokenRegisterReq(BaseModel):
    token: str = Field(..., min_length=10, max_length=512)
    platform: str = Field(default="web")
    device_id: Optional[str] = None


class PublicDeviceTokenRegisterReq(BaseModel):
    session_token: Optional[str] = None
    token: str = Field(..., min_length=10, max_length=512)
    platform: str = Field(default="web")
    device_id: Optional[str] = None


class DeviceTokenResponse(BaseModel):
    id: int
    token: str
    platform: str
    is_active: bool
    notifications_enabled: bool
    qr_session_id: Optional[int] = None
    customer_id: Optional[int] = None

    class Config:
        from_attributes = True


class CustomerNotificationPreferenceReq(BaseModel):
    order_updates: Optional[bool] = None
    payment_updates: Optional[bool] = None
    offers: Optional[bool] = None
    promotions: Optional[bool] = None
    loyalty: Optional[bool] = None
    new_menu: Optional[bool] = None
    announcements: Optional[bool] = None


class CustomerNotificationPreferenceResponse(BaseModel):
    customer_id: int
    order_updates: bool
    payment_updates: bool
    offers: bool
    promotions: bool
    loyalty: bool
    new_menu: bool
    announcements: bool
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SendOfferNotificationReq(BaseModel):
    offer_id: int
    target_type: str = Field(default="branch", description="'branch', 'client', or 'customer'")
    target_id: Optional[int] = Field(default=None, description="branch_id, client_id, or customer_id depending on target_type")
    title: Optional[str] = None
    body: Optional[str] = None


class SendAnnouncementReq(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)
    target_type: str = Field(default="branch", description="'branch', 'client', or 'role'")
    branch_id: Optional[int] = None
    role: Optional[str] = Field(default=None, description="e.g. 'chef', 'waiter', 'all'")


class SendNewMenuReq(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)
    branch_id: int
    item_id: Optional[int] = None


class NotificationResponse(BaseModel):
    id: int
    type: str
    title: str
    body: str
    data: Optional[dict[str, Any]] = None
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None
    order_id: Optional[int] = None
    bill_id: Optional[int] = None
    offer_id: Optional[int] = None

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    total: int
    unread_count: int
    items: list[NotificationResponse]

from pydantic import BaseModel, ConfigDict, Field, EmailStr
from datetime import datetime
import uuid
from typing import List, Optional, TypedDict, NotRequired
from ..auth.auth_schema import UserModel


class NotifyData(TypedDict):
    nid: uuid.UUID
    title: str
    message: str 
    timestamp: datetime 
    isRead: bool
    sender_id: uuid.UUID 
    receiver_id: uuid.UUID
    sender: NotRequired[UserModel] 
    receiver: NotRequired[UserModel]

class UserEditModel(BaseModel):
    firstname: str | None = None
    lastname: str | None = None
    email: EmailStr | None = None
    phone: str | None = Field(min_length=11, max_length=11, default=None)

class NotificationModel(BaseModel):
    nid: uuid.UUID
    title: str
    message: str 
    timestamp: datetime 
    isRead: bool
    sender_id: uuid.UUID 
    receiver_id: uuid.UUID
    sender: Optional[UserModel] 
    receiver: Optional[UserModel]

    model_config = ConfigDict(
        from_attributes=True
    )

class ListNotificationModel(BaseModel):
    notifications: List[NotificationModel]

    model_config = ConfigDict(
        from_attributes=True
    )
    
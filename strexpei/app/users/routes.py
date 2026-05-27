from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from ..auth.dependencies import AccessTokenBearer, get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.session_ini import get_session
from .user_schema import UserEditModel, NotificationModel, ListNotificationModel
from ..auth.service import AuthService
from ..db.models import User
from .service import UserService
import uuid

user_router = APIRouter()
auth_service = AuthService()
user_service = UserService()



@user_router.get('/fetch_current_user')
async def current_user(user: dict = Depends(get_current_user)):
    return user

@user_router.patch('/edit_details')
async def update_userinfo(update_info: UserEditModel, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    update_info_dict = update_info.model_dump(exclude_unset=True, exclude_none=True, exclude_defaults=True)

    update_user = await auth_service.update_user(uid=user.uid, user_data=update_info_dict, session=session)

    return update_user

@user_router.patch('/notifications/{notification_id}/read')
async def update_is_read(notification_id: uuid.UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):

    update_isread = await user_service.update_notification(nid=notification_id, update_notify={'isRead': True} ,session=session)

    return JSONResponse(
        content={
            "message":f'is read {True}'
        },
        status_code=status.HTTP_200_OK
    )

@user_router.get('/notifications', response_model=ListNotificationModel, status_code=status.HTTP_200_OK)
async def get_notification(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):

    notify = await user_service.get_user_notifications(receiver_id=user.uid, session=session)

    if not notify:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No notification")
    
    return {"notifications":[NotificationModel.model_validate(notify)]}


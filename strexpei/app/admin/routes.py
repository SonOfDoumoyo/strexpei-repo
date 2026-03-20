from fastapi import APIRouter, Depends, status
from .service import AdminService
from ..db.session_ini import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from ..auth.dependencies import (
    AccessTokenBearer,
    RefreshTokenBearer,
    get_current_user,
    RoleChecker
)
from ...errors import (
    NoExistingUser
)
from .admin_schema import AllUsersModel, ListUsersModel
from typing import List


admin_service = AdminService()
admin_role = RoleChecker(['admin'])
admin_router = APIRouter()

@admin_router.get('/get_all_users',dependencies=[Depends(admin_role)],response_model=ListUsersModel, status_code=status.HTTP_200_OK)
async def get_users(session: AsyncSession = Depends(get_session)):
    users = await admin_service.get_all_users(session)
    
    if not users:
        users = 'No users yet'
        
    return {"users":[AllUsersModel.model_validate(users)]}


@admin_router.post('/suspend_account')
async def account_suspension():
    pass

@admin_router.delete('/delete_account')
async def delete_user():
    pass

@admin_router.delete('/delete_accounts')
async def delete_users():
    pass
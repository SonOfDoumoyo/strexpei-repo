from fastapi import Request, status, Depends
from ..db.models import User
from fastapi.exceptions import HTTPException
from fastapi.security import HTTPBearer
from fastapi.security.http import HTTPAuthorizationCredentials
from ..auth.utils import decode_token
from ..auth.redis import token_in_blocklist
from ..db.session_ini import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from .service import AuthService
from typing import List, Any, Dict
from ..admin.admin_schema import AllUsersModel
from ...errors import AccountNotVerified, InsufficientPermission, ExpiredToken, InvalidAuthorizationCredentials, RefreshTokenRequired, AccessTokenRequired, InvalidToken, RevokedToken, CompanyTokenRequired, InactiveAccount, AccountBannedError, AccountDeletedError, AccountPendingError, AccountSuspendedError

auth_service = AuthService()


class AccessTokenBearer:
    """Reads access token from Authorization: Bearer <token>"""
    async def __call__(self, request: Request) -> Dict[str, Any]:
        auth = request.headers.get("Authorization")
        if not auth or not auth.lower().startswith("bearer"):
            print("Aythorization:", request.headers.get("Authorization"))
            raise HTTPException(status_code=401, detail="Missing bearer token")
        
        token = auth.split(" ", 1)[1].strip()
        data = decode_token(token)

        if data.get("type") != "access":
            raise AccessTokenRequired()

        return data

class RefreshTokenBearer:
    """Reads refresh token form HttpOnly cookie"""
    async def __call__(self, request: Request) -> Dict[str, Any]:
        token = request.cookies.get("refresh_token")
        if not token:
            print("Authorization:", request.cookies.get("refresh_token"))
            raise HTTPException(status_code=401, detail="Missing refresh cookie")
        
        data = decode_token(token)
        if data.get("type") != "refresh":
            raise RefreshTokenRequired()
        return data
    

async def get_current_user(token_details: dict = Depends(AccessTokenBearer()), session: AsyncSession = Depends(get_session)):
    
    user_id = token_details['user']['user_uid']
    user = await auth_service.get_user_by_uid(user_id, session)
    
    return AllUsersModel.model_validate(user)

async def require_session(request: Request):
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    #validates session-id 
    return refresh_token



class AccountStatus:

    async def __call__(self, current_user: User = Depends(get_current_user)):

        if current_user.status == "suspended":
            raise AccountSuspendedError()
        
        elif current_user.status == "deleted":
            raise AccountDeletedError()
        
        elif current_user.status == "banned":
            raise AccountBannedError()
        
        elif current_user.status == "pending":
            raise AccountPendingError()

    
class RoleChecker:
    
    def __init__(self, allowed_roles: List[str]) -> None:
        self.allowed_roles = allowed_roles
        
    async def __call__(self, current_user: User = Depends(get_current_user)) -> bool:
    
        if not current_user.verified:
            raise AccountNotVerified()
        if current_user.role in self.allowed_roles:
            return True
            
        raise InsufficientPermission()
  
       
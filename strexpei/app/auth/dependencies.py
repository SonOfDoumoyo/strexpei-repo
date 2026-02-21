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
from typing import List, Any
from ...errors import AccountNotVerified, InsufficientPermission, ExpiredToken, InvalidAuthorizationCredentials, RefreshTokenRequired, AccessTokenRequired, InvalidToken, RevokedToken, CompanyTokenRequired, InactiveAccount, AccountBannedError, AccountDeletedError, AccountPendingError, AccountSuspendedError

auth_service = AuthService()

class TokenBearer(HTTPBearer):
    
    #setting auto error to True
    def __init__(self, auto_error=True):
        super().__init__(auto_error=auto_error)
    
    #setting the call function
    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials | None:
        
        
        creds = await super().__call__(request)
        
        if not creds:
            raise InvalidAuthorizationCredentials()
        
        token = creds.credentials
        token_data = self.token_valid(token)
        
        if not token_data:
            raise InvalidToken()
        
        if await token_in_blocklist(token_data['jti']):
            raise RevokedToken()
            
        self.verify_token_data(token_data)
        
        return token_data
            
    
    #checks if the token is a valid one
    def token_valid(self, token: str) -> Any:
        token_data = decode_token(token)
        
        return token_data if token_data is not None else False
     
    #verifies the token data
    def verify_token_data(self, token_data):
        raise NotImplementedError('Please overide this method in child class')
        
class AccessTokenBearer(TokenBearer):
    
    def verify_token_data(self, token_data: dict) ->None:
        if token_data['refresh']:
            raise AccessTokenRequired()
            

class RefreshTokenBearer(TokenBearer):
    
    def verify_token_data(self, token_data: dict) ->None:
        if not token_data['refresh']:
            raise RefreshTokenRequired()


class CompanyTokenBearer(TokenBearer):
    
    def verify_token_data(self, token_data: dict) ->None:
        if not token_data['company']:
            raise CompanyTokenRequired()
    

async def get_current_user(token_details: dict = Depends(AccessTokenBearer()), session: AsyncSession = Depends(get_session)):
    
    user_id = token_details['user']['user_uid']
    user = await auth_service.get_user_by_uid(user_id, session)
    
    return user

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
  
       
import logging
from datetime import timedelta, datetime, timezone
import jwt
from ...config import Config
import uuid
import argon2
import json
from passlib.context import CryptContext
from itsdangerous import URLSafeTimedSerializer
from .redis import redis_client
from .auth_schema import UserModel
from ...errors import(
    InvalidToken,
    RefreshTokenRequired,
    RefreshTokenExpired,
    TokenMisMatch,
    ExpiredToken
)

ACCESS_TOKEN_EXPIRY = 3600

#creating a hash type of argon2
passwd_context = CryptContext(
    schemes=['argon2'],
    deprecated="auto"
)

#here we hash the password
def generate_password_hash(password: str) -> str:
    hash = passwd_context.hash(password)
    
    return hash

#verify login password if matches the hashed
def verify_password(password: str, hash: str) -> bool:
    return passwd_context.verify(password, hash)


#creating an access token with user data
def create_access_token(user_data: dict, expiry: timedelta = None, refresh:bool=False):
    
    #payload to store info needed for token
    payload={}
    
    now = datetime.now(timezone.utc)
    #setting an expiry datetime if expiry is None
    if expiry is None:
        expiry = timedelta(seconds=ACCESS_TOKEN_EXPIRY)
    
    new_expiry = expiry + now
    
    #storing the payload data
    payload['user']= user_data
    payload['exp'] = int(new_expiry.timestamp())
    payload['iat'] = int(now.timestamp())
    payload['jti'] = str(uuid.uuid4())
    payload['type'] = "access"
    payload['refresh'] = refresh
    
    #encoding the information and assigning it to variable token
    token = jwt.encode(
        payload=payload,
        key=Config.JWT_SECRET_KEY,
        algorithm=Config.JWT_ALGORITHM
    )
    return token



def create_refresh_token(user_data: dict, expiry: timedelta = None, refresh:bool=False):
    
    #payload to store info needed for token
    payload={}
    
    now = datetime.now(timezone.utc)
    #setting an expiry datetime if expiry is None
    if expiry is None:
        expiry = timedelta(seconds=ACCESS_TOKEN_EXPIRY)
    
    new_expiry = expiry + now
    jti = user_data['user_uid']
    #storing the payload data
    payload['user_data']= user_data
    payload['exp'] = int(new_expiry.timestamp())
    payload['iat'] = int(now.timestamp())
    payload['jti'] = str(uuid.uuid4())
    payload['type'] = 'refresh'
    payload['refresh'] = refresh
    
    #encoding the information and assigning it to variable token
    token = jwt.encode(
        payload=payload,
        key=Config.JWT_SECRET_KEY,
        algorithm=Config.JWT_ALGORITHM
    )
    return token, jti, payload



def create_company_token(company_data: dict, expiry: timedelta = None, refresh:bool=False):
    
    #payload to store info needed for token
    payload={}
    
    now = datetime.utcnow()
    #setting an expiry datetime if expiry is None
    if expiry is None:
        expiry = timedelta(seconds=ACCESS_TOKEN_EXPIRY)
    
    new_expiry = expiry + now
    
    #storing the payload data
    payload['company']= company_data
    payload['exp'] = int(new_expiry.timestamp())
    payload['iat'] = int(now.timestamp())
    payload['jti'] = str(uuid.uuid4())
    payload['type'] = "access"
    payload['refresh'] = refresh
    
    #encoding the information and assigning it to variable token
    token = jwt.encode(
        payload=payload,
        key=Config.JWT_SECRET_KEY,
        algorithm=Config.JWT_ALGORITHM
    )
    return token



def create_company_refresh_token(company_data: dict, expiry: timedelta = None, refresh:bool=False):
    
    #payload to store info needed for token
    payload={}
    
    now = datetime.utcnow()
    #setting an expiry datetime if expiry is None
    if expiry is None:
        expiry = timedelta(seconds=ACCESS_TOKEN_EXPIRY)
    
    new_expiry = expiry + now
    jti = company_data['company']
    #storing the payload data
    payload['company']= company_data
    payload['exp'] = int(new_expiry.timestamp())
    payload['iat'] = int(now.timestamp())
    payload['jti'] = str(uuid.uuid4())
    payload['type'] = 'refresh'
    payload['refresh'] = refresh
    
    #encoding the information and assigning it to variable token
    token = jwt.encode(
        payload=payload,
        key=Config.JWT_SECRET_KEY,
        algorithm=Config.JWT_ALGORITHM
    )
    return token, jti, payload



def decode_token(token: str) -> dict:
    
    #decodes the token to get user details
    try:
        token_data = jwt.decode(
            jwt=token,
            key=Config.JWT_SECRET_KEY,
            algorithms=[Config.JWT_ALGORITHM]
        )
    
        return token_data
        
    except jwt.ExpiredSignatureError:
        raise ExpiredToken()
        
    except jwt.InvalidTokenError:
        raise InvalidToken()


async def refresh_access_token(user: UserModel, token_data: dict, device=str):
    try:
        payload = token_data
        if payload.get("type") != "refresh":
            raise RefreshTokenRequired()
            
        user_uid = payload['user_data']['user_uid']
        key = f"refresh:user:{user_uid}:device:{device}"
        
        #check redis fpr refresh token
        redis_data = await redis_client.get(key)
        
        if not redis_data:
            
            raise RefreshTokenExpired()
            
        #Optional: verify jti matches
        stored_payload = json.loads(redis_data)
        if stored_payload.get("jti") != payload.get("jti"):
            raise TokenMisMatch()
        
        access_data ={
                "email":user.email,
                "user_uid":payload.get('user_uid'),
                'role':user.role,
                "created_at":user.created_at.isoformat(),
        }
        if payload.get('role') == "admin":
            access_data["admin"] = "all access"
        new_access_token = create_access_token(user_data=access_data)
        return new_access_token
        
    except Exception as e:
        print(f'[DEBUG]: {e}')
        raise InvalidToken()
            

#serializer for fast token
serializer = URLSafeTimedSerializer(
    secret_key=Config.JWT_SECRET_KEY,
    salt="email_configuration"
) 


def create_url_safe_token(data: dict):
    token = serializer.dumps(data)
    
    return token


def decode_url_safe_token(token: str):
    
    try:
        token_data = serializer.loads(token)
        return token_data

    except Exception as e:
        logging.error(str(e))
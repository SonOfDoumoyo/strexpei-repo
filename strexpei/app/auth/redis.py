from redis.asyncio import Redis as aioredis
from ...config import Config
import json



JTI_EXPIRY = 3600
MAX_ATTEMPTS = 5

#gets the url from confog
redis_client = aioredis.from_url(Config.REDIS_URL)

async def add_jti_to_blocklist(jti: str) -> None:
    #adds token to blocklist
    await redis_client.set(
        name=jti,
        value="",
        ex=JTI_EXPIRY
    )
    
async def token_in_blocklist(jti: str) -> bool:
    #checks if token is in blocklist
    jti =await redis_client.get(jti)
    
    return jti is not None
    

"""async def save_otp(user_email: str, otp: str, expiry_seconds: int=45):
    key = f"otp:{user_email}"
    
    await redis_client.set(key, otp, ex=expiry_seconds)
  
    
async def verify_otp(user_email: str, otp_input: str) -> bool:
    key = f"otp:{user_email}"
    stored_otp = await redis_client.get(key)
    if not stored_otp:
        return False
    
    return stored_otp == otp_input"""
    
    
async def save_password_reset_otp(user_email: str, otp: str, expiry_seconds: int = 60):
    key = f"otp:reset:{user_email}"
    
    await redis_client.hset(key, mapping={"otp": otp, "attempts":"0"})
    await redis_client.expire(key, expiry_seconds)

    

async def verify_password_reset_otp(user_email: str, otp_input: str):
    key = f"otp:reset:{user_email}"

    otp, attempts = await redis_client.hmget(key, "otp", "attempts")

    if not otp:
        return False, "OTP expired or invalid"
    otp = otp.decode('utf-8').strip()
    
    if not otp:
        return False, "OTP expired or invalid"

    attempts = int(attempts) if attempts else 0
    
    if attempts >= MAX_ATTEMPTS:
        await redis_client.delete(key)
        return False, "Maximum OTP attempts exceeded"

    if str(otp_input).strip() != str(otp).strip():
        await redis_client.hincrby(key, "attempts", 1)
        return False, "Invalid OTP"

    await redis_client.delete(key)
    return True, "OTP verified"
    

async def store_refresh_token(user_id:str, value, device:str):
    
    key = f"refresh:user:{user_id}:device:{device}"
    value = json.dumps(value)
    await redis_client.set(
        key,
        value,
        ex=7 * 24 * 60 * 60
    )
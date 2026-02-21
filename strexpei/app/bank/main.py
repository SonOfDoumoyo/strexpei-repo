import base64
import uuid
import httpx
from fastapi import APIRouter, HTTPException
from ...config import Config


monnify_router = APIRouter()

API_KEY = Config.MONNIFY_API_KEY
SECRET_KEY = Config.MONNIFY_SECRET_KEY
BASE_URL = Config.MONNIFY_BASE_URL


# 🔐 AUTH
async def get_access_token():
    import httpx
    credentials = f"{API_KEY}:{SECRET_KEY}"
    encoded = base64.b64encode(credentials.encode()).decode()

    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{BASE_URL}/api/v1/auth/login",
            headers={
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/json"
            }
        )

    data = res.json()
    if not data.get("requestSuccessful"):
        print(res.text)
        raise HTTPException(status_code=400, detail="Monnify auth failed")

    return data["responseBody"]["accessToken"]
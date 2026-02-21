from fastapi import APIRouter
from fastapi.exceptions import HTTPException
from .main import get_access_token
import httpx
from ...config import Config

BASE_URL = Config.MONNIFY_BASE_URL

monnify_router = APIRouter()

@monnify_router.get("/verify-account/{account_number}/{bank_code}")
async def verify_account(account_number: str, bank_code: str):
    token = await get_access_token()

    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{BASE_URL}/api/v1/disbursements/account/validate",
            params={
                "accountNumber": account_number,
                "bankCode": bank_code
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

    data = res.json()
    if not data.get("requestSuccessful"):
        raise HTTPException(status_code=400, detail=data)

    return data["responseBody"]

@monnify_router.get('/account_status')
async def status_of_accout():
    pass
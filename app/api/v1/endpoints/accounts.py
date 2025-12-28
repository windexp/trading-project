from fastapi import APIRouter, Depends
from typing import List
import json
from app.core.config import settings
from pydantic import BaseModel

router = APIRouter()

class AccountResponse(BaseModel):
    account_no: str
    # Do not expose app_key/secret

@router.get("/", response_model=List[AccountResponse])
def get_accounts():
    try:
        accounts = json.loads(settings.ACCOUNTS)
        return [{"account_no": acc["account_no"]} for acc in accounts]
    except Exception:
        return []

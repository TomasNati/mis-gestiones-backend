import hmac
import os

from fastapi import Header, HTTPException


def require_api_key(x_api_key: str = Header(...)) -> None:
    secret = os.getenv("BACKEND_SHARED_SECRET")
    if not secret or not hmac.compare_digest(x_api_key, secret):
        raise HTTPException(status_code=401, detail={"error": "Unauthorized", "message": "invalid or missing X-API-Key"})

import os
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-Api-Key", auto_error=False)


async def require_api_key(api_key: str = Security(API_KEY_HEADER)):
    """
    Dependency to verify the `X-Api-Key` header against the `INTERNAL_API_KEY` environment variable.
    """
    expected_api_key = os.getenv("INTERNAL_API_KEY")
    if not expected_api_key:
        raise HTTPException(
            status_code=500, detail="INTERNAL_API_KEY is not configured on the server."
        )
    if not api_key or api_key != expected_api_key:
        raise HTTPException(status_code=403, detail="Invalid or missing API key.")
    return api_key

from fastapi import Header, HTTPException
import os


def require_api_key(x_api_key: str = Header(None)) -> None:
    """
    Simple internal API key guard. Provide `x-api-key` header matching INTERNAL_API_KEY.
    """
    expected = os.getenv("INTERNAL_API_KEY")
    if not expected:
        raise HTTPException(status_code=424, detail="INTERNAL_API_KEY is not configured.")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
    return None

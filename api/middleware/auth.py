from fastapi import Request, HTTPException, Depends
from fastapi.security import APIKeyHeader
from config import get_config

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(request: Request, api_key: str = Depends(API_KEY_HEADER)):
    config = get_config()
    
    # If no api_keys configured, pass through (dev mode)
    if not config.api_keys:
        return
        
    # Check query params for SSE/EventSource support where custom headers are unsupported
    if not api_key:
        api_key = request.query_params.get("api_key")
    
    if api_key not in config.api_keys:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from collections import defaultdict
from database.redis_client import RedisManager

class RedisRateLimiter:
    def __init__(self):
        self.redis = RedisManager()
        self.limits = {
            '/chat': (60, 60),       # 60 requests per 60 seconds
            '/admin': (100, 60),     # 100 requests per 60 seconds
            '/chat/stream': (20, 60), # 20 stream requests per 60 seconds
        }
        # In-memory fallback
        self.fallback_log = defaultdict(list)

    async def check_rate_limit(self, request: Request, identifier: str) -> bool:
        endpoint = request.url.path
        
        # Match prefix if exact not found
        limit, window = self.limits.get(endpoint, None) or next(
            (v for k, v in self.limits.items() if endpoint.startswith(k)), (100, 60)
        )
        
        if self.redis.client:
            try:
                key = f"rate:{identifier}:{endpoint}"
                current = self.redis.client.get(key)
                if current is None:
                    self.redis.client.setex(key, window, 1)
                    return True
                
                if int(current) >= limit:
                    return False
                
                self.redis.client.incr(key)
                return True
            except Exception:
                pass # Fall back to in-memory on error

        # In-memory fallback
        current_time = time.time()
        self.fallback_log[identifier] = [t for t in self.fallback_log[identifier] if current_time - t < window]
        
        if len(self.fallback_log[identifier]) >= limit:
            return False
            
        self.fallback_log[identifier].append(current_time)
        return True

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.limiter = RedisRateLimiter()

    async def dispatch(self, request: Request, call_next):
        # identifier = user_id if user_id else session_id
        # Note: request body is not easily accessible in middleware without breaking it, 
        # so we'll use headers for user_id/session_id
        session_id = request.headers.get("x-session-id", request.client.host if request.client else "unknown")
        user_id = request.headers.get("x-user-id", "")
        identifier = user_id if user_id else session_id
        
        allowed = await self.limiter.check_rate_limit(request, identifier)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "detail": "Too many requests"}
            )
            
        return await call_next(request)

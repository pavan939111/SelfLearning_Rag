import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from collections import defaultdict

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_log = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        session_id = request.headers.get("x-session-id", request.client.host if request.client else "unknown")
        current_time = time.time()
        
        self.request_log[session_id] = [t for t in self.request_log[session_id] if current_time - t < self.window_seconds]
        
        if len(self.request_log[session_id]) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "detail": f"Max {self.max_requests} requests per minute"}
            )
            
        self.request_log[session_id].append(current_time)
        return await call_next(request)

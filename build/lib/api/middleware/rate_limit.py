"""Redis-based rate limiting middleware."""

import time
import redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


# Tier-based limits (requests per minute)
TIER_LIMITS = {
    "free": 10,
    "pro": 60,
    "studio": 200,
    "enterprise": 1000,
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_url: str = "redis://localhost:6379/0", default_limit: str = "60/minute"):
        super().__init__(app)
        try:
            self.redis = redis.from_url(redis_url)
            self.redis.ping()
        except Exception:
            self.redis = None
        self.default_limit = int(default_limit.split("/")[0])

    async def dispatch(self, request: Request, call_next):
        if self.redis is None:
            return await call_next(request)

        # Skip rate limiting for health checks
        if request.url.path.startswith("/api/v1/health"):
            return await call_next(request)

        # Use IP as rate limit key for unauthenticated requests
        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{client_ip}:{int(time.time()) // 60}"

        try:
            current = self.redis.incr(key)
            if current == 1:
                self.redis.expire(key, 60)

            if current > self.default_limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again later."},
                )
        except Exception:
            pass  # Fail open if Redis is down

        return await call_next(request)

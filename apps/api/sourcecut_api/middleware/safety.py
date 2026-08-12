from __future__ import annotations

import re
import time
import uuid
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

REQUEST_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")


class RequestSafetyMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: object,
        *,
        max_body_bytes: int = 1_000_000,
        general_requests_per_minute: int = 120,
        expensive_requests_per_minute: int = 30,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.max_body_bytes = max_body_bytes
        self.general_limit = general_requests_per_minute
        self.expensive_limit = expensive_requests_per_minute
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get("X-Request-ID", "")
        if not REQUEST_ID.fullmatch(correlation_id):
            correlation_id = str(uuid.uuid4())
        content_length = request.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > self.max_body_bytes:
                    return self._response(
                        413, "Request body exceeds the 1 MB limit", correlation_id
                    )
            except ValueError:
                return self._response(400, "Content-Length must be an integer", correlation_id)
        retry_after = self._rate_limit(request)
        if retry_after is not None:
            response = self._response(429, "Request rate limit exceeded", correlation_id)
            response.headers["Retry-After"] = str(retry_after)
            return response
        response = await call_next(request)
        self._secure_headers(response, correlation_id)
        return response

    def _rate_limit(self, request: Request) -> int | None:
        path = request.url.path
        expensive = any(
            marker in path for marker in ("/research", "/search", "/exports", "/regenerate")
        )
        limit = self.expensive_limit if expensive else self.general_limit
        host = request.client.host if request.client else "unknown"
        key = f"{host}:{'expensive' if expensive else 'general'}"
        now = time.monotonic()
        with self._lock:
            bucket = self._requests[key]
            while bucket and now - bucket[0] >= 60:
                bucket.popleft()
            if len(bucket) >= limit:
                return max(1, int(60 - (now - bucket[0])))
            bucket.append(now)
        return None

    @staticmethod
    def _response(status: int, detail: str, correlation_id: str) -> JSONResponse:
        response = JSONResponse(status_code=status, content={"detail": detail})
        RequestSafetyMiddleware._secure_headers(response, correlation_id)
        return response

    @staticmethod
    def _secure_headers(response: Response, correlation_id: str) -> None:
        response.headers["X-Request-ID"] = correlation_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")

"""
middleware.py — request latency logging middleware.

Adds an X-Process-Time-Ms response header and emits a structured log line
for every request. This gives measurable per-request latency without any
external telemetry dependency.
"""
import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class LatencyLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)

        response.headers["X-Process-Time-Ms"] = str(duration_ms)

        logger.info(
            "method=%s path=%s status=%d latency_ms=%.2f",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response

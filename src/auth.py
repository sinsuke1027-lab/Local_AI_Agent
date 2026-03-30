"""auth.py - FastAPI API Key認証ミドルウェア"""

import os
import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

API_KEY = os.getenv("FASTAPI_API_KEY", "")

# 認証をスキップするパス
SKIP_AUTH_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """X-API-Key ヘッダーによる認証ミドルウェア。"""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in SKIP_AUTH_PATHS:
            return await call_next(request)

        # API Keyが未設定の場合は認証スキップ（開発環境用）
        if not API_KEY:
            logger.warning("FASTAPI_API_KEY is not set — authentication disabled")
            return await call_next(request)

        provided_key = request.headers.get("X-API-Key", "")
        if provided_key != API_KEY:
            logger.warning(
                "Invalid API Key from %s: %s",
                request.client.host if request.client else "unknown",
                request.url.path,
            )
            return JSONResponse(status_code=401, content={"detail": "Invalid API Key"})

        return await call_next(request)

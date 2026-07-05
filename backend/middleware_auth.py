"""FastAPI middleware: API token + BYOK headers."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from auth import verify_token
from config import config
from llm_context import RequestKeys, set_request_keys

PUBLIC_PATHS = {"/api/health", "/api/auth/login", "/docs", "/openapi.json", "/redoc"}


class AuthAndKeysMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path.startswith("/api/") and path not in PUBLIC_PATHS:
            if config.api_auth_secret:
                auth = request.headers.get("authorization", "")
                token = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else ""
                if not verify_token(token):
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid or missing API token"},
                    )

        llm_key = request.headers.get("x-llm-api-key", "").strip()
        if llm_key:
            set_request_keys(RequestKeys(
                llm_api_key=llm_key,
                llm_base_url=request.headers.get("x-llm-base-url", "").strip() or config.llm_base_url,
                llm_model=request.headers.get("x-llm-model", "").strip() or config.llm_model,
                tavily_api_key=request.headers.get("x-tavily-api-key", "").strip() or None,
            ))
        else:
            set_request_keys(None)

        return await call_next(request)

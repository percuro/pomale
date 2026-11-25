"""Error responses with a stable, machine-readable code.

Every error the API returns looks like {"detail": "<English message>", "code": "<area.reason>"},
sometimes with extra fields (e.g. "server" for a sync conflict, "errors" for invalid input).
Clients translate by `code` and fall back to `detail`; the message text may change, the code does not.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        headers: dict[str, str] | None = None,
        **extra: Any,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers
        self.extra = extra


def error_response(status_code: int, code: str, message: str, headers=None, **extra: Any) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder({"detail": message, "code": code, **extra}),
        headers=headers,
    )


async def _app_error(_request: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message, exc.headers, **exc.extra)


async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Framework errors (unknown route, wrong method): generic code per status
    message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    return error_response(exc.status_code, f"http.{exc.status_code}", message, getattr(exc, "headers", None))


async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {
            "field": ".".join(str(part) for part in error.get("loc", ()) if part not in ("body", "query", "path")),
            "type": error.get("type", ""),
            "message": error.get("msg", ""),
        }
        for error in exc.errors()
    ]
    return error_response(422, "validation", "Invalid input", errors=errors)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)

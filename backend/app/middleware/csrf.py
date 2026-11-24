import re
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import csrf_enabled, get_allowed_origins

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_HEADER = "X-Habit-CSRF"
# iOS shortcut: authenticates with a bearer key only and sends neither cookie nor Origin
SHORTCUT_PATH = re.compile(r"^(/api)?/v1/habits/\d+/days/today$")


def _is_shortcut_request(request: Request) -> bool:
    return (
        request.method == "PUT"
        and SHORTCUT_PATH.match(request.url.path) is not None
        and request.headers.get("Authorization", "").lower().startswith("bearer ")
        and "cookie" not in request.headers
    )


async def enforce_csrf(request: Request, call_next):
    if not csrf_enabled() or request.method not in UNSAFE_METHODS:
        return await call_next(request)
    if _is_shortcut_request(request):
        return await call_next(request)

    if request.headers.get(CSRF_HEADER) != "1":
        return JSONResponse(status_code=403, content={"detail": "Ungültige Anfrageherkunft"})

    origin = request.headers.get("Origin")
    if not origin:
        referer = request.headers.get("Referer")
        if referer:
            parsed = urlparse(referer)
            origin = f"{parsed.scheme}://{parsed.netloc}"
    trusted_origins = set(get_allowed_origins())
    if not origin or origin.rstrip("/") not in trusted_origins:
        return JSONResponse(status_code=403, content={"detail": "Ungültige Anfrageherkunft"})

    return await call_next(request)

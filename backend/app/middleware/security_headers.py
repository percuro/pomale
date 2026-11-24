"""Security headers for every response (previously set by the frontend nginx)."""

from fastapi import Request

from app.config import get_public_url

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; connect-src 'self'; font-src 'self'; manifest-src 'self'; "
    "worker-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; "
    "frame-ancestors 'none'"
)

STATIC_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    for name, value in STATIC_HEADERS.items():
        response.headers.setdefault(name, value)
    try:
        https = get_public_url().startswith("https://")
    except Exception:  # noqa: BLE001 - missing config is reported at startup
        https = False
    if https:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response

from fastapi import Request

from app.errors import error_response
from app.services.data_export import MAX_IMPORT_BYTES

IMPORT_PATH_SUFFIX = "/v1/import"
# Everything except an import is small JSON; 1 MB leaves room for long notes and many habits
MAX_BODY_BYTES = 1024 * 1024


async def limit_body(request: Request, call_next):
    """Refuse a large body before it is read: FastAPI reads and parses a JSON body before any
    dependency runs. The server enforces Content-Length, so a body cannot be longer. A body sent
    in chunks has no length to check and is refused; clients and reverse proxies send a length."""
    is_import = request.method == "POST" and request.url.path.endswith(IMPORT_PATH_SUFFIX)
    length = request.headers.get("Content-Length")
    if is_import:
        if length is None or not length.isdigit() or int(length) > MAX_IMPORT_BYTES:
            return error_response(413, "import.too_large", "The file is too large (at most 5 MB)")
    elif length is not None:
        if not length.isdigit() or int(length) > MAX_BODY_BYTES:
            return error_response(413, "request.too_large", "The request is too large (at most 1 MB)")
    elif "Transfer-Encoding" in request.headers:
        return error_response(411, "request.length_required", "Send the request with a Content-Length")
    return await call_next(request)

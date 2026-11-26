from fastapi import Request

from app.errors import error_response
from app.services.data_export import MAX_IMPORT_BYTES

IMPORT_PATH_SUFFIX = "/v1/import"


async def limit_import_body(request: Request, call_next):
    """Refuse a large import before its body is read: FastAPI reads and parses a JSON body before
    any dependency runs. The server enforces Content-Length, so a body cannot be longer."""
    if request.method == "POST" and request.url.path.endswith(IMPORT_PATH_SUFFIX):
        length = request.headers.get("Content-Length", "")
        if not length.isdigit() or int(length) > MAX_IMPORT_BYTES:
            return error_response(413, "import.too_large", "The file is too large (at most 5 MB)")
    return await call_next(request)

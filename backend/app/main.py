from fastapi import Depends, FastAPI
from fastapi.openapi.utils import get_openapi
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.dependencies.auth import require_admin, require_user
from app.api.routers.account import router as account_router
from app.api.routers.admin import router as admin_router
from app.api.routers.auth import router as auth_router
from app.api.routers.days import router as days_router
from app.api.routers.export import router as export_router
from app.api.routers.groups import router as groups_router
from app.api.routers.habits import router as habits_router
from app.api.routers.health import router as health_router
from app.api.routers.invitations import router as invitations_router
from app.api.routers.meta import router as meta_router
from app.api.routers.oidc import router as oidc_router
from app.api.routers.pauses import router as pauses_router
from app.api.routers.push import router as push_router
from app.api.routers.setup import router as setup_router
from app.api.routers.shortcuts import public_router as shortcut_public_router
from app.api.routers.shortcuts import router as shortcut_router
from app.config import APP_NAME, api_docs_enabled
from app.errors import install_error_handlers
from app.middleware.body_limit import limit_import_body
from app.middleware.csrf import enforce_csrf
from app.services.auth_service import SESSION_COOKIE_NAME
from app.services.token_service import TOKEN_ROUTES

DESCRIPTION = """
The API behind the pomale web app. Paths in this document are relative to `/api`.

**Authentication.** The web app uses a session cookie. Scripts, iOS shortcuts and home automation
use a personal API key from the account page: `Authorization: Bearer pm_…`. A key can only reach
the operations marked "API key" below, with its scope:

- `read`: days, habits, groups, pauses, history, exports and `GET /v1/today`
- `checkin`: check off, amounts and notes

A key may be limited to some habits; it then sees only those, and history, exports, groups and
pauses need a key for all habits. Requests with a key need no CSRF header.

Guide with examples: https://github.com/percuro/pomale/blob/main/docs/api.md
"""

# Docs pages are not served: the strict Content-Security-Policy allows no CDN scripts. The schema
# is served by the route below, so API_DOCS is read per request.
app = FastAPI(
    title=f"{APP_NAME} API",
    version=__version__,
    description=DESCRIPTION,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.middleware("http")(enforce_csrf)
app.middleware("http")(limit_import_body)
install_error_handlers(app)


# Mounted under /api by app.web: /api/v1/days → /v1/days here
app.include_router(health_router)
# Shortcut route first: /v1/habits/{id}/days/today must not be parsed as a date
app.include_router(shortcut_public_router, prefix="/v1", tags=["shortcut"])
app.include_router(auth_router, prefix="/v1/auth", tags=["auth"])
app.include_router(oidc_router, prefix="/v1/auth/oidc", tags=["oidc"])
app.include_router(setup_router, prefix="/v1/setup", tags=["setup"])
app.include_router(meta_router, prefix="/v1", tags=["meta"])
app.include_router(invitations_router, prefix="/v1/invitations", tags=["invitations"])
protected = [Depends(require_user)]
app.include_router(account_router, prefix="/v1/account", tags=["account"], dependencies=protected)
app.include_router(habits_router, prefix="/v1/habits", tags=["habits"], dependencies=protected)
app.include_router(groups_router, prefix="/v1/groups", tags=["groups"], dependencies=protected)
app.include_router(pauses_router, prefix="/v1/pauses", tags=["pauses"], dependencies=protected)
app.include_router(push_router, prefix="/v1/push", tags=["push"], dependencies=protected)
app.include_router(days_router, prefix="/v1", tags=["days"], dependencies=protected)
app.include_router(shortcut_router, prefix="/v1", tags=["shortcut"], dependencies=protected)
app.include_router(export_router, prefix="/v1", tags=["export"], dependencies=protected)
app.include_router(admin_router, prefix="/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def build_openapi() -> dict:
    if app.openapi_schema is not None:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
    schema["servers"] = [{"url": "/api"}]
    schema.setdefault("components", {})["securitySchemes"] = {
        "session": {"type": "apiKey", "in": "cookie", "name": SESSION_COOKIE_NAME},
        "apiKey": {"type": "http", "scheme": "bearer", "description": "Personal API key (pm_…)"},
    }
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            scope = TOKEN_ROUTES.get((method.upper(), path))
            if scope is None:
                continue
            operation["security"] = [{"session": []}, {"apiKey": [scope]}]
            note = f"API key: scope `{scope}`."
            operation["description"] = f"{operation.get('description', '').strip()}\n\n{note}".strip()
    app.openapi_schema = schema
    return schema


app.openapi = build_openapi


@app.get("/openapi.json", include_in_schema=False)
def openapi_schema() -> dict:
    """The OpenAPI description, for Postman, Bruno, Insomnia or code generators."""
    if not api_docs_enabled():
        raise StarletteHTTPException(404, "Not Found")
    return app.openapi()

from fastapi import Depends, FastAPI

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
from app.api.routers.setup import router as setup_router
from app.api.routers.shortcuts import public_router as shortcut_public_router
from app.api.routers.shortcuts import router as shortcut_router
from app.config import APP_NAME
from app.errors import install_error_handlers
from app.middleware.csrf import enforce_csrf

app = FastAPI(title=f"{APP_NAME} API", version=__version__)
app.middleware("http")(enforce_csrf)
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
app.include_router(days_router, prefix="/v1", tags=["days"], dependencies=protected)
app.include_router(shortcut_router, prefix="/v1", tags=["shortcut"], dependencies=protected)
app.include_router(export_router, prefix="/v1", tags=["export"], dependencies=protected)
app.include_router(admin_router, prefix="/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])

"""ASGI entry point: the API under /api plus the built frontend from FRONTEND_DIST.

Run with: uvicorn app.web:application
"""

import logging
import mimetypes
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app import config
from app.db.database import SessionLocal
from app.main import app as api
from app.middleware.security_headers import add_security_headers
from app.services import setup_service
from app.services.scheduler import ReminderScheduler
from app.services.webpush.keys import ensure_vapid_keys

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(levelname)s:     %(name)s %(message)s",
    )
logger = logging.getLogger("app")
# httpx logs every request with its URL; push endpoints are secrets of the subscribed devices
logging.getLogger("httpx").setLevel(logging.WARNING)

mimetypes.add_type("application/manifest+json", ".webmanifest")

# Files that must always be revalidated so updates (service worker!) reach clients
NO_CACHE_FILES = {"index.html", "sw.js", "registerSW.js", "manifest.webmanifest"}
LONG_CACHE = "public, max-age=31536000, immutable"
ICON_CACHE = "public, max-age=604800"


class SpaStaticFiles(StaticFiles):
    """Static frontend with client-side routing: unknown pages fall back to index.html."""

    async def get_response(self, path: str, scope: Scope):
        served = path
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or self._looks_like_file(path):
                raise
            served = "index.html"
            response = await super().get_response(served, scope)
        name = Path(served).name or "index.html"
        if path in ("", ".") or name in NO_CACHE_FILES:
            response.headers["Cache-Control"] = "no-cache"
        elif served.startswith("assets/"):
            response.headers["Cache-Control"] = LONG_CACHE
        else:
            response.headers["Cache-Control"] = ICON_CACHE
        return response

    @staticmethod
    def _looks_like_file(path: str) -> bool:
        # Missing assets stay 404 instead of returning HTML with status 200
        return path.startswith("assets/") or "." in Path(path).name


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        config.validate()
    except config.ConfigError as exc:
        logger.error("Configuration error: %s", exc)
        raise
    announce_setup_token()
    scheduler = start_reminders()
    try:
        yield
    finally:
        if scheduler is not None:
            await scheduler.stop()


def start_reminders() -> ReminderScheduler | None:
    if not config.push_enabled():
        logger.info("Reminders are turned off (PUSH_ENABLED=false)")
        return None
    db = SessionLocal()
    try:
        ensure_vapid_keys(db)
    except OperationalError:
        logger.warning("Database not migrated yet; reminders stay off until the next start")
        return None
    finally:
        db.close()
    scheduler = ReminderScheduler(SessionLocal)
    scheduler.start()
    return scheduler


def announce_setup_token() -> None:
    db = SessionLocal()
    try:
        needed = setup_service.needs_setup(db)
    except OperationalError:
        logger.warning("Database not migrated yet; run 'alembic upgrade head'")
        return
    finally:
        db.close()
    if not needed:
        return
    token = setup_service.issue_token()
    banner = "=" * 72
    logger.warning(
        "\n%s\nNo account exists yet. Open %s/setup and enter this setup token:\n\n    %s\n\n"
        "The token is valid until the first account is created (a restart issues a new one).\n%s",
        banner,
        config.get_public_url(),
        token,
        banner,
    )


def create_application(frontend_dist: Path | None = None) -> FastAPI:
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    application.middleware("http")(add_security_headers)
    application.mount("/api", api)
    if frontend_dist is not None and (frontend_dist / "index.html").is_file():
        application.mount("/", SpaStaticFiles(directory=frontend_dist, html=True), name="frontend")
    else:
        logger.info("No frontend build found; serving the API only")
    return application


def _default_dist() -> Path | None:
    value = os.getenv("FRONTEND_DIST", "").strip()
    return Path(value) if value else None


application = create_application(_default_dist())

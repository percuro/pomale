from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_database_url

DATABASE_URL = get_database_url()
engine_options: dict = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False, "timeout": 30}

engine = create_engine(DATABASE_URL, **engine_options)


def configure_sqlite(engine_to_configure) -> None:
    """Enforce foreign keys, WAL for concurrent reads, wait on locks."""

    @event.listens_for(engine_to_configure, "connect")
    def _set_pragmas(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        if engine_to_configure.url.database not in (None, "", ":memory:"):
            cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


if DATABASE_URL.startswith("sqlite"):
    configure_sqlite(engine)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

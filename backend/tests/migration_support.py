"""Run Alembic programmatically against a given SQLite file (no alembic.ini logging setup)."""

import os
from pathlib import Path
from unittest import mock

from alembic.config import Config

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parent.parent


def alembic(path: Path, action: str, revision: str) -> None:
    config = Config()
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    with mock.patch.dict(os.environ, {"DATABASE_URL": f"sqlite:///{path}"}):
        getattr(command, action)(config, revision)

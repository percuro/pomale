"""Import a JSON export from stdin into an existing account without habits, groups and pauses.

python -m app.cli.import_account <username> < pomale-alex.json
"""

import argparse
import sys

from pydantic import ValidationError

from app.db.database import SessionLocal
from app.errors import AppError
from app.repositories.auth_repository import AuthRepository
from app.schemas.export import AccountExport
from app.services.data_export import import_account


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a JSON export into an empty account")
    parser.add_argument("username")
    args = parser.parse_args()
    try:
        data = AccountExport.model_validate_json(sys.stdin.read())
    except ValidationError as exc:
        raise SystemExit(f"Not a valid pomale export:\n{exc}") from exc
    db = SessionLocal()
    try:
        user = AuthRepository(db).get_user_by_username(args.username)
        if user is None:
            raise SystemExit(f"Account {args.username.lower()} not found")
        try:
            result = import_account(db, user, data)
        except AppError as exc:
            raise SystemExit(exc.message) from exc
        print(
            f"Imported into {user.username}: {result.habits} habits, {result.checkins} check-ins, "
            f"{result.groups} groups, {result.pauses} pauses, {result.reminders} reminder times."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()

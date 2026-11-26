"""Export one account as JSON to stdout, e.g. to move it to another instance.

python -m app.cli.export_account <username> > pomale-alex.json
"""

import argparse
import json
import sys

from app.db.database import SessionLocal
from app.repositories.auth_repository import AuthRepository
from app.services.data_export import export_account


def main() -> None:
    parser = argparse.ArgumentParser(description="Export an account as JSON (format pomale-export)")
    parser.add_argument("username")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        user = AuthRepository(db).get_user_by_username(args.username)
        if user is None:
            raise SystemExit(f"Account {args.username.lower()} not found")
        data = export_account(db, user)
        json.dump(data.model_dump(mode="json"), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()

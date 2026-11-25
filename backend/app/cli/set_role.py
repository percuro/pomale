"""Emergency exit: change an account's role from the command line, e.g. when no admin can log in.

python -m app.cli.set_role <username> admin|user
"""

import argparse

from app.db.database import SessionLocal
from app.errors import AppError
from app.models.user import ROLES
from app.repositories.auth_repository import AuthRepository
from app.services import audit_service
from app.services.account_service import AccountService


def main() -> None:
    parser = argparse.ArgumentParser(description="Change the role of an account")
    parser.add_argument("username")
    parser.add_argument("role", choices=ROLES)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = AuthRepository(db).get_user_by_username(args.username)
        if user is None:
            raise SystemExit(f"Account {args.username.lower()} not found")
        if args.role != "admin":
            try:
                AccountService(db).ensure_not_last_admin(user)
            except AppError as exc:
                raise SystemExit(exc.message) from exc
        if user.role != args.role:
            audit_service.record(
                db, "admin.role_changed", target=user, commit=False, before=user.role, after=args.role, via="cli"
            )
        user.role = args.role
        db.commit()
        print(f"Account {user.username} is now {user.role}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

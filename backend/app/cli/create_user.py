import argparse
import getpass

from sqlalchemy import func, select

from app.db.database import SessionLocal
from app.errors import AppError
from app.models.user import ROLE_ADMIN, ROLES, User
from app.repositories.auth_repository import AuthRepository
from app.services import audit_service
from app.services.auth_service import MIN_PASSWORD_LENGTH, AuthService


def read_password() -> str:
    password = getpass.getpass(f"Password (at least {MIN_PASSWORD_LENGTH} characters): ")
    confirmation = getpass.getpass("Repeat password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    return password


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an account or reset its password")
    parser.add_argument("username")
    parser.add_argument(
        "--role",
        choices=ROLES,
        help="role of a new account (default: user; the very first account always becomes admin)",
    )
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="set a new password for an existing account (logs out all devices)",
    )
    args = parser.parse_args()
    if args.reset_password and args.role:
        parser.error("--role only applies to new accounts; use app.cli.set_role to change a role")
    password = read_password()

    db = SessionLocal()
    try:
        service = AuthService(AuthRepository(db))
        try:
            if args.reset_password:
                service.set_password(args.username, password)
                target = service.repository.get_user_by_username(args.username)
                audit_service.record(db, "account.password_changed", target=target, via="cli")
                print(f"Password for {args.username.lower()} has been set.")
            else:
                first = (db.scalar(select(func.count()).select_from(User)) or 0) == 0
                role = ROLE_ADMIN if first else (args.role or "user")
                user = service.create_user(args.username, password, role=role)
                audit_service.record(db, "account.created", target=user, via="cli", role=user.role)
                print(f"Account {user.username} ({user.role}) has been created.")
        except AppError as exc:
            raise SystemExit(exc.message) from exc
    finally:
        db.close()


if __name__ == "__main__":
    main()

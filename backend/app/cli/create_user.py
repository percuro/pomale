import argparse
import getpass

from app.db.database import SessionLocal
from app.errors import AppError
from app.repositories.auth_repository import AuthRepository
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
        "--reset-password",
        action="store_true",
        help="set a new password for an existing account (logs out all devices)",
    )
    args = parser.parse_args()
    password = read_password()

    db = SessionLocal()
    try:
        service = AuthService(AuthRepository(db))
        try:
            if args.reset_password:
                service.set_password(args.username, password)
                print(f"Password for {args.username.lower()} has been set.")
            else:
                user = service.create_user(args.username, password)
                print(f"Account {user.username} has been created.")
        except AppError as exc:
            raise SystemExit(exc.message) from exc
    finally:
        db.close()


if __name__ == "__main__":
    main()

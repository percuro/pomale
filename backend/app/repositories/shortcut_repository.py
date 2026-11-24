from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.shortcut_token import ShortcutToken


class ShortcutRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_habit(self, habit_id: int) -> list[ShortcutToken]:
        return list(
            self.db.scalars(select(ShortcutToken).where(ShortcutToken.habit_id == habit_id).order_by(ShortcutToken.id))
        )

    def get_for_habit(self, token_id: int, habit_id: int) -> ShortcutToken | None:
        return self.db.scalars(
            select(ShortcutToken).where(ShortcutToken.id == token_id, ShortcutToken.habit_id == habit_id)
        ).first()

    def get_by_hash(self, token_hash: str) -> ShortcutToken | None:
        return self.db.scalars(select(ShortcutToken).where(ShortcutToken.token_hash == token_hash)).first()

    def add(self, token: ShortcutToken) -> ShortcutToken:
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        return token

    def revoke(self, token: ShortcutToken, now: datetime) -> None:
        if token.revoked_at is None:
            token.revoked_at = now
            self.db.commit()

    def touch(self, token: ShortcutToken, now: datetime) -> None:
        token.last_used_at = now
        self.db.commit()

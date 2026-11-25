from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.push import PushSubscription


class PushRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_user(self, user_id: int) -> list[PushSubscription]:
        return list(
            self.db.scalars(
                select(PushSubscription)
                .where(PushSubscription.user_id == user_id)
                .order_by(PushSubscription.created_at, PushSubscription.id)
            )
        )

    def count_for_user(self, user_id: int) -> int:
        return self.db.scalar(select(func.count()).where(PushSubscription.user_id == user_id)) or 0

    def get_for_user(self, subscription_id: int, user_id: int) -> PushSubscription | None:
        return self.db.scalars(
            select(PushSubscription).where(PushSubscription.id == subscription_id, PushSubscription.user_id == user_id)
        ).first()

    def get_by_endpoint(self, endpoint: str) -> PushSubscription | None:
        return self.db.scalars(select(PushSubscription).where(PushSubscription.endpoint == endpoint)).first()

    def delete_endpoint_for_user(self, endpoint: str, user_id: int) -> None:
        self.db.execute(
            delete(PushSubscription).where(PushSubscription.endpoint == endpoint, PushSubscription.user_id == user_id)
        )

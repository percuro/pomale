from app.errors import AppError
from app.models.habit import HabitGroup
from app.repositories.habit_repository import HabitRepository
from app.schemas.habit import GroupCreate, GroupOrder, GroupUpdate


class GroupService:
    def __init__(self, repository: HabitRepository):
        self.repository = repository

    def get(self, group_id: int, user_id: int) -> HabitGroup:
        group = self.repository.get_group(group_id, user_id)
        if group is None:
            raise AppError(404, "group.not_found", "Group not found")
        return group

    def _check_name(self, user_id: int, name: str, except_id: int | None = None) -> None:
        if self.repository.group_name_taken(user_id, name, except_id):
            raise AppError(409, "group.name_taken", "A group with this name exists already")

    def create(self, user_id: int, data: GroupCreate) -> HabitGroup:
        self._check_name(user_id, data.name)
        group = HabitGroup(user_id=user_id, name=data.name, sort_order=self.repository.next_group_sort_order(user_id))
        self.repository.add_object(group)
        return group

    def update(self, group_id: int, user_id: int, data: GroupUpdate) -> HabitGroup:
        group = self.get(group_id, user_id)
        self._check_name(user_id, data.name, except_id=group.id)
        group.name = data.name
        self.repository.commit()
        return group

    def delete(self, group_id: int, user_id: int) -> None:
        # Its habits stay, without a group (ON DELETE SET NULL)
        self.repository.delete_object(self.get(group_id, user_id))

    def reorder(self, user_id: int, data: GroupOrder) -> list[HabitGroup]:
        if len(set(data.ids)) != len(data.ids):
            raise AppError(422, "group.order_duplicate", "A group is listed twice")
        groups = {g.id: g for g in self.repository.list_groups(user_id)}
        if any(group_id not in groups for group_id in data.ids):
            raise AppError(404, "group.not_found", "Group not found")
        rest = [g for g in groups.values() if g.id not in set(data.ids)]
        for position, group in enumerate([groups[i] for i in data.ids] + rest, start=1):
            group.sort_order = position
        self.repository.commit()
        return self.repository.list_groups(user_id)

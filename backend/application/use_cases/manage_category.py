from backend.domain.ports.category_repository import CategoryRepository
from backend.domain.value_objects.category import Category


class ListAllCategories:
    def __init__(self, repo: CategoryRepository) -> None:
        self._repo = repo

    def execute(self, user_id: int) -> list[Category]:
        return self._repo.find_all(user_id)


class CreateCategory:
    def __init__(self, repo: CategoryRepository) -> None:
        self._repo = repo

    def execute(self, name: str, color: str | None = None, *, user_id: int) -> int:
        return self._repo.save(name, color=color, user_id=user_id)


class EditCategory:
    def __init__(self, repo: CategoryRepository) -> None:
        self._repo = repo

    def execute(
        self, category_id: int, name: str, color: str | None = None, *, user_id: int
    ) -> int:
        return self._repo.save(name, category_id, color=color, user_id=user_id)


class DeleteCategory:
    def __init__(self, repo: CategoryRepository) -> None:
        self._repo = repo

    def execute(self, category_id: int, user_id: int) -> None:
        self._repo.delete(category_id, user_id)


class HardDeleteCategory:
    def __init__(self, repo: CategoryRepository) -> None:
        self._repo = repo

    def execute(self, category_id: int, user_id: int) -> None:
        self._repo.hard_delete(category_id, user_id)


class ActivateCategory:
    def __init__(self, repo: CategoryRepository) -> None:
        self._repo = repo

    def execute(self, category_id: int, user_id: int) -> None:
        self._repo.activate(category_id, user_id)


class CheckCategoryUsed:
    def __init__(self, repo: CategoryRepository) -> None:
        self._repo = repo

    def execute(self, category_id: int, user_id: int) -> bool:
        return self._repo.is_used(category_id, user_id)


class MoveCategoryAndDelete:
    def __init__(self, repo: CategoryRepository) -> None:
        self._repo = repo

    def execute(self, from_id: int, to_id: int, user_id: int) -> None:
        self._repo.move_and_delete(from_id, to_id, user_id)


class CategoryBundle:
    """Groups all category use cases for one category type."""

    def __init__(self, repo: CategoryRepository) -> None:
        self.list_all = ListAllCategories(repo)
        self.create = CreateCategory(repo)
        self.edit = EditCategory(repo)
        self.delete = DeleteCategory(repo)
        self.hard_delete = HardDeleteCategory(repo)
        self.activate = ActivateCategory(repo)
        self.check_used = CheckCategoryUsed(repo)
        self.move_and_delete = MoveCategoryAndDelete(repo)

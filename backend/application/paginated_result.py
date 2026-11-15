from dataclasses import dataclass

PAGE_SIZE = 25


@dataclass
class PaginatedResult[T]:
    items: list[T]
    total: int
    page: int
    page_size: int

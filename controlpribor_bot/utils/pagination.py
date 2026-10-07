import math
from typing import List, TypeVar, Generic

T = TypeVar("T")


class Paginator(Generic[T]):
    def __init__(self, items: List[T], per_page: int = 6):
        self.items = items
        self.per_page = max(1, per_page)
        self.total_items = len(items)
        self.total_pages = max(1, math.ceil(self.total_items / self.per_page))

    def get_page(self, page: int = 1) -> List[T]:
        if page < 1:
            page = 1
        elif page > self.total_pages:
            page = self.total_pages

        start_idx = (page - 1) * self.per_page
        end_idx = start_idx + self.per_page
        return self.items[start_idx:end_idx]

    def has_next(self, page: int) -> bool:
        return page < self.total_pages

    def has_prev(self, page: int) -> bool:
        return page > 1

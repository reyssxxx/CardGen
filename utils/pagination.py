"""
Утилита пагинации для инлайн-клавиатур.
"""
from typing import Any, List, Tuple

PAGE_SIZE = 8


def paginate(items: List[Any], page: int, page_size: int = PAGE_SIZE) -> Tuple[List[Any], bool, bool]:
    """
    Разбивает список на страницы.
    Возвращает (страница_элементов, есть_предыдущая, есть_следующая).
    """
    page = max(0, page)
    start = page * page_size
    end = start + page_size
    return items[start:end], page > 0, end < len(items)

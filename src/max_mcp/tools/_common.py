from collections.abc import Sequence
from typing import Any


def positive_int(name: str, value: int, *, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return value


def item_time(item: Any) -> int | None:
    value = item.get("time") if isinstance(item, dict) else getattr(item, "time", None)
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def next_before_time(items: Sequence[Any], *, page_is_full: bool) -> int | None:
    if not page_is_full:
        return None
    times = [timestamp for item in items if (timestamp := item_time(item)) is not None]
    return min(times) - 1 if times else None

"""A deliberately broken module used by the Looma repair example."""


def divide(a: float, b: float) -> float:
    # BUG: floor division loses the fractional part.
    return a // b


def clamp(value: float, low: float, high: float) -> float:
    # BUG: the min/max order is reversed.
    return min(low, max(value, high))

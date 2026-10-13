"""Her Math.round rounds half up; Python's round is banker's, so 20.5 would say 20."""

import math


def math_round(value: float) -> int:
    return math.floor(value + 0.5)

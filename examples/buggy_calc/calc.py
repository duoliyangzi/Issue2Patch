"""Tiny calculator with a deliberate bug for Issue2Patch demos."""


def add(a: int, b: int) -> int:
    # BUG: should be a + b
    return a * b


def sub(a: int, b: int) -> int:
    return a - b

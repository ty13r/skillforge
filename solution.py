def solve(items: list) -> list:
    """Return the squares of all even numbers in the input list."""
    return [number ** 2 for number in items if number % 2 == 0]

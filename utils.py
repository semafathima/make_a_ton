from decimal import Decimal, InvalidOperation


def parse_decimal(raw):
    """Return a non-negative Decimal, or None if the input is invalid."""
    try:
        value = Decimal((raw or "").strip())
    except InvalidOperation:
        return None
    return value if value >= 0 else None

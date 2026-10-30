"""The small-cell rule. Every statistical value leaves the app through format_value."""
from decimal import ROUND_HALF_UP, Decimal

THRESHOLD = 10
SMALL = "<10"
SUPPRESSED = "suppressed"


def round1(value):
    return float(Decimal(value).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def format_value(kind, raw):
    """kind: count (raw n), percent (raw (num, den)), mean (raw (exact Decimal total, n))."""
    if kind == "count":
        return SMALL if raw < THRESHOLD else int(raw)
    if kind == "percent":
        num, den = raw
        if num < THRESHOLD or den < THRESHOLD:
            return SUPPRESSED
        return round1(Decimal(num) * 100 / Decimal(den))
    if kind == "mean":
        total, n = raw
        if n < THRESHOLD:
            return SUPPRESSED
        return round1(Decimal(total) / Decimal(n))
    raise ValueError(f"unknown measure kind: {kind}")


def is_safe(value, kind):
    """True if a formatted value could have left the app under the rule (used by the leak check)."""
    if kind == "count":
        return value == SMALL or (isinstance(value, int) and value >= THRESHOLD)
    return value == SUPPRESSED or isinstance(value, float)

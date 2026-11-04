"""Groundwork: research workflows you can trust, hand over, and build on."""

__version__ = "0.3.0"
SPEC_VERSION = "0.3"


def vtuple(v: str | None) -> tuple[int, ...]:
    """'0.3' / 'v0.3.1' → (0, 3) / (0, 3, 1). Unknown → (0, 2): the first released spec."""
    import re
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums) if nums else (0, 2)

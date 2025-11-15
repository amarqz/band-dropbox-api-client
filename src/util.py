from __future__ import annotations

from collections.abc import Iterable


def strip_suffix(entry: str, suffix: str | None) -> str:
    """Return ``entry`` without ``suffix`` when it ends with it."""
    if not suffix:
        return entry
    return entry[: -len(suffix)] if entry.endswith(suffix) else entry


def contains_any_substring(entry: str, substrings: Iterable[str]) -> bool:
    """Return True when any non-empty substring is contained within ``entry``."""
    return any(substring and substring in entry for substring in substrings)


def remove_library_suffix(entry: str, suffix: str) -> str:
    """Backward compatible helper delegating to :func:`strip_suffix`."""
    return strip_suffix(entry, suffix)

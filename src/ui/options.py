from __future__ import annotations

from textual.widgets import OptionList
from textual.widgets.option_list import Option


def option_index(option: Option) -> int | None:
    """Return the integer index encoded in an option id, if available."""
    option_id = option.id
    if not option_id:
        return None
    try:
        _, index_text = option_id.rsplit("-", 1)
        index = int(index_text)
    except (ValueError, AttributeError):
        return None
    return index if index >= 0 else None


def focus_option(option_list: OptionList, index: int) -> None:
    """Best-effort attempt to move a list's cursor without raising."""
    moved = False
    if hasattr(option_list, "index"):
        try:
            option_list.index = index  # type: ignore[attr-defined]
            moved = True
        except Exception:  # pragma: no cover - defensive
            moved = False

    if not moved and hasattr(option_list, "action_cursor_down"):
        for _ in range(index + 1):
            try:
                option_list.action_cursor_down()  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - defensive
                break

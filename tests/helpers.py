from __future__ import annotations

from textual.widgets.option_list import Option


class OptionListStub:
    """Minimal stub mimicking Textual's OptionList for controller tests."""

    def __init__(self, widget_id: str = "") -> None:
        self.id = widget_id
        self.options: list[Option] = []
        self.index = 0
        self.cleared = False
        self.cursor_moves: list[int] = []

    def clear_options(self) -> None:
        self.cleared = True
        self.options.clear()

    def add_option(self, option: Option) -> None:
        self.options.append(option)

    def action_cursor_down(self) -> None:
        if self.options:
            self.index = min(self.index + 1, len(self.options) - 1)
        self.cursor_moves.append(self.index)

from __future__ import annotations

from collections.abc import Callable

from textual.widgets import OptionList

from ..actions import ActionHistory
from ..controllers.instruments import InstrumentController
from ..controllers.library import LibraryController
from .options import option_index


class LibraryEventHandler:
    """Route library-related Textual events to the controller."""

    def __init__(
        self,
        controller: LibraryController,
        history: ActionHistory,
        get_option_list: Callable[[], OptionList],
        refresh_detail: Callable[[], None],
    ) -> None:
        self._controller = controller
        self._history = history
        self._get_option_list = get_option_list
        self._refresh_detail = refresh_detail

    def handle_option_selected(self, event: OptionList.OptionSelected) -> bool:
        if (event.option_list.id or "") != "library-list":
            return False
        if event.option.disabled:
            return False
        index = option_index(event.option)
        if index is None:
            return False
        entry = self._controller.entry_for_filtered_index(index)
        if entry is None:
            return False
        self._controller.set_highlight(index)
        action = self._controller.toggle_entry(entry)
        self._history.push(action)
        self._controller.refresh_options(event.option_list)
        self._refresh_detail()
        return True

    def handle_option_highlighted(
        self,
        event: OptionList.OptionHighlighted,
    ) -> bool:
        if (event.option_list.id or "") != "library-list":
            return False
        index = option_index(event.option)
        if index is None:
            return False
        self._controller.set_highlight(index)
        return True

    def handle_filter_changed(self, value: str) -> None:
        self._controller.set_filter_text(value)
        self._controller.refresh_options(self._get_option_list())

    def clear_filter(self) -> None:
        self._controller.clear_filter()
        self._controller.refresh_options(self._get_option_list())

    def refresh_options(self) -> None:
        self._controller.refresh_options(self._get_option_list())


class InstrumentEventHandler:
    """Route instrument-related Textual events to the controller."""

    def __init__(
        self,
        controller: InstrumentController,
        history: ActionHistory,
        get_option_list: Callable[[], OptionList],
        refresh_detail: Callable[[], None],
    ) -> None:
        self._controller = controller
        self._history = history
        self._get_option_list = get_option_list
        self._refresh_detail = refresh_detail

    def handle_option_selected(self, event: OptionList.OptionSelected) -> bool:
        if (event.option_list.id or "") != "instrument-list":
            return False
        if event.option.disabled:
            return False
        index = option_index(event.option)
        if index is None:
            return False
        return self._apply_delta_for_index(index, 1, event.option_list)

    def handle_option_highlighted(
        self,
        event: OptionList.OptionHighlighted,
    ) -> bool:
        if (event.option_list.id or "") != "instrument-list":
            return False
        index = option_index(event.option)
        if index is None:
            return False
        self._controller.set_highlight(index)
        return True

    def refresh_options(self) -> None:
        self._controller.refresh_options(self._get_option_list())

    def _apply_delta_for_index(
        self,
        index: int,
        delta: int,
        option_list: OptionList,
    ) -> bool:
        entry = self._controller.entry_for_index(index)
        if entry is None:
            return False
        self._controller.set_highlight(index)
        action = self._controller.adjust_count(entry, delta)
        if not action:
            return False
        self._history.push(action)
        self._controller.refresh_options(option_list)
        self._refresh_detail()
        return True

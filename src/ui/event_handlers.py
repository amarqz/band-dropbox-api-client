from __future__ import annotations

from collections.abc import Callable

from textual import events
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
        delta = -1 if self._is_decrement_event(getattr(event, "input_event", None)) else 1
        return self._apply_delta_for_index(index, delta, event.option_list)

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

    def handle_keyboard_decrement(self, focused: OptionList | None) -> bool:
        if not isinstance(focused, OptionList) or focused.id != "instrument-list":
            return False
        index = getattr(focused, "index", None)
        if not isinstance(index, int):
            return False
        return self._apply_delta_for_index(index, -1, focused)

    def handle_mouse_decrement(self, event: events.MouseDown) -> bool:
        button = getattr(event, "button", None)
        button_name = getattr(button, "name", str(button) if button is not None else "")
        if str(button_name).lower() not in {"right", "secondary"}:
            return False
        instrument_list = self._get_option_list()
        path = getattr(event, "path", [])
        if instrument_list not in path:
            return False
        index = getattr(instrument_list, "index", None)
        if not isinstance(index, int):
            return False
        return self._apply_delta_for_index(index, -1, instrument_list)

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

    @staticmethod
    def _is_decrement_event(input_event: events.Event | None) -> bool:
        if input_event is None:
            return False
        if isinstance(input_event, events.Key):
            return input_event.key in {"backspace", "delete"}
        if isinstance(input_event, events.MouseEvent):
            button = getattr(input_event, "button", None)
            if hasattr(button, "name"):
                return button.name.lower() in {"right", "secondary"}
            return str(button).lower() in {"right", "secondary"}
        return False

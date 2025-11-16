from __future__ import annotations

from dataclasses import dataclass, field

from rich.text import Text
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from ..actions import SelectionAction
from ..ui.options import focus_option


@dataclass
class LibraryController:
    """Encapsulates library data, filtering, and selection state."""

    placeholder: str
    _entries: list[str] = field(default_factory=list)
    _filtered_entries: list[str] = field(default_factory=list)
    _selected_entries: set[str] = field(default_factory=set)
    _filter_text: str = ""
    _highlight_index: int = 0

    EMPTY_FILTER_MESSAGE = "No entries match the filter."
    EMPTY_FOLDER_MESSAGE = "This folder is empty."

    def load_entries(self, entries: list[str]) -> None:
        self._entries = list(entries)
        self._filtered_entries = list(entries)
        self._selected_entries.clear()
        self._highlight_index = 0
        if self._filter_text:
            self._apply_filter()

    def set_filter_text(self, value: str) -> None:
        self._filter_text = value
        self._apply_filter()

    def clear_filter(self) -> None:
        self.set_filter_text("")

    @property
    def filter_text(self) -> str:
        return self._filter_text

    @property
    def filtered_entries(self) -> list[str]:
        return self._filtered_entries

    @property
    def selected_entries(self) -> set[str]:
        return self._selected_entries

    @property
    def highlight_index(self) -> int:
        return self._highlight_index

    def set_highlight(self, index: int) -> None:
        if index >= 0:
            self._highlight_index = index

    def entry_for_filtered_index(self, index: int) -> str | None:
        if 0 <= index < len(self._filtered_entries):
            return self._filtered_entries[index]
        return None

    def toggle_entry(self, entry: str) -> SelectionAction:
        was_selected = entry in self._selected_entries
        if was_selected:
            self._selected_entries.discard(entry)
        else:
            self._selected_entries.add(entry)
        return SelectionAction(entry, was_selected)

    def restore_selection(self, entry: str, previous_state: bool) -> None:
        if previous_state:
            self._selected_entries.add(entry)
        else:
            self._selected_entries.discard(entry)

    def clear_selections(self) -> bool:
        if not self._selected_entries:
            return False
        self._selected_entries.clear()
        return True

    def refresh_options(self, option_list: OptionList) -> None:
        option_list.clear_options()

        if not self._filtered_entries:
            if self._entries and self._filter_text:
                message = self.EMPTY_FILTER_MESSAGE
            elif self._entries:
                message = self.EMPTY_FOLDER_MESSAGE
            else:
                message = self.placeholder
            option_list.add_option(Option(message, disabled=True))
            self._highlight_index = 0
            return

        target_index = min(self._highlight_index, len(self._filtered_entries) - 1)

        for index, entry in enumerate(self._filtered_entries):
            marker = "[x]" if entry in self._selected_entries else "[ ]"
            prompt = Text.assemble(marker, " ", entry)
            option_list.add_option(Option(prompt, id=f"entry-{index}"))

        focus_option(option_list, target_index)
        self._highlight_index = target_index

    def _apply_filter(self) -> None:
        query = self._filter_text.strip().lower()
        if not query:
            self._filtered_entries = list(self._entries)
        else:
            self._filtered_entries = [
                entry for entry in self._entries if query in entry.lower()
            ]
        self._highlight_index = 0

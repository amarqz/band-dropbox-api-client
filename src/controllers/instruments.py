from __future__ import annotations

from dataclasses import dataclass, field

from rich.text import Text
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from ..actions import InstrumentAction
from ..ui.options import focus_option
from ..util import contains_any_substring, strip_suffix


@dataclass
class InstrumentController:
    """Handles instrument entry processing and count adjustments."""

    placeholder: str
    empty_message: str
    suffix: str | None = None
    exclude_substrings: tuple[str, ...] = field(default_factory=tuple)
    _entries: list[str] = field(default_factory=list)
    _entry_map: dict[str, str] = field(default_factory=dict)
    _counts: dict[str, int] = field(default_factory=dict)
    _highlight_index: int = 0

    def load_entries(self, entries: list[str]) -> None:
        processed, entry_map = self._process_entries(entries)
        self._entries = processed
        self._entry_map = entry_map
        self._counts = {entry: self._counts.get(entry, 0) for entry in processed}
        self._highlight_index = 0

    def entry_for_index(self, index: int) -> str | None:
        if 0 <= index < len(self._entries):
            return self._entries[index]
        return None

    @property
    def entries(self) -> list[str]:
        return self._entries

    def raw_entry_for_display(self, entry: str) -> str:
        return self._entry_map.get(entry, entry)

    @property
    def counts(self) -> dict[str, int]:
        return self._counts

    @property
    def highlight_index(self) -> int:
        return self._highlight_index

    def set_highlight(self, index: int) -> None:
        if index >= 0:
            self._highlight_index = index

    def adjust_count(self, entry: str, delta: int) -> InstrumentAction | None:
        if not delta:
            return None
        current = self._counts.get(entry, 0)
        new_value = max(0, current + delta)
        if new_value == current:
            return None
        self._counts[entry] = new_value
        applied_delta = new_value - current
        return InstrumentAction(entry, applied_delta)

    def restore_count(self, entry: str, delta: int) -> None:
        if delta:
            self.adjust_count(entry, delta)

    def clear_counts(self) -> bool:
        if not any(self._counts.values()):
            return False
        for entry in list(self._counts.keys()):
            self._counts[entry] = 0
        return True

    def refresh_options(self, option_list: OptionList) -> None:
        option_list.clear_options()

        if not self._entries:
            option_list.add_option(Option(self.empty_message, disabled=True))
            self._highlight_index = 0
            return

        target_index = min(self._highlight_index, len(self._entries) - 1)

        for index, entry in enumerate(self._entries):
            count = self._counts.get(entry, 0)
            prompt = Text.assemble(f"[{count}] ", entry)
            option_list.add_option(Option(prompt, id=f"instrument-{index}"))

        focus_option(option_list, target_index)
        self._highlight_index = target_index

    def _process_entries(self, entries: list[str]) -> tuple[list[str], dict[str, str]]:
        processed: list[str] = []
        entry_map: dict[str, str] = {}
        for entry in entries:
            raw_entry = self._strip_type_indicator(entry)
            display = self._strip_instrument_suffix(raw_entry)
            if self.exclude_substrings and contains_any_substring(
                display, self.exclude_substrings
            ):
                continue
            if display not in entry_map:
                entry_map[display] = raw_entry
                processed.append(display)
        return sorted(processed, key=str.lower), entry_map

    def _strip_instrument_suffix(self, entry: str) -> str:
        if not self.suffix:
            return entry
        if " / " in entry:
            instrument, voice = entry.split(" / ", 1)
            instrument = strip_suffix(instrument, self.suffix)
            voice = strip_suffix(voice, self.suffix)
            return f"{instrument} / {voice}"
        return strip_suffix(entry, self.suffix)

    @staticmethod
    def _strip_type_indicator(entry: str) -> str:
        if entry.startswith("[") and "] " in entry:
            return entry.split("] ", 1)[1]
        return entry

    @staticmethod
    def parse_exclusions(raw: str | None) -> tuple[str, ...]:
        if not raw:
            return ()
        parts = (part.strip() for part in raw.split(","))
        return tuple(part for part in parts if part)

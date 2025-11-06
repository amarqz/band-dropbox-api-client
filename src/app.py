"""Textual application entry point for the band's Dropbox client."""

from __future__ import annotations

import asyncio

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, LoadingIndicator, OptionList, Static
from textual.widgets.option_list import Option

from .config import APP_CONFIG, AppConfig, DBX_CONFIG
from .client.dropbox_client import DropboxClient
from .util import contains_any_substring, strip_suffix


class BandDropboxApp(App[None]):
    """Textual application with a simple splash screen and main layout."""

    CSS_PATH = "app.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("space", "toggle_option", "Toggle Selection"),
    ]

    is_loading = reactive(True)

    def __init__(self, *, app_config: AppConfig | None = None, **kwargs) -> None:
        """Allow injecting configuration, defaulting to the on-disk settings."""
        super().__init__(**kwargs)
        self.app_config = app_config or APP_CONFIG
        self._dbx_client: DropboxClient | None = None
        self._library_entries: list[str] = []
        self._selected_entries: set[str] = set()
        self._highlight_index: int = 0
        self._instrument_entries: list[str] = []
        self._instrument_counts: dict[str, int] = {}
        self._instrument_highlight_index: int = 0

    def compose(self) -> ComposeResult:
        """Compose the initial widget tree."""
        yield Container(
            Static(self.app_config.title, classes="loading__title"),
            LoadingIndicator(id="loading__spinner"),
            Static(self.app_config.loading_message, classes="loading__subtitle"),
            id="loading-view",
        )

        yield Container(
            Header(show_clock=True),
            Horizontal(
                Container(
                    Static(self.app_config.library_title, classes="panel__title"),
                    OptionList(
                        Option(self.app_config.library_placeholder, disabled=True),
                        classes="panel__body",
                        id="library-list",
                    ),
                    classes="panel",
                    id="library-panel",
                ),
                Vertical(
                    Container(
                        Static(self.app_config.detail_title, classes="panel__title"),
                        Static(
                            self.app_config.detail_placeholder,
                            classes="panel__body",
                            id="detail-body",
                        ),
                        classes="panel",
                        id="detail-panel",
                    ),
                    Container(
                        Static(self.app_config.instruments_title, classes="panel__title"),
                        OptionList(
                            Option(self.app_config.instruments_placeholder, disabled=True),
                            classes="panel__body",
                            id="instrument-list",
                        ),
                        classes="panel",
                        id="instrument-panel",
                    ),
                ),
                id="main-panels",
            ),
            Footer(),
            id="main-view",
        )

    def watch_is_loading(self, loading: bool) -> None:
        """Toggle visibility between the splash screen and the main layout."""
        self.query_one("#loading-view").display = loading
        self.query_one("#main-view").display = not loading

    async def on_mount(self) -> None:
        """Kick off startup tasks when the application mounts."""
        await self._startup()

    async def _startup(self) -> None:
        """Start the application by connecting to Dropbox and loading initial data."""
        try:
            self._dbx_client = DropboxClient(DBX_CONFIG)
        except Exception as exc:
            message = str(exc)
            self._on_library_error(message)
            self._on_instruments_error(message)
            return

        tasks = [
            asyncio.to_thread(
                self._dbx_client.list_contents,
                self.app_config.library_path,
            )
        ]

        instrument_path = self.app_config.instruments_path
        instrument_task_index: int | None = None
        if instrument_path is not None:
            normalized_instruments_path = instrument_path.strip()
            instrument_task_index = len(tasks)
            tasks.append(
                asyncio.to_thread(
                    self._dbx_client.list_contents,
                    normalized_instruments_path,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        library_result = results[0]
        instruments_result = (
            results[instrument_task_index]
            if instrument_task_index is not None and instrument_task_index < len(results)
            else None
        )

        if isinstance(library_result, Exception):
            self._on_library_error(str(library_result))
        else:
            library_entries = list(library_result)
            if self.app_config.library_suffix:
                library_entries = [
                    strip_suffix(entry, self.app_config.library_suffix)
                    for entry in library_entries
                ]
            self._on_library_loaded(library_entries)

        if instrument_task_index is not None:
            if isinstance(instruments_result, Exception):
                self._on_instruments_error(str(instruments_result))
            elif instruments_result is not None:
                instruments_entries = self._process_instrument_entries(
                    list(instruments_result)
                )
                self._on_instruments_loaded(instruments_entries)
            else:
                self._on_instruments_loaded([])

    def _on_library_loaded(self, contents: list[str]) -> None:
        """Render the fetched Dropbox contents in the library panel."""
        self.is_loading = False
        self._library_entries = contents
        self._selected_entries.clear()
        self._highlight_index = 0
        self._refresh_library_options()
        self._update_detail_panel()

    def _on_library_error(self, message: str) -> None:
        """Display error information when Dropbox calls fail."""
        self.is_loading = False
        self._library_entries = []
        self._selected_entries.clear()
        self._highlight_index = 0
        library_list = self.query_one("#library-list", OptionList)
        library_list.clear_options()
        library_list.add_option(
            Option(
                f"Unable to load Dropbox contents:\n{message}",
                disabled=True,
            )
        )
        self.log.error(f"Dropbox startup failed: {message}")
        self._update_detail_panel(error=True)

    def _on_instruments_loaded(self, entries: list[str]) -> None:
        """Render the fetched instruments in the instruments panel."""
        self._instrument_entries = entries
        self._instrument_counts = {
            entry: self._instrument_counts.get(entry, 0) for entry in entries
        }
        self._instrument_highlight_index = 0
        self._refresh_instrument_options()
        self._update_detail_panel()

    def _on_instruments_error(self, message: str) -> None:
        """Display error information when instrument loading fails."""
        self._instrument_entries = []
        self._instrument_counts.clear()
        self._instrument_highlight_index = 0
        instrument_list = self.query_one("#instrument-list", OptionList)
        instrument_list.clear_options()
        instrument_list.add_option(
            Option(f"Unable to load instruments:\n{message}", disabled=True)
        )
        self.log.error(f"Dropbox instruments load failed: {message}")
        self._update_detail_panel()

    def on_option_list_option_selected(
        self,
        event: OptionList.OptionSelected,
    ) -> None:
        """Handle option selections for library and instrument lists."""
        option_list = event.option_list
        list_id = option_list.id or ""
        if event.option.disabled:
            return

        index = self._option_index(event.option)
        if index is None:
            return

        if list_id == "library-list":
            if not 0 <= index < len(self._library_entries):
                return

            entry = self._library_entries[index]
            self._highlight_index = index
            if entry in self._selected_entries:
                self._selected_entries.remove(entry)
            else:
                self._selected_entries.add(entry)

            self._refresh_library_options()
            self._update_detail_panel()
            return

        if list_id == "instrument-list":
            if not 0 <= index < len(self._instrument_entries):
                return

            entry = self._instrument_entries[index]
            self._instrument_highlight_index = index

            input_event = getattr(event, "input_event", None)
            delta = -1 if self._is_decrement_event(input_event) else 1
            self._adjust_instrument_count(entry, delta)
            return

    def _refresh_library_options(self) -> None:
        """Render library options with selection markers, keeping focus where possible."""
        library_list = self.query_one("#library-list", OptionList)
        library_list.clear_options()

        if not self._library_entries:
            library_list.add_option(Option("This folder is empty.", disabled=True))
            self._highlight_index = 0
            return

        target_index = min(self._highlight_index, len(self._library_entries) - 1)

        for index, entry in enumerate(self._library_entries):
            marker = "[x]" if entry in self._selected_entries else "[ ]"
            prompt = Text.assemble(marker, " ", entry)
            library_list.add_option(
                Option(prompt, id=f"entry-{index}")
            )

        moved = False
        if hasattr(library_list, "index"):
            try:
                library_list.index = target_index  # type: ignore[attr-defined]
                moved = True
            except Exception:  # pragma: no cover - defensive
                moved = False

        if not moved and hasattr(library_list, "action_cursor_down"):
            for _ in range(target_index + 1):
                try:
                    library_list.action_cursor_down()  # type: ignore[attr-defined]
                except Exception:  # pragma: no cover - defensive
                    break

        self._highlight_index = target_index

    def _refresh_instrument_options(self) -> None:
        """Render instrument options with counts while keeping focus."""
        instrument_list = self.query_one("#instrument-list", OptionList)
        instrument_list.clear_options()

        if not self._instrument_entries:
            instrument_list.add_option(
                Option(self.app_config.instruments_empty_message, disabled=True)
            )
            self._instrument_highlight_index = 0
            return

        target_index = min(
            self._instrument_highlight_index, len(self._instrument_entries) - 1
        )

        for index, entry in enumerate(self._instrument_entries):
            count = self._instrument_counts.get(entry, 0)
            prompt = Text.assemble(f"[{count}] ", entry)
            instrument_list.add_option(
                Option(prompt, id=f"instrument-{index}")
            )

        moved = False
        if hasattr(instrument_list, "index"):
            try:
                instrument_list.index = target_index  # type: ignore[attr-defined]
                moved = True
            except Exception:  # pragma: no cover - defensive
                moved = False

        if not moved and hasattr(instrument_list, "action_cursor_down"):
            for _ in range(target_index + 1):
                try:
                    instrument_list.action_cursor_down()  # type: ignore[attr-defined]
                except Exception:  # pragma: no cover - defensive
                    break

        self._instrument_highlight_index = target_index

    def _update_detail_panel(self, *, error: bool = False) -> None:
        """Refresh the detail panel content based on current selection state."""
        detail_panel = self.query_one("#detail-body", Static)

        if error:
            detail_panel.update("Unable to show details.")
            return

        sections: list[str] = []

        if self._selected_entries:
            library_lines = "\n".join(sorted(self._selected_entries, key=str.lower))
            sections.append(
                f"Selected items ({len(self._selected_entries)}):\n{library_lines}"
            )

        counted_instruments = [
            (entry, count)
            for entry, count in sorted(
                self._instrument_counts.items(), key=lambda item: item[0].lower()
            )
            if count > 0
        ]
        if counted_instruments:
            instrument_lines = "\n".join(
                f"{entry}: {count}" for entry, count in counted_instruments
            )
            sections.append(
                f"Instrument counts ({len(counted_instruments)}):\n{instrument_lines}"
            )

        if sections:
            detail_panel.update("\n\n".join(sections))
        else:
            detail_panel.update(self.app_config.detail_placeholder)

    def action_toggle_option(self) -> None:
        """Toggle the selection state for the focused library entry."""
        focused = self.focused
        if isinstance(focused, OptionList):
            focused.action_select()

    def on_key(self, event: events.Key) -> None:
        """Handle global key presses for manual adjustments."""
        if event.key in {"backspace", "delete"}:
            focused = self.focused
            if isinstance(focused, OptionList) and focused.id == "instrument-list":
                index = getattr(focused, "index", None)
                if isinstance(index, int) and 0 <= index < len(self._instrument_entries):
                    entry = self._instrument_entries[index]
                    self._instrument_highlight_index = index
                    self._adjust_instrument_count(entry, -1)
                    event.stop()
                    return
        handler = getattr(super(), "on_key", None)
        if handler:
            handler(event)

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Handle right clicks on the instrument list to decrement counts."""
        button = getattr(event, "button", None)
        button_name = getattr(button, "name", str(button) if button is not None else "")
        if str(button_name).lower() in {"right", "secondary"}:
            instrument_list = self.query_one("#instrument-list", OptionList)
            path = getattr(event, "path", [])
            if instrument_list in path:
                index = getattr(instrument_list, "index", None)
                if isinstance(index, int) and 0 <= index < len(self._instrument_entries):
                    entry = self._instrument_entries[index]
                    self._instrument_highlight_index = index
                    self._adjust_instrument_count(entry, -1)
                    event.stop()
                    return
        handler = getattr(super(), "on_mouse_down", None)
        if handler:
            handler(event)

    def on_option_list_option_highlighted(
        self,
        event: OptionList.OptionHighlighted,
    ) -> None:
        """Track the highlighted index so the cursor doesn't jump on refresh."""
        index = self._option_index(event.option)
        if index is not None:
            option_list = event.option_list
            if option_list.id == "library-list":
                self._highlight_index = index
            elif option_list.id == "instrument-list":
                self._instrument_highlight_index = index

    def _adjust_instrument_count(self, entry: str, delta: int) -> None:
        """Adjust the selection count for an instrument entry."""
        current = self._instrument_counts.get(entry, 0)
        new_value = max(0, current + delta)
        self._instrument_counts[entry] = new_value
        self._refresh_instrument_options()
        self._update_detail_panel()

    @staticmethod
    def _is_decrement_event(input_event: events.Event | None) -> bool:
        """Return True if the originating input should decrement a count."""
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

    @staticmethod
    def _option_index(option: Option) -> int | None:
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

    def _process_instrument_entries(self, entries: list[str]) -> list[str]:
        """Return processed instrument entries ready for display."""
        suffix = self.app_config.instruments_suffix
        exclusions = self._instrument_exclusions()

        processed: list[str] = []
        for entry in entries:
            display = self._strip_type_indicator(entry)
            display = strip_suffix(display, suffix)
            if exclusions and contains_any_substring(display, exclusions):
                continue
            processed.append(display)

        return sorted(processed, key=str.lower)

    @staticmethod
    def _strip_type_indicator(entry: str) -> str:
        """Remove the Dropbox type indicator prefix when present."""
        if entry.startswith("[") and "] " in entry:
            return entry.split("] ", 1)[1]
        return entry

    def _instrument_exclusions(self) -> tuple[str, ...]:
        """Return configured instrument substrings to exclude."""
        raw = self.app_config.instruments_exclude_substrings or ""
        parts = (part.strip() for part in raw.split(","))
        return tuple(part for part in parts if part)


if __name__ == "__main__":
    app = BandDropboxApp()
    app.run()

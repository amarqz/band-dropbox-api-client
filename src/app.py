"""Textual application entry point for the band's Dropbox client."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from textual import events
from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.widgets import Button, Input, OptionList, Static
from textual.widgets.option_list import Option

from .actions import ActionHistory, InstrumentAction, SelectionAction
from .config import APP_CONFIG, AppConfig, DBX_CONFIG
from .controllers.instruments import InstrumentController
from .controllers.library import LibraryController
from .services.startup import load_initial_data
from .ui.commands import StartCommandProvider
from .ui.detail_panel import build_detail_panel_content
from .ui.layout import compose_layout
from .ui.options import option_index
from .util import strip_suffix


class BandDropboxApp(App[None]):
    """Textual application with a simple splash screen and main layout."""

    CSS_PATH = "app.tcss"
    COMMANDS = App.COMMANDS | {StartCommandProvider}
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("s", "start_detail_action", "Start"),
        ("space", "toggle_option", "Toggle Selection"),
        ("u", "undo_detail_action", "Undo"),
        ("c", "clear_detail_action", "Clear"),
        ("d", "clear_library_filter", "Reset Filter"),
    ]

    is_loading = reactive(True)

    def __init__(self, *, app_config: AppConfig | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.app_config = app_config or APP_CONFIG
        self.library_controller = LibraryController(self.app_config.library_placeholder)
        self.instrument_controller = InstrumentController(
            placeholder=self.app_config.instruments_placeholder,
            empty_message=self.app_config.instruments_empty_message,
            suffix=self.app_config.instruments_suffix,
            exclude_substrings=InstrumentController.parse_exclusions(
                self.app_config.instruments_exclude_substrings
            ),
        )
        self.history = ActionHistory()
        self._startup_task: asyncio.Task[None] | None = None
        self._start_task: asyncio.Task[None] | None = None

    def compose(self) -> ComposeResult:
        """Compose the initial widget tree."""
        yield from compose_layout(self.app_config)

    def watch_is_loading(self, loading: bool) -> None:
        """Toggle visibility between the splash screen and the main layout."""
        self.query_one("#loading-view").display = loading
        self.query_one("#main-view").display = not loading

    async def on_mount(self) -> None:
        """Kick off startup tasks when the application mounts."""
        self._startup_task = asyncio.create_task(self._startup())

    async def on_unmount(self) -> None:
        """Cancel the startup task if the application exits early."""
        if self._startup_task and not self._startup_task.done():
            self._startup_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._startup_task

    async def _startup(self) -> None:
        """Start the application by connecting to Dropbox and loading data."""
        result = await load_initial_data(self.app_config, DBX_CONFIG)

        if result.library_entries is not None:
            library_entries = self._prepare_library_entries(result.library_entries)
            self._on_library_loaded(library_entries)
        else:
            message = result.library_error or "Unable to load Dropbox contents."
            self._on_library_error(message)

        if result.instrument_entries is not None:
            self._on_instruments_loaded(result.instrument_entries)
        elif result.instrument_error:
            self._on_instruments_error(result.instrument_error)
        else:
            self._on_instruments_loaded([])

    def _prepare_library_entries(self, entries: list[str]) -> list[str]:
        suffix = self.app_config.library_suffix
        if not suffix:
            return list(entries)
        return [strip_suffix(entry, suffix) for entry in entries]

    def _on_library_loaded(self, contents: list[str]) -> None:
        """Render the fetched Dropbox contents in the library panel."""
        self.is_loading = False
        self.history.clear()
        self.library_controller.load_entries(contents)
        self.library_controller.refresh_options(self._library_list())
        self._update_detail_panel()

    def _on_library_error(self, message: str) -> None:
        """Display error information when Dropbox calls fail."""
        self.is_loading = False
        self.history.clear()
        self.library_controller.load_entries([])
        self.library_controller.clear_filter()
        with suppress(LookupError):
            self.query_one("#library-filter", Input).value = ""
        library_list = self._library_list()
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
        self.history.clear()
        self.instrument_controller.load_entries(entries)
        self.instrument_controller.refresh_options(self._instrument_list())
        self._update_detail_panel()

    def _on_instruments_error(self, message: str) -> None:
        """Display error information when instrument loading fails."""
        self.history.clear()
        self.instrument_controller.load_entries([])
        instrument_list = self._instrument_list()
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

        index = option_index(event.option)
        if index is None:
            return

        if list_id == "library-list":
            entry = self.library_controller.entry_for_filtered_index(index)
            if entry is None:
                return
            self.library_controller.set_highlight(index)
            action = self.library_controller.toggle_entry(entry)
            self.history.push(action)
            self.library_controller.refresh_options(option_list)
            self._update_detail_panel()
            return

        if list_id == "instrument-list":
            entry = self.instrument_controller.entry_for_index(index)
            if entry is None:
                return
            self.instrument_controller.set_highlight(index)
            input_event = getattr(event, "input_event", None)
            delta = -1 if self._is_decrement_event(input_event) else 1
            action = self.instrument_controller.adjust_count(entry, delta)
            if action:
                self.history.push(action)
                self.instrument_controller.refresh_options(option_list)
                self._update_detail_panel()

    def on_option_list_option_highlighted(
        self,
        event: OptionList.OptionHighlighted,
    ) -> None:
        """Track the highlighted index so the cursor doesn't jump on refresh."""
        index = option_index(event.option)
        if index is None:
            return
        option_list = event.option_list
        if option_list.id == "library-list":
            self.library_controller.set_highlight(index)
        elif option_list.id == "instrument-list":
            self.instrument_controller.set_highlight(index)

    def action_toggle_option(self) -> None:
        """Toggle the selection state for the focused library entry."""
        focused = self.focused
        if isinstance(focused, OptionList):
            focused.action_select()

    def action_undo_detail_action(self) -> None:
        """Undo the most recent selection or instrument adjustment."""
        self._undo_last_action()

    def action_clear_detail_action(self) -> None:
        """Clear all selections via keyboard bindings."""
        self._clear_all_selections()

    def action_start_detail_action(self) -> None:
        """Trigger the start action from a keyboard binding."""
        button = self.query_one("#detail-action-start", Button)
        self._handle_start_button(button)

    def action_clear_library_filter(self) -> None:
        """Clear the library filter and refocus the input."""
        with suppress(LookupError):
            filter_input = self.query_one("#library-filter", Input)
            filter_input.value = ""
            filter_input.focus()
        self.library_controller.clear_filter()
        self.library_controller.refresh_options(self._library_list())

    def on_input_changed(self, event: Input.Changed) -> None:
        """Apply the library filter as the user types."""
        if event.input.id == "library-filter":
            self.library_controller.set_filter_text(event.value)
            self.library_controller.refresh_options(self._library_list())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle control button clicks below the detail panel."""
        button_id = event.button.id or ""
        if button_id == "detail-action-undo":
            self._undo_last_action()
            return
        if button_id == "detail-action-clear":
            self._clear_all_selections()
            return
        if button_id == "detail-action-start":
            self._handle_start_button(event.button)

    def on_key(self, event: events.Key) -> None:
        """Handle global key presses for manual adjustments."""
        if event.key in {"delete", "backspace"}:
            focused = self.focused
            if isinstance(focused, OptionList) and focused.id == "instrument-list":
                index = getattr(focused, "index", None)
                if isinstance(index, int):
                    entry = self.instrument_controller.entry_for_index(index)
                    if entry:
                        self.instrument_controller.set_highlight(index)
                        action = self.instrument_controller.adjust_count(entry, -1)
                        if action:
                            self.history.push(action)
                            self.instrument_controller.refresh_options(focused)
                            self._update_detail_panel()
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
            instrument_list = self._instrument_list()
            path = getattr(event, "path", [])
            if instrument_list in path:
                index = getattr(instrument_list, "index", None)
                if isinstance(index, int):
                    entry = self.instrument_controller.entry_for_index(index)
                    if entry:
                        self.instrument_controller.set_highlight(index)
                        action = self.instrument_controller.adjust_count(entry, -1)
                        if action:
                            self.history.push(action)
                            self.instrument_controller.refresh_options(instrument_list)
                            self._update_detail_panel()
                            event.stop()
                            return
        handler = getattr(super(), "on_mouse_down", None)
        if handler:
            handler(event)

    def _undo_last_action(self) -> None:
        """Revert the most recent selection or instrument adjustment."""
        action = self.history.pop()
        if not action:
            return
        if isinstance(action, SelectionAction):
            self.library_controller.restore_selection(action.entry, action.previous_state)
            self.library_controller.refresh_options(self._library_list())
        elif isinstance(action, InstrumentAction):
            self.instrument_controller.adjust_count(action.entry, -action.delta)
            self.instrument_controller.refresh_options(self._instrument_list())
        self._update_detail_panel()

    def _clear_all_selections(self) -> None:
        """Reset both the selected entries and instrument counts."""
        cleared_library = self.library_controller.clear_selections()
        cleared_instruments = self.instrument_controller.clear_counts()
        if not cleared_library and not cleared_instruments:
            return
        self.history.clear()
        self.library_controller.refresh_options(self._library_list())
        self.instrument_controller.refresh_options(self._instrument_list())
        self._update_detail_panel()

    def _handle_start_button(self, button: Button) -> None:
        """Kick off the asynchronous start countdown, if not already running."""
        if self._start_task and not self._start_task.done():
            return
        self._start_task = asyncio.create_task(self._run_start_sequence(button))

    async def _run_start_sequence(self, button: Button) -> None:
        """Simulate a short async operation by counting to three."""
        button.label = "In progress..."
        try:
            for _ in range(3):
                await asyncio.sleep(1)
        finally:
            button.label = "Start"
            self._start_task = None

    def _update_detail_panel(self, *, error: bool = False) -> None:
        detail_library = self.query_one("#detail-library", Static)
        detail_instruments = self.query_one("#detail-instruments", Static)
        detail_library_title = self.query_one("#detail-library-title", Static)
        detail_instruments_title = self.query_one("#detail-instruments-title", Static)

        content = build_detail_panel_content(
            self.app_config,
            self.library_controller.selected_entries,
            self.instrument_controller.counts,
            error=error,
        )
        detail_library_title.update(content.library_title)
        detail_library.update(content.library_body)
        detail_instruments_title.update(content.instruments_title)
        detail_instruments.update(content.instruments_body)

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

    def _library_list(self) -> OptionList:
        return self.query_one("#library-list", OptionList)

    def _instrument_list(self) -> OptionList:
        return self.query_one("#instrument-list", OptionList)


if __name__ == "__main__":
    app = BandDropboxApp()
    app.run()

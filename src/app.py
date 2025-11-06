"""Textual application entry point for the band's Dropbox client."""

from __future__ import annotations

import asyncio

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import Footer, Header, LoadingIndicator, OptionList, Static
from textual.widgets.option_list import Option

from .config import APP_CONFIG, AppConfig, DBX_CONFIG
from .client.dropbox_client import DropboxClient
from .util import remove_library_suffix


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
        """Startup the application by connecting to Dropbox and fetching the root folder contents."""
        try:
            self._dbx_client = DropboxClient(DBX_CONFIG)
            contents = await asyncio.to_thread(
                self._dbx_client.list_contents,
                self.app_config.library_path,
            )
            if self.app_config.library_suffix:
                contents = [
                    remove_library_suffix(entry, self.app_config.library_suffix)
                    for entry in contents
                ]
        except Exception as exc:
            self._on_library_error(str(exc))
        else:
            self._on_library_loaded(contents)

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

    def on_option_list_option_selected(
        self,
        event: OptionList.OptionSelected,
    ) -> None:
        """Update the detail panel when a library option is selected."""
        if event.option.disabled:
            return

        index = self._option_index(event.option)
        if index is None:
            return

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

    def _refresh_library_options(self) -> None:
        """Render library options with selection markers, keeping focus where possible."""
        library_list = self.query_one("#library-list", OptionList)
        current_index: int | None = None

        if hasattr(library_list, "index"):
            try:
                current_index = library_list.index  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - defensive
                current_index = None

        library_list.clear_options()

        if not self._library_entries:
            library_list.add_option(Option("This folder is empty.", disabled=True))
            return

        target_index = min(self._highlight_index, len(self._library_entries) - 1)

        for index, entry in enumerate(self._library_entries):
            marker = "[x]" if entry in self._selected_entries else "[ ]"
            prompt = Text.assemble(marker, " ", entry)
            library_list.add_option(
                Option(prompt, id=f"entry-{index}")
            )

        if target_index > 0:
            for _ in range(target_index + 1):
                library_list.action_cursor_down()
        self._highlight_index = target_index

        if current_index is not None and self._library_entries:
            try:
                library_list.index = max(0, min(current_index, len(self._library_entries) - 1))  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - defensive
                pass

    def _update_detail_panel(self, *, error: bool = False) -> None:
        """Refresh the detail panel content based on current selection state."""
        detail_panel = self.query_one("#detail-body", Static)

        if error:
            detail_panel.update("Unable to show details.")
            return

        if not self._selected_entries:
            detail_panel.update(self.app_config.detail_placeholder)
            return

        formatted = "\n".join(sorted(self._selected_entries, key=str.lower))
        detail_panel.update(
            f"Selected items ({len(self._selected_entries)}):\n{formatted}"
        )

    def action_toggle_option(self) -> None:
        """Toggle the selection state for the focused library entry."""
        focused = self.focused
        if isinstance(focused, OptionList):
            focused.action_select()

    @staticmethod
    def _option_index(option: Option) -> int | None:
        """Return the integer index encoded in an option id, if available."""
        option_id = option.id
        if not option_id:
            return None
        if not option_id.startswith("entry-"):
            return None

        try:
            index = int(option_id.split("-", 1)[1])
        except (IndexError, ValueError):
            return None

        return index if index >= 0 else None


if __name__ == "__main__":
    app = BandDropboxApp()
    app.run()

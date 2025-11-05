"""Textual application entry point for the band's Dropbox client."""

from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import Footer, Header, LoadingIndicator, Static

from .config import APP_CONFIG, AppConfig


class BandDropboxApp(App[None]):
    """Textual application with a simple splash screen and main layout."""

    CSS_PATH = "app.tcss"
    BINDINGS = [("q", "quit", "Quit")]

    is_loading = reactive(True)

    def __init__(self, *, app_config: AppConfig | None = None, **kwargs) -> None:
        """Allow injecting configuration, defaulting to the on-disk settings."""
        super().__init__(**kwargs)
        self.app_config = app_config or APP_CONFIG

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
                    Static(
                        self.app_config.library_placeholder,
                        classes="panel__body",
                    ),
                    classes="panel",
                    id="library-panel",
                ),
                Container(
                    Static(self.app_config.detail_title, classes="panel__title"),
                    Static(
                        self.app_config.detail_placeholder,
                        classes="panel__body",
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
        self.run_worker(self._simulate_startup(), exclusive=True)

    async def _simulate_startup(self) -> None:
        """Simulate asynchronous initialization before showing the main UI."""
        await asyncio.sleep(1.2)
        self.is_loading = False


if __name__ == "__main__":
    app = BandDropboxApp()
    app.run()

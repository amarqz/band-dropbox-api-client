from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, ProgressBar, RichLog, Static


class DownloadScreen(ModalScreen[None]):
    """Modal screen that shows download progress and log output."""

    BINDINGS = [("escape", "close", "Close")]

    def __init__(self) -> None:
        super().__init__()
        self._progress_bar: ProgressBar | None = None
        self._log: RichLog | None = None

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Downloads", classes="panel__title"),
            Vertical(
                ProgressBar(id="download-progress"),
                RichLog(id="download-log"),
                Container(
                    Button("Close", id="download-close"),
                    id="download-actions",
                ),
            ),
            id="download-modal",
        )

    def on_mount(self) -> None:
        self._progress_bar = self.query_one("#download-progress", ProgressBar)
        self._log = self.query_one("#download-log", RichLog)

    def action_close(self) -> None:
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "download-close":
            self.dismiss()

    def reset(self, total: int) -> None:
        if not self._progress_bar or not self._log:
            return
        self._progress_bar.update(total=total, progress=0)
        self._log.clear()
        self._log.write("Starting downloads...")

    def update_progress(self, completed: int, total: int) -> None:
        if not self._progress_bar or not self.is_attached:
            return
        self._progress_bar.update(total=total, progress=completed)

    def append_log(self, message: str) -> None:
        if not self._log or not self.is_attached:
            return
        self._log.write(message)

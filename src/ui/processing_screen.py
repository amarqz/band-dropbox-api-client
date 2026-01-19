from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, ProgressBar, RichLog, Static


class ProcessingScreen(ModalScreen[None]):
    """Modal screen that shows pipeline progress and log output."""

    BINDINGS = [("escape", "close", "Close")]

    def __init__(self) -> None:
        super().__init__()
        self._title: Static | None = None
        self._progress_bar: ProgressBar | None = None
        self._log: RichLog | None = None

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Processing", classes="panel__title", id="process-title"),
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
        self._title = self.query_one("#process-title", Static)
        self._progress_bar = self.query_one("#download-progress", ProgressBar)
        self._log = self.query_one("#download-log", RichLog)

    def action_close(self) -> None:
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "download-close":
            self.dismiss()

    def reset_downloads(self, total: int) -> None:
        self._reset(
            title="Downloads",
            total=total,
            message="Starting downloads...",
            clear_log=True,
        )

    def reset_export(self, total: int | None = None) -> None:
        export_total = total if total is not None else 1
        self._reset(
            title="Export",
            total=export_total,
            message="Starting export...",
            clear_log=False,
        )

    def update_progress(self, completed: int, total: int) -> None:
        if not self._progress_bar or not self.is_attached:
            return
        self._progress_bar.update(total=total, progress=completed)

    def append_log(self, message: str) -> None:
        if not self._log or not self.is_attached:
            return
        self._log.write(message)

    def _reset(
        self,
        *,
        title: str,
        total: int,
        message: str,
        clear_log: bool,
    ) -> None:
        if not self._progress_bar or not self._log:
            return
        if self._title:
            self._title.update(title)
        self._progress_bar.update(total=total, progress=0)
        if clear_log:
            self._log.clear()
        else:
            self._log.write("")
        self._log.write(message)

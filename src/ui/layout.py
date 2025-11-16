from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    LoadingIndicator,
    OptionList,
    Static,
)
from textual.widgets.option_list import Option

from ..config import AppConfig


def compose_layout(app_config: AppConfig) -> ComposeResult:
    """Yield the static layout used by the application."""
    yield Container(
        Static(app_config.title, classes="loading__title"),
        LoadingIndicator(id="loading__spinner"),
        Static(app_config.loading_message, classes="loading__subtitle"),
        id="loading-view",
    )

    yield Container(
        Header(show_clock=True),
        Horizontal(
            Container(
                Static(app_config.library_title, classes="panel__title"),
                Vertical(
                    OptionList(
                        Option(app_config.library_placeholder, disabled=True),
                        classes="panel__body",
                        id="library-list",
                    ),
                    Input(
                        placeholder="Filter items...",
                        id="library-filter",
                    ),
                    classes="library__body",
                ),
                classes="panel",
                id="library-panel",
            ),
            Vertical(
                Container(
                    Static(app_config.detail_title, classes="panel__title"),
                    Vertical(
                        VerticalScroll(
                            Horizontal(
                                Container(
                                    Static(
                                        "Selected items (0)",
                                        classes="detail__header",
                                        id="detail-library-title",
                                    ),
                                    VerticalScroll(
                                        Static(
                                            app_config.detail_library_placeholder,
                                            classes="panel__body detail__content",
                                            id="detail-library",
                                        ),
                                        classes="detail__section",
                                    ),
                                    classes="detail__column",
                                ),
                                Container(
                                    Static(
                                        "Instrument counts (0)",
                                        classes="detail__header",
                                        id="detail-instruments-title",
                                    ),
                                    VerticalScroll(
                                        Static(
                                            app_config.detail_instruments_placeholder,
                                            classes="panel__body detail__content",
                                            id="detail-instruments",
                                        ),
                                        classes="detail__section",
                                    ),
                                    classes="detail__column",
                                ),
                                id="detail-content",
                            ),
                            classes="detail__scroll",
                        ),
                        Horizontal(
                            Button(
                                "Undo",
                                id="detail-action-undo",
                            ),
                            Button(
                                "Clear",
                                id="detail-action-clear",
                            ),
                            Button(
                                "Start",
                                id="detail-action-start",
                            ),
                            classes="detail__actions",
                        ),
                        id="detail-body",
                    ),
                    classes="panel",
                    id="detail-panel",
                ),
                Container(
                    Static(app_config.instruments_title, classes="panel__title"),
                    OptionList(
                        Option(app_config.instruments_placeholder, disabled=True),
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

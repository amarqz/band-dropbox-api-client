from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from ..config import AppConfig


@dataclass
class DetailPanelContent:
    """Simple view model for the detail panel."""

    library_title: str
    library_body: str
    instruments_title: str
    instruments_body: str


def build_detail_panel_content(
    app_config: AppConfig,
    selected_entries: Iterable[str],
    instrument_counts: Mapping[str, int],
    *,
    error: bool = False,
) -> DetailPanelContent:
    """Return the strings that should populate the detail panel."""
    if error:
        return DetailPanelContent(
            library_title="Selected items (0)",
            library_body="Unable to show details.",
            instruments_title="Instrument counts (0)",
            instruments_body="Unable to show details.",
        )

    selected = sorted(selected_entries, key=str.lower)
    selected_count = len(selected)
    library_title = f"Selected items ({selected_count})"
    library_body = "\n".join(selected) if selected else app_config.detail_library_placeholder

    counted_instruments = [
        (entry, count)
        for entry, count in sorted(instrument_counts.items(), key=lambda item: item[0].lower())
        if count > 0
    ]
    instruments_title = f"Instrument counts ({len(counted_instruments)})"
    if counted_instruments:
        instruments_body = "\n".join(f"{entry}: {count}" for entry, count in counted_instruments)
    else:
        instruments_body = app_config.detail_instruments_placeholder

    return DetailPanelContent(
        library_title=library_title,
        library_body=library_body,
        instruments_title=instruments_title,
        instruments_body=instruments_body,
    )

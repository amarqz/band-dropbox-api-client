"""Extensible configuration dataclass for the TUI."""

from __future__ import annotations

import configparser
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

_CONFIG_FILENAME = "application.conf"


def _config_path(path: Path | None) -> Path:
    return path or Path(__file__).resolve().parent / "resources" / _CONFIG_FILENAME


@dataclass(frozen=True)
class AppConfig:
    """Typed application settings.

    Extend by adding new fields with sensible defaults; values are
    automatically pulled from ``application.conf`` when present.
    """

    title: str = "Band Dropbox Client"
    loading_message: str = "Warming up the stage..."
    library_title: str = "Library"
    library_placeholder: str = "Dropbox folders and files will appear here once the data layer is ready."
    detail_title: str = "Details"
    detail_placeholder: str = "Select an item to see its metadata and preview details."

    @classmethod
    def from_file(cls, path: Path | None = None) -> AppConfig:
        parser = configparser.ConfigParser()
        parser.read(_config_path(path), encoding="utf-8")

        merged: dict[str, str] = {}
        for section in parser.sections():
            merged.update(parser[section])

        init_values: dict[str, Any] = {}
        for field in fields(cls):
            value = merged.get(field.name)
            if value is None:
                continue
            cleaned = value.strip()
            if cleaned:
                init_values[field.name] = cleaned

        return cls(**init_values)

    def with_overrides(self, **overrides: Any) -> AppConfig:
        """Return a copy with explicit overrides."""
        current = {field.name: getattr(self, field.name) for field in fields(self)}
        current.update({key: value for key, value in overrides.items() if key in current})
        return AppConfig(**current)

    def as_dict(self) -> dict[str, Any]:
        """Expose a plain dict for diagnostics or templating."""
        return {field.name: getattr(self, field.name) for field in fields(self)}


APP_CONFIG = AppConfig.from_file()

__all__ = ["APP_CONFIG", "AppConfig"]


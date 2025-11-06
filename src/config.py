"""Extensible configuration dataclass for the TUI."""

from __future__ import annotations

import configparser
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, ClassVar, Sequence, TypeVar

_CONFIG_FILENAME = "application.conf"


def _config_path(path: Path | None) -> Path:
    return path or Path(__file__).resolve().parent / "resources" / _CONFIG_FILENAME

_ConfigT = TypeVar("_ConfigT", bound="BaseConfig")


class BaseConfig:
    """Base configuration class aggregating shared config helpers."""

    SECTION_NAMES: ClassVar[Sequence[str]] = ()

    @classmethod
    def _candidate_sections(cls) -> tuple[str, ...]:
        """Return the config sections that should populate this dataclass."""
        if cls.SECTION_NAMES:
            return tuple(dict.fromkeys(cls.SECTION_NAMES))

        name = cls.__name__
        suffix = "Config"
        if name.lower().endswith(suffix.lower()):
            name = name[: -len(suffix)]

        name = name or cls.__name__
        candidates = [name]
        lowered = name.lower()
        if lowered != name:
            candidates.append(lowered)

        return tuple(dict.fromkeys(candidates))

    @classmethod
    def from_file(cls: type[_ConfigT], path: Path | None = None) -> _ConfigT:
        parser = configparser.ConfigParser()
        parser.read(_config_path(path), encoding="utf-8")

        merged: dict[str, str] = dict(parser.defaults())
        for section in cls._candidate_sections():
            if parser.has_section(section):
                merged.update(parser[section])

        init_values: dict[str, Any] = {}
        for field in fields(cls): # type: ignore[attr-defined]
            value = merged.get(field.name)
            if value is None:
                continue
            cleaned = value.strip()
            if cleaned:
                init_values[field.name] = cleaned

        return cls(**init_values)

    def with_overrides(self: _ConfigT, **overrides: Any) -> _ConfigT:
        """Return a copy with explicit overrides."""
        current = {field.name: getattr(self, field.name) for field in fields(self)} # type: ignore[attr-defined]
        current.update({key: value for key, value in overrides.items() if key in current})
        return type(self)(**current)

    def as_dict(self) -> dict[str, Any]:
        """Expose a plain dict for diagnostics or templating."""
        return {field.name: getattr(self, field.name) for field in fields(self)} # type: ignore[attr-defined]


@dataclass(frozen=True)
class AppConfig(BaseConfig):
    """Typed application settings.

    Extend by adding new fields with sensible defaults; values are
    automatically pulled from ``application.conf`` when present.
    """

    title: str = "Band Dropbox Client"
    loading_message: str = "Warming up the stage..."
    library_title: str = "Library"
    library_path: str = ""
    library_suffix: str | None = None
    library_placeholder: str = "Dropbox folders and files will appear here once the data layer is ready."
    detail_title: str = "Details"
    detail_placeholder: str = "Select an item to see its metadata and preview details."

APP_CONFIG = AppConfig.from_file()

@dataclass(frozen=True)
class DropboxConfig(BaseConfig):
    """Typed Dropbox Client settings.
    
    Extend by adding new fields with sensible defaults; values are
    automatically pulled from ``application.conf`` when present.
    """
    
    access_token: str | None = None

DBX_CONFIG = DropboxConfig.from_file()

__all__ = ["APP_CONFIG", "AppConfig", "BaseConfig"]

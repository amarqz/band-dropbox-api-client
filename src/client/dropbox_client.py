"""Dropbox client abstraction"""

from __future__ import annotations

from pathlib import Path

import dropbox
from dropbox.exceptions import ApiError, AuthError

from src.config import DropboxConfig


class DropboxClient:
    """Thin wrapper around the Dropbox SDK with helper functions."""

    def __init__(self, config: DropboxConfig):
        self.config: DropboxConfig = config
        self._access_token: str | None = self.config.access_token
        self._dbx_client: dropbox.Dropbox | None = None

        if not self._access_token:
            raise Exception("Cannot connect! The DBX access token is missing in the configurations.")
        
        try:
            self._dbx_client = dropbox.Dropbox(self._access_token)
            self._dbx_client.users_get_current_account()
        except AuthError as e:
            raise Exception("Cannot connect!", e.error)

    def list_contents(self, path: str = "") -> list[str]:
        """Return a formatted listing of the contents for ``path``."""
        if not self._dbx_client:
            raise RuntimeError("Dropbox client is not connected.")

        entries = self.list_entries(path, recursive=False)
        names = [entry.name for entry in entries]
        return sorted(names, key=str.lower)

    def list_instrument_voices(self, path: str) -> list[str]:
        """Return a listing of instrument voices found under ``path``."""
        if not self._dbx_client:
            raise RuntimeError("Dropbox client is not connected.")

        normalized_path = self._normalize_path(path)
        entries = self.list_entries(path, recursive=True)

        instruments: set[str] = set()
        voices_by_instrument: dict[str, set[str]] = {}

        for entry in entries:
            entry_path = entry.path_display or entry.path_lower or ""
            parts = self._relative_parts(entry_path, normalized_path)
            if not parts:
                continue
            if len(parts) == 1 and isinstance(entry, dropbox.files.FolderMetadata):
                instruments.add(parts[0])
            elif len(parts) == 2 and isinstance(entry, dropbox.files.FolderMetadata):
                voices_by_instrument.setdefault(parts[0], set()).add(parts[1])

        voices: list[str] = []
        for instrument in sorted(instruments, key=str.lower):
            voice_names = voices_by_instrument.get(instrument)
            if voice_names:
                for voice in sorted(voice_names, key=str.lower):
                    voices.append(f"{instrument} / {voice}")
            else:
                voices.append(instrument)

        return voices

    def list_entries(
        self,
        path: str,
        *,
        recursive: bool = False,
    ) -> list[dropbox.files.Metadata]:
        """Return metadata entries for ``path``."""
        if not self._dbx_client:
            raise RuntimeError("Dropbox client is not connected.")

        normalized_path = self._normalize_path(path)
        return self._list_folder_entries(normalized_path, recursive=recursive)

    def download_file(self, dropbox_path: str, local_path: Path) -> None:
        """Download a Dropbox file to ``local_path``."""
        if not self._dbx_client:
            raise RuntimeError("Dropbox client is not connected.")

        local_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._dbx_client.files_download_to_file(str(local_path), dropbox_path)
        except ApiError as exc:
            raise Exception(f"Unable to download '{dropbox_path}'.") from exc

    @staticmethod
    def _normalize_path(path: str) -> str:
        normalized_path = path.strip()
        if normalized_path == "/":
            return ""
        return normalized_path

    def _list_folder_entries(
        self,
        normalized_path: str,
        recursive: bool,
    ) -> list[dropbox.files.Metadata]:
        try:
            list_result = self._dbx_client.files_list_folder(
                normalized_path,
                recursive=recursive,
            )
        except ApiError as exc:
            folder = normalized_path or "/"
            raise Exception(f"Unable to list folder '{folder}'.") from exc

        entries = list(list_result.entries) # type: ignore[attr-defined]

        while list_result.has_more: # type: ignore[attr-defined]
            list_result = self._dbx_client.files_list_folder_continue(list_result.cursor) # type: ignore[attr-defined]
            entries.extend(list_result.entries) # type: ignore[attr-defined]

        return entries

    @staticmethod
    def _relative_parts(entry_path: str, root_path: str) -> list[str]:
        if not entry_path:
            return []
        trimmed_root = root_path.rstrip("/")
        if trimmed_root:
            if not entry_path.lower().startswith(trimmed_root.lower()):
                return []
            trimmed = entry_path[len(trimmed_root) :]
        else:
            trimmed = entry_path
        trimmed = trimmed.strip("/")
        if not trimmed:
            return []
        return [part for part in trimmed.split("/") if part]

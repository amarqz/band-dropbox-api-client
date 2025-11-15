"""Dropbox client abstraction"""

from __future__ import annotations

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

        normalized_path = path.strip()
        if normalized_path == "/":
            normalized_path = ""

        try:
            list_result = self._dbx_client.files_list_folder(normalized_path)
        except ApiError as exc:
            folder = normalized_path or "/"
            raise Exception(f"Unable to list folder '{folder}'.") from exc

        entries: list[str] = []
        entries.extend(entry.name for entry in list_result.entries) # type: ignore[attr-defined]

        while list_result.has_more: # type: ignore[attr-defined]
            list_result = self._dbx_client.files_list_folder_continue(list_result.cursor) # type: ignore[attr-defined]
            entries.extend(entry.name for entry in list_result.entries) # type: ignore[attr-defined]

        return sorted(entries, key=str.lower)
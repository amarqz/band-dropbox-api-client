"""Dropbox client abstraction"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import dropbox
from dropbox.exceptions import ApiError, AuthError
from dropbox.oauth import DropboxOAuth2FlowNoRedirect

from src.config import DropboxConfig


@dataclass(frozen=True)
class OAuthToken:
    access_token: str
    refresh_token: str | None = None
    expires_at: float | None = None


def _resolve_token_cache_path(config: DropboxConfig) -> Path:
    return Path(os.path.expanduser(config.token_cache_path)).resolve()


def _load_cached_token(config: DropboxConfig) -> OAuthToken | None:
    cache_path = _resolve_token_cache_path(config)
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeError):
        return None
    access_token = payload.get("access_token")
    if not access_token:
        return None
    expires_at = payload.get("expires_at")
    if isinstance(expires_at, (int, float)):
        normalized_expires = float(expires_at)
    elif isinstance(expires_at, str):
        try:
            normalized_expires = float(expires_at)
        except ValueError:
            normalized_expires = None
    else:
        normalized_expires = None
    return OAuthToken(
        access_token=access_token,
        refresh_token=payload.get("refresh_token"),
        expires_at=normalized_expires,
    )


def _save_cached_token(config: DropboxConfig, token: OAuthToken) -> None:
    if isinstance(token.expires_at, datetime):
        expires_at = token.expires_at.astimezone(timezone.utc).timestamp()
    else:
        expires_at = token.expires_at
    cache_path = _resolve_token_cache_path(config)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "access_token": token.access_token,
        "refresh_token": token.refresh_token,
        "expires_at": expires_at,
    }
    cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _is_expired(expires_at: float | None) -> bool:
    if expires_at is None:
        return False
    # Keep a small skew so nearly-expired tokens are treated as expired.
    return expires_at <= time.time() + 30


def ensure_access_token(
    config: DropboxConfig,
    *,
    interactive: bool = True,
) -> DropboxConfig:
    """Ensure a usable access token, prompting for OAuth2 if needed."""
    cached = _load_cached_token(config)

    if config.access_token:
        if config.refresh_token:
            if cached and cached.refresh_token and _is_expired(cached.expires_at):
                return config.with_overrides(
                    access_token=None,
                    refresh_token=cached.refresh_token,
                )
            return config
        if cached and cached.refresh_token:
            if _is_expired(cached.expires_at):
                return config.with_overrides(
                    access_token=None,
                    refresh_token=cached.refresh_token,
                )
            return config.with_overrides(refresh_token=cached.refresh_token)
        return config

    if cached:
        if _is_expired(cached.expires_at):
            if cached.refresh_token and config.app_key:
                # Let SDK refresh with the refresh token.
                return config.with_overrides(
                    access_token=None,
                    refresh_token=cached.refresh_token,
                )
        else:
            return config.with_overrides(
                access_token=cached.access_token,
                refresh_token=cached.refresh_token,
            )
        return config.with_overrides(
            access_token=cached.access_token,
            refresh_token=cached.refresh_token,
        )

    if not interactive or not config.app_key:
        return config

    token_access_type = (config.token_access_type or "offline").strip() or "offline"
    use_pkce = not config.app_secret
    try:
        flow = DropboxOAuth2FlowNoRedirect(
            config.app_key,
            config.app_secret,
            token_access_type=token_access_type,
            use_pkce=use_pkce,
        )
    except TypeError:
        flow = DropboxOAuth2FlowNoRedirect(
            config.app_key,
            config.app_secret,
            token_access_type=token_access_type,
        )
    authorize_url = flow.start()
    print("\nDropbox authorization required.")
    print("1) Open this URL in your browser:")
    print(authorize_url)
    print("2) Click Allow, then copy the authorization code.")
    sys.stdout.flush()
    auth_code = input("Paste the authorization code here: ").strip()
    result = flow.finish(auth_code)
    token = OAuthToken(
        access_token=result.access_token,
        refresh_token=getattr(result, "refresh_token", None),
        expires_at=getattr(result, "expires_at", None),
    )
    _save_cached_token(config, token)
    return config.with_overrides(
        access_token=token.access_token,
        refresh_token=token.refresh_token,
    )


class DropboxClient:
    """Thin wrapper around the Dropbox SDK with helper functions."""

    def __init__(self, config: DropboxConfig):
        self.config: DropboxConfig = config
        self._access_token: str | None = self.config.access_token
        self._refresh_token: str | None = self.config.refresh_token
        self._dbx_client: dropbox.Dropbox | None = None

        if not self._access_token and not self._refresh_token:
            raise Exception("Cannot connect! The DBX access token is missing in the configurations.")
        
        try:
            if self._refresh_token and self.config.app_key:
                self._dbx_client = dropbox.Dropbox(
                    oauth2_access_token=self._access_token,
                    oauth2_refresh_token=self._refresh_token,
                    app_key=self.config.app_key,
                    app_secret=self.config.app_secret,
                )
                if self._is_expired_by_cached_metadata():
                    self._refresh_on_expiry_and_persist()
            elif self._access_token:
                self._dbx_client = dropbox.Dropbox(self._access_token)
            else:
                raise Exception(
                    "Cannot connect! The DBX refresh token requires app_key."
                )
            self._dbx_client.users_get_current_account()
            if self._access_token is None and self._refresh_token:
                self._persist_runtime_token()
        except AuthError as e:
            if self._refresh_on_auth_error_and_persist():
                return
            raise Exception("Cannot connect!", e.error)

    def _is_expired_by_cached_metadata(self) -> bool:
        if not self._access_token:
            return True
        cached = _load_cached_token(self.config)
        if not cached or not cached.refresh_token:
            return False
        if cached.access_token != self._access_token:
            return False
        return _is_expired(cached.expires_at)

    def _persist_runtime_token(self) -> None:
        if not self._dbx_client:
            return

        access_token = getattr(self._dbx_client, "_oauth2_access_token", None)
        refresh_token = getattr(self._dbx_client, "_oauth2_refresh_token", None)
        expires_at = getattr(self._dbx_client, "_oauth2_access_token_expiration", None)
        if not access_token or not refresh_token:
            return

        try:
            _save_cached_token(
                self.config,
                OAuthToken(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                ),
            )
        except OSError:
            return

    def _refresh_on_auth_error_and_persist(self) -> bool:
        if not self._dbx_client:
            return False
        if not self._refresh_token or not self.config.app_key:
            return False

        previous_access_token = getattr(self._dbx_client, "_oauth2_access_token", None)
        self._dbx_client.check_and_refresh_access_token()
        access_token = getattr(self._dbx_client, "_oauth2_access_token", None)
        refresh_token = getattr(self._dbx_client, "_oauth2_refresh_token", None)
        expires_at = getattr(self._dbx_client, "_oauth2_access_token_expiration", None)
        if not access_token or not refresh_token:
            return False
        if access_token == previous_access_token:
            return False

        self._dbx_client.users_get_current_account()

        try:
            _save_cached_token(
                self.config,
                OAuthToken(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                ),
            )
        except OSError:
            # Cache write failures should not block the app's Dropbox session.
            return True
        return True

    def _refresh_on_expiry_and_persist(self) -> None:
        if not self._dbx_client:
            return
        if not self._refresh_token or not self.config.app_key:
            return

        previous_access_token = getattr(self._dbx_client, "_oauth2_access_token", None)
        self._dbx_client.check_and_refresh_access_token()
        access_token = getattr(self._dbx_client, "_oauth2_access_token", None)
        refresh_token = getattr(self._dbx_client, "_oauth2_refresh_token", None)
        expires_at = getattr(self._dbx_client, "_oauth2_access_token_expiration", None)
        if not access_token or not refresh_token:
            return
        if access_token == previous_access_token:
            return

        try:
            _save_cached_token(
                self.config,
                OAuthToken(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                ),
            )
        except OSError:
            return

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

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.client.dropbox_client import DropboxClient, OAuthToken, ensure_access_token
from src.config import DropboxConfig


class FakeEntry:
    def __init__(self, name: str) -> None:
        self.name = name


class DropboxClientTests(unittest.TestCase):
    def test_requires_access_token(self) -> None:
        with self.assertRaises(Exception):
            DropboxClient(DropboxConfig(access_token=None))

    def test_list_contents_with_pagination(self) -> None:
        class FakeResult:
            def __init__(self, entries, has_more=False, cursor="cursor") -> None:
                self.entries = entries
                self.has_more = has_more
                self.cursor = cursor

        class FakeDropbox:
            def __init__(self, token: str) -> None:
                self.token = token

            def users_get_current_account(self) -> None:
                return None

            def files_list_folder(self, path: str, recursive: bool = False) -> FakeResult:
                self.first_path = path
                self.recursive_used = recursive
                return FakeResult(
                    [FakeEntry("bravo"), FakeEntry("alpha")],
                    has_more=True,
                    cursor="123",
                )

            def files_list_folder_continue(self, cursor: str) -> FakeResult:
                self.cursor_used = cursor
                return FakeResult([FakeEntry("charlie")])

        with patch("src.client.dropbox_client.dropbox.Dropbox", FakeDropbox):
            client = DropboxClient(DropboxConfig(access_token="token"))
            entries = client.list_contents(" /demo ")

        self.assertEqual(entries, ["alpha", "bravo", "charlie"])

    def test_list_contents_wraps_api_errors(self) -> None:
        class DummyApiError(Exception):
            pass

        class FakeDropbox:
            def __init__(self, *args, **kwargs):
                pass

            def users_get_current_account(self):
                return None

            def files_list_folder(self, path: str, recursive: bool = False):
                raise DummyApiError("boom")

        with patch("src.client.dropbox_client.dropbox.Dropbox", FakeDropbox):
            with patch("src.client.dropbox_client.ApiError", DummyApiError):
                client = DropboxClient(DropboxConfig(access_token="token"))
                with self.assertRaises(Exception) as exc:
                    client.list_contents("/demo")
                self.assertIn("Unable to list folder", str(exc.exception))

    def test_list_instrument_voices_flattens_recursive_folders(self) -> None:
        class FakeFolderMetadata:
            def __init__(self, name: str, path_display: str) -> None:
                self.name = name
                self.path_display = path_display
                self.path_lower = path_display.lower()

        class FakeResult:
            def __init__(self, entries, has_more=False, cursor="cursor") -> None:
                self.entries = entries
                self.has_more = has_more
                self.cursor = cursor

        class FakeDropbox:
            def __init__(self, token: str) -> None:
                self.token = token

            def users_get_current_account(self) -> None:
                return None

            def files_list_folder(self, path: str, recursive: bool = False) -> FakeResult:
                self.path_used = path
                self.recursive_used = recursive
                entries = [
                    FakeFolderMetadata("Trumpet", "/Band/Trumpet"),
                    FakeFolderMetadata("1", "/Band/Trumpet/1"),
                    FakeFolderMetadata("Trombone", "/Band/Trombone"),
                    FakeFolderMetadata("Clarinete", "/Band/Clarinete"),
                    FakeFolderMetadata("2", "/Band/Clarinete/2"),
                ]
                return FakeResult(entries)

            def files_list_folder_continue(self, cursor: str) -> FakeResult:
                return FakeResult([])

        with patch("src.client.dropbox_client.dropbox.Dropbox", FakeDropbox):
            with patch("src.client.dropbox_client.dropbox.files.FolderMetadata", FakeFolderMetadata):
                client = DropboxClient(DropboxConfig(access_token="token"))
                voices = client.list_instrument_voices("/Band")

        self.assertEqual(
            voices,
            ["Clarinete / 2", "Trombone", "Trumpet / 1"],
        )

    def test_ensure_access_token_adds_cached_refresh_token(self) -> None:
        config = DropboxConfig(access_token="expired-token")
        cached = OAuthToken(access_token="cached-token", refresh_token="refresh-token")

        with patch("src.client.dropbox_client._load_cached_token", return_value=cached):
            resolved = ensure_access_token(config, interactive=False)

        self.assertEqual(resolved.access_token, "expired-token")
        self.assertEqual(resolved.refresh_token, "refresh-token")

    def test_ensure_access_token_uses_refresh_for_expired_cached_token(self) -> None:
        config = DropboxConfig(app_key="app-key")
        cached = OAuthToken(
            access_token="expired-token",
            refresh_token="refresh-token",
            expires_at=0,
        )

        with patch("src.client.dropbox_client._load_cached_token", return_value=cached):
            resolved = ensure_access_token(config, interactive=False)

        self.assertIsNone(resolved.access_token)
        self.assertEqual(resolved.refresh_token, "refresh-token")

    def test_ensure_access_token_forces_refresh_when_config_token_is_expired(self) -> None:
        config = DropboxConfig(
            access_token="expired-token",
            refresh_token="refresh-token",
            app_key="app-key",
        )
        cached = OAuthToken(
            access_token="expired-token",
            refresh_token="refresh-token",
            expires_at=0,
        )

        with patch("src.client.dropbox_client._load_cached_token", return_value=cached):
            resolved = ensure_access_token(config, interactive=False)

        self.assertIsNone(resolved.access_token)
        self.assertEqual(resolved.refresh_token, "refresh-token")

    def test_refresh_token_flow_does_not_require_app_secret(self) -> None:
        seen_kwargs: dict[str, object] = {}

        class FakeDropbox:
            def __init__(self, *args, **kwargs) -> None:
                seen_kwargs.update(kwargs)

            def check_and_refresh_access_token(self) -> None:
                return None

            def users_get_current_account(self) -> None:
                return None

        with patch("src.client.dropbox_client.dropbox.Dropbox", FakeDropbox):
            DropboxClient(
                DropboxConfig(
                    access_token="expired-token",
                    refresh_token="refresh-token",
                    app_key="app-key",
                    app_secret=None,
                )
            )

        self.assertEqual(seen_kwargs["oauth2_refresh_token"], "refresh-token")
        self.assertEqual(seen_kwargs["app_key"], "app-key")
        self.assertIsNone(seen_kwargs["app_secret"])

    def test_refresh_token_flow_persists_runtime_token_cache(self) -> None:
        saved_token = None

        class DummyAuthError(Exception):
            def __init__(self, error: str = "expired") -> None:
                super().__init__(error)
                self.error = error

        class FakeDropbox:
            def __init__(self, *args, **kwargs) -> None:
                self._oauth2_access_token = "expired-token"
                self._oauth2_refresh_token = kwargs.get("oauth2_refresh_token")
                self._oauth2_access_token_expiration = 1234.0
                self._account_checks = 0

            def check_and_refresh_access_token(self) -> None:
                self._oauth2_access_token = "new-access-token"

            def users_get_current_account(self) -> None:
                self._account_checks += 1
                if self._account_checks == 1:
                    raise DummyAuthError("expired")
                return None

        def capture_save(_config, token):
            nonlocal saved_token
            saved_token = token

        with patch("src.client.dropbox_client.dropbox.Dropbox", FakeDropbox):
            with patch("src.client.dropbox_client.AuthError", DummyAuthError):
                with patch("src.client.dropbox_client._save_cached_token", side_effect=capture_save):
                    DropboxClient(
                        DropboxConfig(
                            access_token="expired-token",
                            refresh_token="refresh-token",
                            app_key="app-key",
                        )
                    )

        self.assertIsNotNone(saved_token)
        self.assertEqual(saved_token.access_token, "new-access-token")
        self.assertEqual(saved_token.refresh_token, "refresh-token")
        self.assertEqual(saved_token.expires_at, 1234.0)

    def test_refresh_token_flow_persists_when_cache_expired_metadata_matches_token(self) -> None:
        saved_token = None

        class FakeDropbox:
            def __init__(self, *args, **kwargs) -> None:
                self._oauth2_access_token = "expired-token"
                self._oauth2_refresh_token = kwargs.get("oauth2_refresh_token")
                self._oauth2_access_token_expiration = 2468.0

            def check_and_refresh_access_token(self) -> None:
                self._oauth2_access_token = "new-access-token"

            def users_get_current_account(self) -> None:
                return None

        def capture_save(_config, token):
            nonlocal saved_token
            saved_token = token

        with patch("src.client.dropbox_client.dropbox.Dropbox", FakeDropbox):
            with patch(
                "src.client.dropbox_client._load_cached_token",
                return_value=OAuthToken(
                    access_token="expired-token",
                    refresh_token="refresh-token",
                    expires_at=0,
                ),
            ):
                with patch("src.client.dropbox_client._save_cached_token", side_effect=capture_save):
                    DropboxClient(
                        DropboxConfig(
                            access_token="expired-token",
                            refresh_token="refresh-token",
                            app_key="app-key",
                        )
                    )

        self.assertIsNotNone(saved_token)
        self.assertEqual(saved_token.access_token, "new-access-token")
        self.assertEqual(saved_token.refresh_token, "refresh-token")
        self.assertEqual(saved_token.expires_at, 2468.0)

    def test_refresh_token_bootstrap_persists_when_no_access_token_is_provided(self) -> None:
        saved_token = None

        class FakeDropbox:
            def __init__(self, *args, **kwargs) -> None:
                self._oauth2_access_token = None
                self._oauth2_refresh_token = kwargs.get("oauth2_refresh_token")
                self._oauth2_access_token_expiration = 5678.0

            def check_and_refresh_access_token(self) -> None:
                self._oauth2_access_token = "new-access-token"

            def users_get_current_account(self) -> None:
                return None

        def capture_save(_config, token):
            nonlocal saved_token
            saved_token = token

        with patch("src.client.dropbox_client.dropbox.Dropbox", FakeDropbox):
            with patch("src.client.dropbox_client._save_cached_token", side_effect=capture_save):
                DropboxClient(
                    DropboxConfig(
                        access_token=None,
                        refresh_token="refresh-token",
                        app_key="app-key",
                    )
                )

        self.assertIsNotNone(saved_token)
        self.assertEqual(saved_token.access_token, "new-access-token")
        self.assertEqual(saved_token.refresh_token, "refresh-token")
        self.assertEqual(saved_token.expires_at, 5678.0)

    def test_refresh_token_flow_does_not_persist_when_token_not_refreshed(self) -> None:
        class FakeDropbox:
            def __init__(self, *args, **kwargs) -> None:
                self._oauth2_access_token = "still-valid-token"
                self._oauth2_refresh_token = kwargs.get("oauth2_refresh_token")
                self._oauth2_access_token_expiration = 9999.0

            def users_get_current_account(self) -> None:
                return None

        with patch("src.client.dropbox_client.dropbox.Dropbox", FakeDropbox):
            with patch("src.client.dropbox_client._save_cached_token") as save_mock:
                DropboxClient(
                    DropboxConfig(
                        access_token="still-valid-token",
                        refresh_token="refresh-token",
                        app_key="app-key",
                    )
                )

        save_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()

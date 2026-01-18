from __future__ import annotations

import unittest
from unittest.mock import patch

from src.client.dropbox_client import DropboxClient
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


if __name__ == "__main__":
    unittest.main()

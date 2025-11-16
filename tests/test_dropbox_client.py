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

            def files_list_folder(self, path: str) -> FakeResult:
                self.first_path = path
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

            def files_list_folder(self, path: str):
                raise DummyApiError("boom")

        with patch("src.client.dropbox_client.dropbox.Dropbox", FakeDropbox):
            with patch("src.client.dropbox_client.ApiError", DummyApiError):
                client = DropboxClient(DropboxConfig(access_token="token"))
                with self.assertRaises(Exception) as exc:
                    client.list_contents("/demo")
                self.assertIn("Unable to list folder", str(exc.exception))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import asyncio
import unittest

from src.config import AppConfig, DropboxConfig
from src.services.startup import load_initial_data


class FakeDropboxClient:
    def __init__(self, library: list[str], instruments: list[str]) -> None:
        self._library = library
        self._instruments = instruments

    def list_contents(self, path: str):
        if "library" in path:
            return list(self._library)
        raise ValueError(path)

    def list_instrument_voices(self, path: str):
        if "inst" in path:
            return list(self._instruments)
        raise ValueError(path)


class StartupServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app_config = AppConfig(
            library_path="/library",
            instruments_path=" inst ",
        )
        self.dbx_config = DropboxConfig(access_token="token")

    def test_load_initial_data_success(self) -> None:
        async def run() -> None:
            result = await load_initial_data(
                self.app_config,
                self.dbx_config,
                client_factory=lambda _: FakeDropboxClient(
                    library=["file-a", "file-b"],
                    instruments=["inst-1"],
                ),
            )
            self.assertEqual(result.library_entries, ["file-a", "file-b"])
            self.assertEqual(result.instrument_entries, ["inst-1"])
            self.assertIsNone(result.library_error)

        asyncio.run(run())

    def test_load_initial_data_with_errors(self) -> None:
        async def run() -> None:
            def failing_factory(_):
                raise RuntimeError("boom")

            result = await load_initial_data(
                self.app_config,
                self.dbx_config,
                client_factory=failing_factory,
            )
            self.assertIsNone(result.library_entries)
            self.assertEqual(result.library_error, "boom")
            self.assertEqual(result.instrument_error, "boom")

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()

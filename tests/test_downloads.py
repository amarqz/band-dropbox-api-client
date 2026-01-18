from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.services.downloads import InstrumentSelection, download_selected_pdfs


class DownloadsTests(unittest.TestCase):
    def test_downloads_match_titles_and_skip_existing(self) -> None:
        class FakeFileMetadata:
            def __init__(self, name: str, path_display: str) -> None:
                self.name = name
                self.path_display = path_display
                self.path_lower = path_display.lower()

        class FakeDropboxClient:
            def __init__(self) -> None:
                self.downloaded: list[str] = []

            def list_entries(self, path: str, *, recursive: bool = False):
                return [
                    FakeFileMetadata("Song A.pdf", f"{path}/Song A.pdf"),
                    FakeFileMetadata("Song B.PDF", f"{path}/Song B.PDF"),
                ]

            def download_file(self, dropbox_path: str, local_path: Path) -> None:
                self.downloaded.append(dropbox_path)
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_text("pdf")

        with tempfile.TemporaryDirectory() as tmp_dir:
            download_root = Path(tmp_dir)
            existing_path = download_root / "Trumpet" / "Song A.pdf"
            existing_path.parent.mkdir(parents=True, exist_ok=True)
            existing_path.write_text("existing")

            client = FakeDropboxClient()
            instruments = [InstrumentSelection(display="Trumpet", raw="Trumpet")]

            with patch("src.services.downloads.dropbox.files.FileMetadata", FakeFileMetadata):
                summary = download_selected_pdfs(
                    client,
                    titles=["Song A", "Song B"],
                    instruments=instruments,
                    instruments_path="/Band",
                    download_root=download_root,
                )

        self.assertEqual(len(summary.downloaded), 1)
        self.assertEqual(len(summary.skipped), 1)
        self.assertEqual(len(summary.missing), 0)
        self.assertIn("/band/trumpet/song b.pdf", client.downloaded)

    def test_downloads_reports_missing_titles(self) -> None:
        class FakeFileMetadata:
            def __init__(self, name: str, path_display: str) -> None:
                self.name = name
                self.path_display = path_display
                self.path_lower = path_display.lower()

        class FakeDropboxClient:
            def list_entries(self, path: str, *, recursive: bool = False):
                return [FakeFileMetadata("Other.pdf", f"{path}/Other.pdf")]

            def download_file(self, dropbox_path: str, local_path: Path) -> None:
                raise AssertionError("Should not be called")

        client = FakeDropboxClient()
        instruments = [InstrumentSelection(display="Flute / 1", raw="Flute / 1")]

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("src.services.downloads.dropbox.files.FileMetadata", FakeFileMetadata):
                summary = download_selected_pdfs(
                    client,
                    titles=["Missing"],
                    instruments=instruments,
                    instruments_path="/Band",
                    download_root=Path(tmp_dir),
                )

        self.assertEqual(summary.downloaded, ())
        self.assertEqual(summary.skipped, ())
        self.assertEqual(summary.missing, ("Flute / 1: Missing",))


if __name__ == "__main__":
    unittest.main()

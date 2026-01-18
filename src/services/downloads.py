from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import dropbox

from ..client.dropbox_client import DropboxClient


@dataclass(frozen=True)
class InstrumentSelection:
    display: str
    raw: str


@dataclass(frozen=True)
class DownloadSummary:
    downloaded: tuple[str, ...]
    skipped: tuple[str, ...]
    missing: tuple[str, ...]


def download_selected_pdfs(
    client: DropboxClient,
    *,
    titles: Iterable[str],
    instruments: Iterable[InstrumentSelection],
    instruments_path: str,
    download_root: Path,
) -> DownloadSummary:
    normalized_titles = sorted({title.strip() for title in titles if title.strip()}, key=str.lower)
    if not normalized_titles:
        return DownloadSummary(downloaded=(), skipped=(), missing=())

    downloaded: list[str] = []
    skipped: list[str] = []
    missing: list[str] = []

    for instrument in instruments:
        folder_path = _join_dropbox_path(instruments_path, *instrument.raw.split(" / "))
        entries = client.list_entries(folder_path, recursive=False)
        files = [
            entry
            for entry in entries
            if isinstance(entry, dropbox.files.FileMetadata)
            and entry.name.lower().endswith(".pdf")
        ]

        for title in normalized_titles:
            match = _match_pdf_for_title(files, title)
            if not match:
                missing.append(f"{instrument.display}: {title}")
                continue
            local_path = download_root.joinpath(*instrument.display.split(" / "), match.name)
            if local_path.exists():
                skipped.append(str(local_path))
                continue
            dropbox_path = match.path_lower or match.path_display or ""
            if not dropbox_path:
                missing.append(f"{instrument.display}: {title}")
                continue
            client.download_file(dropbox_path, local_path)
            downloaded.append(str(local_path))

    return DownloadSummary(
        downloaded=tuple(downloaded),
        skipped=tuple(skipped),
        missing=tuple(missing),
    )


def _match_pdf_for_title(
    files: Sequence[dropbox.files.FileMetadata],
    title: str,
) -> dropbox.files.FileMetadata | None:
    normalized_title = title.strip().lower()
    if not normalized_title:
        return None

    for entry in files:
        name_lower = entry.name.lower()
        if name_lower == normalized_title:
            return entry
        if name_lower.endswith(".pdf") and name_lower[:-4] == normalized_title:
            return entry

    starts_with = [
        entry for entry in files if entry.name.lower().startswith(normalized_title)
    ]
    if starts_with:
        return min(starts_with, key=lambda entry: len(entry.name))

    contains = [
        entry for entry in files if normalized_title in entry.name.lower()
    ]
    if contains:
        return min(contains, key=lambda entry: len(entry.name))

    return None


def _join_dropbox_path(root: str, *parts: str) -> str:
    cleaned_root = root.strip().rstrip("/")
    cleaned_parts = [part.strip().strip("/") for part in parts if part.strip()]
    if cleaned_root:
        return f"{cleaned_root}/" + "/".join(cleaned_parts)
    if cleaned_parts:
        return "/" + "/".join(cleaned_parts)
    return ""

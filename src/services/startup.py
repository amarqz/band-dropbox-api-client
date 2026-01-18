from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable, Iterable

from ..client.dropbox_client import DropboxClient
from ..config import AppConfig, DropboxConfig


@dataclass
class StartupResult:
    """Aggregated data returned from the initial Dropbox fetches."""

    library_entries: list[str] | None = None
    library_error: str | None = None
    instrument_entries: list[str] | None = None
    instrument_error: str | None = None


DropboxClientFactory = Callable[[DropboxConfig], DropboxClient]


async def load_initial_data(
    app_config: AppConfig,
    dbx_config: DropboxConfig,
    client_factory: DropboxClientFactory = DropboxClient,
) -> StartupResult:
    """Connect to Dropbox and fetch library/instrument contents."""
    result = StartupResult()
    try:
        client = await asyncio.to_thread(client_factory, dbx_config)
    except Exception as exc:  # pragma: no cover - defensive
        message = str(exc)
        result.library_error = message
        if app_config.instruments_path:
            result.instrument_error = message
        return result

    tasks: list[asyncio.Future[Iterable[str]]] = [
        asyncio.to_thread(client.list_contents, app_config.library_path)
    ]

    instrument_task_index: int | None = None
    instrument_path = app_config.instruments_path
    if instrument_path:
        instrument_task_index = len(tasks)
        tasks.append(asyncio.to_thread(client.list_instrument_voices, instrument_path.strip()))

    responses = await asyncio.gather(*tasks, return_exceptions=True)

    library_result = responses[0]
    if isinstance(library_result, Exception):
        result.library_error = str(library_result)
    else:
        result.library_entries = list(library_result)

    if instrument_task_index is not None and instrument_task_index < len(responses):
        instrument_result = responses[instrument_task_index]
        if isinstance(instrument_result, Exception):
            result.instrument_error = str(instrument_result)
        else:
            result.instrument_entries = list(instrument_result)

    return result

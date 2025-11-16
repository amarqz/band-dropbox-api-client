from __future__ import annotations

import asyncio
import unittest

from src.config import AppConfig
from src.ui.commands import StartCommandProvider
from src.ui.layout import compose_layout


class DummyApp:
    def __init__(self) -> None:
        self.calls = 0

    def action_start_detail_action(self) -> None:
        self.calls += 1


class UICommandTests(unittest.TestCase):
    def test_start_command_provider(self) -> None:
        dummy_app = DummyApp()

        class DummyScreen:
            def __init__(self, app) -> None:
                self.app = app

        provider = StartCommandProvider(screen=DummyScreen(dummy_app))

        async def collect_search():
            hits = []
            async for hit in provider.search("start"):
                hits.append(hit)
            return hits

        hits = asyncio.run(collect_search())
        self.assertTrue(hits)

        async def collect_discover():
            hits = []
            async for hit in provider.discover():
                hits.append(hit)
            return hits

        discover_hits = asyncio.run(collect_discover())
        self.assertEqual(len(discover_hits), 1)

        provider._trigger_start()
        self.assertEqual(dummy_app.calls, 1)


class LayoutTests(unittest.TestCase):
    def test_compose_layout_returns_expected_structure(self) -> None:
        config = AppConfig()
        nodes = list(compose_layout(config))
        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0].id, "loading-view")
        self.assertEqual(nodes[1].id, "main-view")


if __name__ == "__main__":
    unittest.main()

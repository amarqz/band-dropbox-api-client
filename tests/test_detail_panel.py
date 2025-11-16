from __future__ import annotations

import unittest

from src.config import AppConfig
from src.ui.detail_panel import build_detail_panel_content


class DetailPanelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = AppConfig()

    def test_error_state(self) -> None:
        content = build_detail_panel_content(
            self.config,
            selected_entries=[],
            instrument_counts={},
            error=True,
        )
        self.assertIn("Unable to show details", content.library_body)
        self.assertIn("Instrument counts (0)", content.instruments_title)

    def test_normal_state(self) -> None:
        content = build_detail_panel_content(
            self.config,
            selected_entries=["Bravo", "alpha"],
            instrument_counts={"Guitar": 2, "Bass": 0},
        )
        self.assertEqual(content.library_title, "Selected items (2)")
        self.assertIn("alpha", content.library_body.splitlines()[0])
        self.assertIn("Guitar: 2", content.instruments_body)


if __name__ == "__main__":
    unittest.main()

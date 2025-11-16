from __future__ import annotations

import unittest

from textual.widgets.option_list import Option

from src.controllers.library import LibraryController
from tests.helpers import OptionListStub


class LibraryControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = LibraryController("Empty")
        self.option_list = OptionListStub("library-list")

    def test_refresh_options_populates_entries_and_selection_markers(self) -> None:
        self.controller.load_entries(["Alpha", "Beta"])
        self.controller.refresh_options(self.option_list)
        self.assertEqual(len(self.option_list.options), 2)
        self.assertTrue(self.option_list.options[0].prompt.plain.startswith("[ ]"))

        self.controller.toggle_entry("Alpha")
        self.controller.refresh_options(self.option_list)
        self.assertTrue(self.option_list.options[0].prompt.plain.startswith("[x]"))

    def test_filter_is_applied_and_reset(self) -> None:
        self.controller.load_entries(["Alpha", "Beta"])
        self.controller.set_filter_text("be")
        self.controller.refresh_options(self.option_list)
        self.assertEqual(len(self.option_list.options), 1)
        self.assertIn("Beta", self.option_list.options[0].prompt.plain)

        self.controller.clear_filter()
        self.controller.refresh_options(self.option_list)
        self.assertEqual(len(self.option_list.options), 2)

    def test_load_entries_reapplies_existing_filter(self) -> None:
        self.controller.load_entries(["Alpha"])
        self.controller.set_filter_text("gamma")
        self.controller.load_entries(["Gamma", "Delta"])
        self.controller.refresh_options(self.option_list)
        self.assertEqual(len(self.option_list.options), 1)
        self.assertIn("Gamma", self.option_list.options[0].prompt.plain)

    def test_empty_state_shows_placeholder_message(self) -> None:
        self.controller.load_entries([])
        self.controller.refresh_options(self.option_list)
        self.assertEqual(len(self.option_list.options), 1)
        self.assertTrue(self.option_list.options[0].disabled)

    def test_clear_selections_resets_state(self) -> None:
        self.controller.load_entries(["Alpha"])
        self.controller.toggle_entry("Alpha")
        self.assertTrue(self.controller.clear_selections())
        self.assertFalse(self.controller.selected_entries)
        self.assertFalse(self.controller.clear_selections())

    def test_restore_selection(self) -> None:
        self.controller.load_entries(["Alpha"])
        self.controller.toggle_entry("Alpha")
        self.controller.restore_selection("Alpha", False)
        self.assertNotIn("Alpha", self.controller.selected_entries)
        self.controller.restore_selection("Alpha", True)
        self.assertIn("Alpha", self.controller.selected_entries)


if __name__ == "__main__":
    unittest.main()

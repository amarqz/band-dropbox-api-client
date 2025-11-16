from __future__ import annotations

import unittest

from src.controllers.instruments import InstrumentController
from tests.helpers import OptionListStub


class InstrumentControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = InstrumentController(
            placeholder="No instruments",
            empty_message="Empty",
            suffix=".inst",
            exclude_substrings=("skip",),
        )
        self.option_list = OptionListStub("instrument-list")

    def test_load_entries_processes_suffix_and_exclusions(self) -> None:
        self.controller.load_entries(
            ["[D] Guitar.inst", "[F] skip-me.inst", "[A] Bass.inst"]
        )
        self.assertEqual(self.controller.entries, ["Bass", "Guitar"])

    def test_adjust_count_respects_bounds(self) -> None:
        self.controller.load_entries(["Guitar"])
        action = self.controller.adjust_count("Guitar", 2)
        self.assertIsNotNone(action)
        self.assertEqual(self.controller.counts["Guitar"], 2)
        negative_action = self.controller.adjust_count("Guitar", -5)
        self.assertIsNotNone(negative_action)
        self.assertEqual(negative_action.delta, -2)
        self.assertEqual(self.controller.counts["Guitar"], 0)

    def test_clear_counts(self) -> None:
        self.controller.load_entries(["Guitar"])
        self.controller.adjust_count("Guitar", 1)
        self.assertTrue(self.controller.clear_counts())
        self.assertFalse(self.controller.clear_counts())

    def test_refresh_options_handles_empty_state(self) -> None:
        self.controller.load_entries([])
        self.controller.refresh_options(self.option_list)
        self.assertEqual(len(self.option_list.options), 1)
        self.assertTrue(self.option_list.options[0].disabled)

    def test_refresh_options_with_counts(self) -> None:
        self.controller.load_entries(["Guitar"])
        self.controller.adjust_count("Guitar", 2)
        self.controller.refresh_options(self.option_list)
        self.assertEqual(len(self.option_list.options), 1)
        self.assertIn("Guitar", self.option_list.options[0].prompt.plain)
        self.assertIn("[2]", self.option_list.options[0].prompt.plain)

    def test_parse_exclusions(self) -> None:
        result = InstrumentController.parse_exclusions(" drums , , keys ")
        self.assertEqual(result, ("drums", "keys"))
        self.assertEqual(InstrumentController.parse_exclusions(None), ())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from src.ui import options as option_utils
from tests.helpers import OptionListStub


class OptionHelpersTests(unittest.TestCase):
    def test_option_index_parses_identifier(self) -> None:
        class DummyOption:
            def __init__(self, option_id: str | None) -> None:
                self.id = option_id

        self.assertEqual(option_utils.option_index(DummyOption("entry-12")), 12)
        self.assertIsNone(option_utils.option_index(DummyOption(None)))
        self.assertIsNone(option_utils.option_index(DummyOption("invalid")))

    def test_focus_option_sets_index_or_falls_back(self) -> None:
        option_list = OptionListStub()
        option_list.options = ["a", "b", "c"]
        option_utils.focus_option(option_list, 2)
        self.assertEqual(option_list.index, 2)

        class BlockingOptionList(OptionListStub):
            def __init__(self) -> None:
                super().__init__()
                self.block_next = True

            def __setattr__(self, name, value):
                if name == "index" and getattr(self, "block_next", False):
                    super().__setattr__("block_next", False)
                    raise RuntimeError("block")
                super().__setattr__(name, value)

        blocking_list = BlockingOptionList()
        blocking_list.options = ["a", "b", "c"]
        option_utils.focus_option(blocking_list, 1)
        self.assertEqual(blocking_list.index, 2)


if __name__ == "__main__":
    unittest.main()

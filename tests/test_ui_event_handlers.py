from __future__ import annotations

import unittest

from textual.widgets.option_list import Option

from src.actions import ActionHistory
from src.controllers.instruments import InstrumentController
from src.controllers.library import LibraryController
from src.ui.event_handlers import InstrumentEventHandler, LibraryEventHandler
from tests.helpers import OptionListStub


class OptionSelectedEvent:
    def __init__(self, option_list, option, input_event=None) -> None:
        self.option_list = option_list
        self.option = option
        self.input_event = input_event


class OptionHighlightedEvent:
    def __init__(self, option_list, option) -> None:
        self.option_list = option_list
        self.option = option


class EventHandlerTests(unittest.TestCase):
    def test_library_event_handler_selects_and_filters(self) -> None:
        controller = LibraryController("Empty")
        controller.load_entries(["Alpha", "Beta"])
        option_list = OptionListStub("library-list")
        controller.refresh_options(option_list)

        history = ActionHistory()
        refreshed = {"count": 0}

        handler = LibraryEventHandler(
            controller=controller,
            history=history,
            get_option_list=lambda: option_list,
            refresh_detail=lambda: refreshed.__setitem__("count", refreshed["count"] + 1),
        )

        event = OptionSelectedEvent(option_list, Option("Alpha", id="entry-0"))
        self.assertTrue(handler.handle_option_selected(event))
        action = history.pop()
        self.assertIsNotNone(action)
        self.assertEqual(action.entry, "Alpha")
        self.assertEqual(refreshed["count"], 1)

        highlight_event = OptionHighlightedEvent(option_list, Option("Alpha", id="entry-0"))
        self.assertTrue(handler.handle_option_highlighted(highlight_event))
        self.assertEqual(controller.highlight_index, 0)

        handler.handle_filter_changed("be")
        self.assertEqual(controller.filtered_entries, ["Beta"])
        handler.clear_filter()
        self.assertEqual(len(controller.filtered_entries), 2)

    def test_instrument_event_handler_increments_and_refreshes(self) -> None:
        controller = InstrumentController(
            placeholder="None",
            empty_message="Empty",
        )
        controller.load_entries(["Guitar"])
        option_list = OptionListStub("instrument-list")
        controller.refresh_options(option_list)
        history = ActionHistory()
        refresh_calls: list[int] = []

        handler = InstrumentEventHandler(
            controller=controller,
            history=history,
            get_option_list=lambda: option_list,
            refresh_detail=lambda: refresh_calls.append(1),
        )

        event = OptionSelectedEvent(option_list, Option("Guitar", id="instrument-0"))
        self.assertTrue(handler.handle_option_selected(event))
        self.assertEqual(controller.counts["Guitar"], 1)
        self.assertTrue(handler.handle_option_highlighted(OptionHighlightedEvent(option_list, Option("Guitar", id="instrument-0"))))
        handler.refresh_options()
        self.assertGreaterEqual(len(refresh_calls), 1)


if __name__ == "__main__":
    unittest.main()

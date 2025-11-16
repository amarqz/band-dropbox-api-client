from __future__ import annotations

import unittest

from src.actions import ActionHistory, InstrumentAction, SelectionAction


class ActionHistoryTests(unittest.TestCase):
    def test_push_pop_and_iterate(self) -> None:
        history = ActionHistory()
        self.assertFalse(history)

        first = SelectionAction("entry", False)
        second = InstrumentAction("guitar", 1)

        history.push(first)
        history.push(second)
        self.assertTrue(history)

        self.assertEqual(list(history), [first, second])
        self.assertEqual(history.pop(), second)
        self.assertEqual(history.pop(), first)
        self.assertIsNone(history.pop())
        self.assertFalse(history)


if __name__ == "__main__":
    unittest.main()

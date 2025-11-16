from __future__ import annotations

import unittest

from src import util


class UtilTests(unittest.TestCase):
    def test_strip_suffix_removes_when_present(self) -> None:
        self.assertEqual(util.strip_suffix("hello.txt", ".txt"), "hello")

    def test_strip_suffix_leaves_intact(self) -> None:
        self.assertEqual(util.strip_suffix("hello.txt", ".pdf"), "hello.txt")

    def test_contains_any_substring(self) -> None:
        substrings = ["foo", "bar"]
        self.assertTrue(util.contains_any_substring("a foobar b", substrings))
        self.assertFalse(util.contains_any_substring("bazqux", substrings))

    def test_remove_library_suffix_delegates(self) -> None:
        self.assertEqual(util.remove_library_suffix("demo.suf", ".suf"), "demo")


if __name__ == "__main__":
    unittest.main()

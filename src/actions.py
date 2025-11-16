from __future__ import annotations

from collections.abc import Iterator
from typing import NamedTuple


class SelectionAction(NamedTuple):
    """Represents a library selection toggle that can be undone."""

    entry: str
    previous_state: bool


class InstrumentAction(NamedTuple):
    """Represents an instrument count adjustment."""

    entry: str
    delta: int


Action = SelectionAction | InstrumentAction


class ActionHistory:
    """Simple stack to record reversible actions."""

    def __init__(self) -> None:
        self._actions: list[Action] = []

    def push(self, action: Action) -> None:
        self._actions.append(action)

    def pop(self) -> Action | None:
        if not self._actions:
            return None
        return self._actions.pop()

    def clear(self) -> None:
        self._actions.clear()

    def __bool__(self) -> bool:
        return bool(self._actions)

    def __iter__(self) -> Iterator[Action]:
        return iter(self._actions)

from __future__ import annotations

from textual.command import DiscoveryHit, Hit, Provider


class StartCommandProvider(Provider):
    """Expose the start action through Textual's command palette."""

    _COMMAND_LABEL = "Start action"

    async def search(self, query: str):
        """Return hits for palette searches."""
        matcher = self.matcher(query)
        score = matcher.match(self._COMMAND_LABEL)
        if score:
            yield Hit(
                score,
                matcher.highlight(self._COMMAND_LABEL),
                self._trigger_start,
                text=self._COMMAND_LABEL,
                help="Trigger the Start action for the detail panel.",
            )

    async def discover(self):
        """Provide a default hit when the palette opens."""
        yield DiscoveryHit(
            self._COMMAND_LABEL,
            self._trigger_start,
            text=self._COMMAND_LABEL,
            help="Trigger the Start action for the detail panel.",
        )

    def _trigger_start(self) -> None:
        """Invoke the application's start action."""
        self.app.action_start_detail_action()

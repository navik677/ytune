"""Search view widget — search tab for finding music on YouTube Music."""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Input, Static, Label, RadioSet, RadioButton
from textual.widget import Widget
from textual.message import Message

from ytune.models import Track
from ytune.widgets.track_table import TrackTable

log = logging.getLogger(__name__)


class SearchView(Widget):
    """Search tab — input field, filter buttons, and results table."""

    DEFAULT_CSS = """
    SearchView {
        height: 1fr;
        width: 1fr;
    }
    SearchView #search-bar {
        height: auto;
        padding: 1 1 0 1;
    }
    SearchView #search-input {
        width: 1fr;
        border: round #6d28d9;
        background: #0f0a1e;
        color: #e2e8f0;
    }
    SearchView #search-input:focus {
        border: round #a855f7;
    }
    SearchView #search-filters {
        height: auto;
        padding: 0 1;
        margin: 0 0 0 0;
    }
    SearchView #search-status {
        height: 1;
        padding: 0 1;
        color: #64748b;
    }
    SearchView #search-results {
        height: 1fr;
    }
    SearchView .filter-btn {
        min-width: 12;
        margin: 0 1 0 0;
        background: #1e1b4b;
        color: #a78bfa;
        border: none;
        height: 1;
    }
    SearchView .filter-btn.-active {
        background: #6d28d9;
        color: #f5f3ff;
        text-style: bold;
    }
    """

    class PlayTrack(Message):
        """Request to play a track."""
        def __init__(self, track: Track) -> None:
            self.track = track
            super().__init__()

    class AddToQueue(Message):
        """Request to add a track to queue."""
        def __init__(self, track: Track) -> None:
            self.track = track
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_filter = "songs"

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(id="search-bar"):
                yield Input(
                    placeholder="🔍 Search YouTube Music...",
                    id="search-input",
                )
            with Horizontal(id="search-filters"):
                yield Label("Filter: ", classes="filter-label")
                yield Static("⦿ Songs", classes="filter-btn -active", id="filter-songs")
                yield Static("◯ Albums", classes="filter-btn", id="filter-albums")
                yield Static("◯ Artists", classes="filter-btn", id="filter-artists")
            yield Static("Type to search", id="search-status")
            yield TrackTable(show_index=True, id="search-results")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle search submission."""
        query = event.value.strip()
        if query:
            self._perform_search(query)

    def _perform_search(self, query: str) -> None:
        """Start a search."""
        status = self.query_one("#search-status", Static)
        status.update(f"Searching for '{query}'...")
        self.run_worker(self._do_search(query), exclusive=True, name="search")

    async def _do_search(self, query: str) -> None:
        """Execute the search in background."""
        try:
            app = self.app
            if hasattr(app, "ytmusic"):
                tracks = await app.ytmusic.search(query, filter_type=self._current_filter)
                table = self.query_one("#search-results", TrackTable)
                table.load_tracks(tracks)
                status = self.query_one("#search-status", Static)
                count = len(tracks)
                status.update(f"Found {count} result{'s' if count != 1 else ''} for '{query}'")
            else:
                status = self.query_one("#search-status", Static)
                status.update("YouTube Music client not available")
        except Exception as e:
            log.error("Search failed: %s", e)
            status = self.query_one("#search-status", Static)
            status.update(f"Search error: {e}")

    def on_click(self, event) -> None:
        """Handle filter button clicks."""
        widget = event.widget if hasattr(event, 'widget') else None

    def on_static_click(self, event) -> None:
        """Handle filter clicks via Static widget."""
        pass

    async def on_track_table_track_selected(self, event: TrackTable.TrackSelected) -> None:
        """Handle track selection — play it."""
        self.post_message(self.PlayTrack(event.track))

    async def on_track_table_track_add_to_queue(self, event: TrackTable.TrackAddToQueue) -> None:
        """Handle add-to-queue."""
        self.post_message(self.AddToQueue(event.track))

    def focus_search(self) -> None:
        """Focus the search input."""
        try:
            inp = self.query_one("#search-input", Input)
            inp.focus()
        except Exception:
            pass

    def set_filter(self, filter_type: str) -> None:
        """Change the active filter."""
        self._current_filter = filter_type
        # Update visual state
        for fid in ("filter-songs", "filter-albums", "filter-artists"):
            try:
                btn = self.query_one(f"#{fid}", Static)
                label = fid.replace("filter-", "").capitalize()
                if fid == f"filter-{filter_type}":
                    btn.update(f"⦿ {label}")
                    btn.add_class("-active")
                else:
                    btn.update(f"◯ {label}")
                    btn.remove_class("-active")
            except Exception:
                pass

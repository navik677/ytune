"""Queue view widget — displays and manages the playback queue."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static
from textual.widget import Widget
from textual.message import Message

from ytune.models import Track
from ytune.widgets.track_table import TrackTable


class QueueView(Widget):
    """Queue tab — shows tracks in the playback queue."""

    DEFAULT_CSS = """
    QueueView {
        height: 1fr;
        width: 1fr;
    }
    QueueView #queue-header {
        height: 1;
        padding: 0 1;
        background: #1e1b4b;
        color: #c4b5fd;
        text-style: bold;
    }
    QueueView #queue-table {
        height: 1fr;
    }
    QueueView #queue-empty {
        height: 1fr;
        content-align: center middle;
        color: #475569;
        text-style: italic;
    }
    """

    class PlayFromQueue(Message):
        """Request to play a specific track from queue."""
        def __init__(self, track: Track, index: int) -> None:
            self.track = track
            self.index = index
            super().__init__()

    class RemoveFromQueue(Message):
        """Request to remove a track from queue."""
        def __init__(self, index: int) -> None:
            self.index = index
            super().__init__()

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("♫ Queue — 0 tracks", id="queue-header")
            yield TrackTable(show_index=True, id="queue-table")
            yield Static("Queue is empty\n\nSearch for music and add tracks with [a]", id="queue-empty")

    def on_mount(self) -> None:
        """Hide table initially if queue is empty."""
        pass

    def update_queue(self, tracks: list[Track], current_index: int = -1) -> None:
        """Refresh the queue display."""
        header = self.query_one("#queue-header", Static)
        table = self.query_one("#queue-table", TrackTable)
        empty = self.query_one("#queue-empty", Static)

        count = len(tracks)
        header.update(f"♫ Queue — {count} track{'s' if count != 1 else ''}")

        if count == 0:
            table.display = False
            empty.display = True
        else:
            table.display = True
            empty.display = False
            table.load_tracks(tracks, highlight_index=current_index)

    async def on_track_table_track_selected(self, event: TrackTable.TrackSelected) -> None:
        """Play track from queue."""
        self.post_message(self.PlayFromQueue(event.track, event.index))

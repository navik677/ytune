"""Track table widget — reusable DataTable for track listings."""

from __future__ import annotations

from textual.widgets import DataTable
from textual.message import Message

from ytune.models import Track


class TrackTable(DataTable):
    """A DataTable specialized for displaying tracks."""

    DEFAULT_CSS = """
    TrackTable {
        height: 1fr;
    }
    TrackTable > .datatable--header {
        background: #1e1b4b;
        color: #a78bfa;
        text-style: bold;
    }
    TrackTable > .datatable--cursor {
        background: #4c1d95;
        color: #f5f3ff;
    }
    TrackTable > .datatable--hover {
        background: #312e81 30%;
    }
    """

    class TrackSelected(Message):
        """Emitted when a track is selected (Enter key)."""
        def __init__(self, track: Track, index: int) -> None:
            self.track = track
            self.index = index
            super().__init__()

    class TrackAddToQueue(Message):
        """Emitted when user wants to add a track to queue."""
        def __init__(self, track: Track) -> None:
            self.track = track
            super().__init__()

    def __init__(self, show_index: bool = True, **kwargs) -> None:
        super().__init__(**kwargs)
        self._tracks: list[Track] = []
        self._show_index = show_index
        self.cursor_type = "row"
        self.zebra_stripes = True

    def on_mount(self) -> None:
        """Set up columns when mounted."""
        if self._show_index:
            self.add_column("#", width=5, key="index")
        self.add_column("Title", width=None, key="title")
        self.add_column("Artist", width=20, key="artist")
        self.add_column("Album", width=20, key="album")
        self.add_column("Duration", width=8, key="duration")

    def load_tracks(self, tracks: list[Track], highlight_index: int = -1) -> None:
        """Load tracks into the table."""
        self._tracks = list(tracks)
        self.clear()
        for i, track in enumerate(tracks):
            marker = "▶ " if i == highlight_index else ""
            row_data = []
            if self._show_index:
                if i == highlight_index:
                    row_data.append(f"▶{i + 1}")
                else:
                    row_data.append(str(i + 1))
            row_data.extend([
                f"{marker}{track.display_title}",
                track.display_artist,
                track.album or "—",
                track.duration_str,
            ])
            style = "bold #e879f9" if i == highlight_index else ""
            self.add_row(*row_data, key=str(i))

    def get_track_at(self, index: int) -> Track | None:
        """Get track by index."""
        if 0 <= index < len(self._tracks):
            return self._tracks[index]
        return None

    @property
    def selected_track(self) -> Track | None:
        """Get the currently selected track."""
        if self.cursor_row is not None:
            return self.get_track_at(self.cursor_row)
        return None

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection (Enter key)."""
        try:
            index = int(str(event.row_key.value))
            track = self.get_track_at(index)
            if track:
                self.post_message(self.TrackSelected(track, index))
        except (ValueError, TypeError):
            pass

    def action_add_to_queue(self) -> None:
        """Add selected track to queue (bound to 'a' key)."""
        track = self.selected_track
        if track:
            self.post_message(self.TrackAddToQueue(track))

"""Library view widget — browse user's YouTube Music library."""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Tree
from textual.widget import Widget
from textual.message import Message

from ytune.models import Track, Playlist
from ytune.widgets.track_table import TrackTable

log = logging.getLogger(__name__)


class LibraryView(Widget):
    """Library tab — shows playlists, liked songs, etc. (requires auth)."""

    DEFAULT_CSS = """
    LibraryView {
        height: 1fr;
        width: 1fr;
    }
    LibraryView #library-no-auth {
        height: 1fr;
        content-align: center middle;
        color: #64748b;
    }
    LibraryView #library-tree {
        height: 1fr;
        width: 1fr;
        background: #0a0a1a;
        padding: 1;
    }
    LibraryView #library-tree > .tree--cursor {
        background: #4c1d95;
        color: #f5f3ff;
    }
    LibraryView #library-status {
        height: 1;
        padding: 0 1;
        color: #64748b;
    }
    LibraryView #library-tracks {
        height: 1fr;
        display: none;
    }
    """

    class PlayTrack(Message):
        """Request to play a track."""
        def __init__(self, track: Track) -> None:
            self.track = track
            super().__init__()

    class LoadPlaylist(Message):
        """Request to load a playlist into queue."""
        def __init__(self, playlist_id: str, title: str) -> None:
            self.playlist_id = playlist_id
            self.title = title
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._playlists: list[Playlist] = []
        self._is_authenticated = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(
                "🔒 Authentication Required\n\n"
                "Run 'ytune auth' to connect your YouTube Music account\n"
                "and access your library, playlists, and liked songs.",
                id="library-no-auth",
            )
            yield Static("Library", id="library-status")
            tree: Tree = Tree("📚 Library", id="library-tree")
            tree.show_root = True
            tree.guide_depth = 3
            yield tree
            yield TrackTable(show_index=True, id="library-tracks")

    def on_mount(self) -> None:
        """Check auth and load library."""
        tree = self.query_one("#library-tree", Tree)
        tree.display = False
        status = self.query_one("#library-status", Static)
        status.display = False

    async def load_library(self, is_authenticated: bool) -> None:
        """Load the library data."""
        self._is_authenticated = is_authenticated
        no_auth = self.query_one("#library-no-auth", Static)
        tree = self.query_one("#library-tree", Tree)
        status = self.query_one("#library-status", Static)

        if not is_authenticated:
            no_auth.display = True
            tree.display = False
            status.display = False
            return

        no_auth.display = False
        tree.display = True
        status.display = True
        status.update("Loading library...")

        self.run_worker(self._fetch_library(), exclusive=True, name="load-library")

    async def _fetch_library(self) -> None:
        """Fetch library data from YouTube Music."""
        try:
            app = self.app
            if not hasattr(app, "ytmusic"):
                return

            tree = self.query_one("#library-tree", Tree)
            tree.clear()

            # Liked Songs node
            liked_node = tree.root.add("❤️ Liked Songs", data={"type": "liked"})
            liked_node.allow_expand = True

            # Playlists
            playlists = await app.ytmusic.get_library_playlists()
            self._playlists = playlists

            playlists_node = tree.root.add("📋 Playlists", data={"type": "playlists_root"})
            for pl in playlists:
                pl_node = playlists_node.add(
                    f"🎵 {pl.title} ({pl.track_count})",
                    data={"type": "playlist", "id": pl.playlist_id, "title": pl.title},
                )
                pl_node.allow_expand = True

            tree.root.expand()
            playlists_node.expand()

            status = self.query_one("#library-status", Static)
            status.update(f"Library: {len(playlists)} playlists")

        except Exception as e:
            log.error("Failed to load library: %s", e)
            status = self.query_one("#library-status", Static)
            status.update(f"Error loading library: {e}")

    async def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection."""
        data = event.node.data
        if not data:
            return

        node_type = data.get("type", "")

        if node_type == "liked":
            self.run_worker(self._load_liked_songs(), exclusive=True, name="load-liked")

        elif node_type == "playlist":
            playlist_id = data.get("id", "")
            title = data.get("title", "")
            if playlist_id:
                self.post_message(self.LoadPlaylist(playlist_id, title))

    async def _load_liked_songs(self) -> None:
        """Load liked songs and show in table."""
        try:
            app = self.app
            if not hasattr(app, "ytmusic"):
                return

            status = self.query_one("#library-status", Static)
            status.update("Loading liked songs...")

            tracks = await app.ytmusic.get_liked_songs(limit=100)

            table = self.query_one("#library-tracks", TrackTable)
            table.display = True
            table.load_tracks(tracks)

            status.update(f"❤️ Liked Songs — {len(tracks)} tracks")

        except Exception as e:
            log.error("Failed to load liked songs: %s", e)

    async def on_track_table_track_selected(self, event: TrackTable.TrackSelected) -> None:
        """Play selected track."""
        self.post_message(self.PlayTrack(event.track))

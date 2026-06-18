"""ytune — Main Textual Application."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, TabbedContent, TabPane, Static

from ytune.config import Config
from ytune.models import Track, PlaybackState, RepeatMode
from ytune.player import Player
from ytune.queue_manager import QueueManager
from ytune.ytmusic_client import YTMusicClient
from ytune.widgets.album_art import AlbumArt
from ytune.widgets.now_playing import NowPlaying
from ytune.widgets.search_view import SearchView
from ytune.widgets.queue_view import QueueView
from ytune.widgets.library_view import LibraryView

log = logging.getLogger(__name__)

STYLES_PATH = Path(__file__).parent / "styles" / "app.tcss"


class YTuneApp(App):
    """ytune — Terminal YouTube Music Player."""

    TITLE = "ytune"
    SUB_TITLE = "YouTube Music Player"
    CSS_PATH = STYLES_PATH if STYLES_PATH.exists() else None

    BINDINGS = [
        ("space", "toggle_pause", "Play/Pause"),
        ("n", "next_track", "Next"),
        ("p", "prev_track", "Previous"),
        ("s", "stop", "Stop"),
        ("slash", "focus_search", "Search"),
        ("plus", "volume_up", "Vol +"),
        ("minus", "volume_down", "Vol −"),
        ("r", "cycle_repeat", "Repeat"),
        ("z", "toggle_shuffle", "Shuffle"),
        ("a", "add_to_queue", "Add to Queue"),
        ("d", "remove_from_queue", "Remove"),
        ("left", "seek_back", "Seek −5s"),
        ("right", "seek_forward", "Seek +5s"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config = Config.load()
        self.player = Player()
        self.queue = QueueManager()
        self.ytmusic = YTMusicClient(self.config)
        self._update_timer = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            with Vertical(id="sidebar"):
                yield AlbumArt(id="album-art")
            with Vertical(id="content-area"):
                with TabbedContent(id="tabs"):
                    with TabPane("♫ Queue", id="tab-queue"):
                        yield QueueView(id="queue-view")
                    with TabPane("🔍 Search", id="tab-search"):
                        yield SearchView(id="search-view")
                    with TabPane("📚 Library", id="tab-library"):
                        yield LibraryView(id="library-view")
        yield NowPlaying(id="now-playing")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize everything when the app mounts."""
        # Initialize player
        try:
            self.player.initialize()
            self.player.volume = self.config.volume
        except RuntimeError as e:
            self.notify(str(e), severity="error", timeout=10)
            return

        # Set up player callbacks
        self.player.on_position_change = self._on_position_change
        self.player.on_state_change = self._on_state_change
        self.player.on_track_end = self._on_track_end

        # Initialize YouTube Music client
        await self.ytmusic.initialize()

        # Load library if authenticated
        library_view = self.query_one("#library-view", LibraryView)
        await library_view.load_library(self.ytmusic.is_authenticated)

        # Start the UI update timer (every 500ms)
        self._update_timer = self.set_interval(0.5, self._tick)

        # Auto-focus search on start
        self.set_timer(0.3, self._initial_focus)

        # Show auth status
        if self.ytmusic.is_authenticated:
            self.notify("✓ Connected to YouTube Music", severity="information", timeout=3)
        else:
            self.notify(
                "Not authenticated — run 'ytune auth' for full access",
                severity="warning",
                timeout=5,
            )

    def _initial_focus(self) -> None:
        """Focus the search tab initially."""
        try:
            tabs = self.query_one("#tabs", TabbedContent)
            tabs.active = "tab-search"
            search = self.query_one("#search-view", SearchView)
            search.focus_search()
        except Exception:
            pass

    # ── Playback Controls ──

    def action_toggle_pause(self) -> None:
        """Toggle play/pause."""
        if self.player.state == PlaybackState.STOPPED:
            # If stopped, try to play current queue track
            track = self.queue.current_track
            if track:
                self._play_track(track)
        else:
            self.player.toggle_pause()

    def action_next_track(self) -> None:
        """Play next track in queue."""
        track = self.queue.next()
        if track:
            self._play_track(track)
        else:
            self.notify("End of queue", severity="information", timeout=2)

    def action_prev_track(self) -> None:
        """Play previous track in queue."""
        # If more than 3 seconds in, restart current track
        if self.player.position > 3.0:
            self.player.seek(0)
            return
        track = self.queue.previous()
        if track:
            self._play_track(track)

    def action_stop(self) -> None:
        """Stop playback."""
        self.player.stop()
        now_playing = self.query_one("#now-playing", NowPlaying)
        now_playing.update_state(PlaybackState.STOPPED)

    def action_seek_back(self) -> None:
        """Seek back 5 seconds."""
        self.player.seek_relative(-5)

    def action_seek_forward(self) -> None:
        """Seek forward 5 seconds."""
        self.player.seek_relative(5)

    def action_volume_up(self) -> None:
        """Increase volume by 5%."""
        self.player.volume = self.player.volume + 5
        self._update_volume_display()
        self.notify(f"Volume: {self.player.volume}%", timeout=1)

    def action_volume_down(self) -> None:
        """Decrease volume by 5%."""
        self.player.volume = self.player.volume - 5
        self._update_volume_display()
        self.notify(f"Volume: {self.player.volume}%", timeout=1)

    def action_cycle_repeat(self) -> None:
        """Cycle repeat mode."""
        mode = self.queue.cycle_repeat()
        now_playing = self.query_one("#now-playing", NowPlaying)
        now_playing.repeat_mode = mode
        labels = {RepeatMode.OFF: "off", RepeatMode.ALL: "all", RepeatMode.ONE: "one"}
        self.notify(f"Repeat: {labels.get(mode, 'off')}", timeout=1)

    def action_toggle_shuffle(self) -> None:
        """Toggle shuffle."""
        enabled = self.queue.toggle_shuffle()
        now_playing = self.query_one("#now-playing", NowPlaying)
        now_playing.shuffle_on = enabled
        self.notify(f"Shuffle: {'on' if enabled else 'off'}", timeout=1)

    def action_focus_search(self) -> None:
        """Focus the search input."""
        tabs = self.query_one("#tabs", TabbedContent)
        tabs.active = "tab-search"
        search = self.query_one("#search-view", SearchView)
        search.focus_search()

    def action_add_to_queue(self) -> None:
        """Add selected track to queue from current view."""
        # Try to get selected track from the active tab
        try:
            tabs = self.query_one("#tabs", TabbedContent)
            active_id = tabs.active
            if active_id == "tab-search":
                search = self.query_one("#search-view", SearchView)
                table = search.query_one("#search-results")
                if hasattr(table, 'selected_track') and table.selected_track:
                    self._add_track_to_queue(table.selected_track)
        except Exception:
            pass

    def action_remove_from_queue(self) -> None:
        """Remove selected track from queue."""
        try:
            queue_view = self.query_one("#queue-view", QueueView)
            table = queue_view.query_one("#queue-table")
            if hasattr(table, 'cursor_row') and table.cursor_row is not None:
                self.queue.remove(table.cursor_row)
                self._refresh_queue_view()
                self.notify("Removed from queue", timeout=1)
        except Exception:
            pass

    # ── Event Handlers from Widgets ──

    async def on_search_view_play_track(self, event: SearchView.PlayTrack) -> None:
        """Handle play request from search."""
        # Add to queue and play
        self.queue.add(event.track)
        index = self.queue.length - 1
        self.queue.set_current(index)
        self._play_track(event.track)
        self._refresh_queue_view()

    async def on_search_view_add_to_queue(self, event: SearchView.AddToQueue) -> None:
        """Handle add-to-queue from search."""
        self._add_track_to_queue(event.track)

    async def on_queue_view_play_from_queue(self, event: QueueView.PlayFromQueue) -> None:
        """Handle play request from queue view."""
        self.queue.set_current(event.index)
        self._play_track(event.track)

    async def on_library_view_play_track(self, event: LibraryView.PlayTrack) -> None:
        """Handle play request from library."""
        self.queue.add(event.track)
        index = self.queue.length - 1
        self.queue.set_current(index)
        self._play_track(event.track)
        self._refresh_queue_view()

    async def on_library_view_load_playlist(self, event: LibraryView.LoadPlaylist) -> None:
        """Handle playlist load from library."""
        self.notify(f"Loading '{event.title}'...", timeout=2)
        try:
            playlist = await self.ytmusic.get_playlist(event.playlist_id)
            if playlist.tracks:
                self.queue.clear()
                self.queue.add_many(playlist.tracks)
                self.queue.set_current(0)
                self._play_track(playlist.tracks[0])
                self._refresh_queue_view()
                self.notify(f"Loaded {len(playlist.tracks)} tracks from '{event.title}'", timeout=3)
                # Switch to queue tab
                tabs = self.query_one("#tabs", TabbedContent)
                tabs.active = "tab-queue"
        except Exception as e:
            self.notify(f"Failed to load playlist: {e}", severity="error", timeout=5)

    # ── Internal Methods ──

    def _play_track(self, track: Track) -> None:
        """Start playing a track."""
        log.info("Playing: %s — %s", track.title, track.artist)
        self.player.play(track.video_id)

        # Update Now Playing
        now_playing = self.query_one("#now-playing", NowPlaying)
        now_playing.update_track(track.display_title, track.display_artist)
        now_playing.update_state(PlaybackState.BUFFERING)

        # Update Album Art
        album_art = self.query_one("#album-art", AlbumArt)
        album_art.thumbnail_url = track.thumbnail_url

        # Refresh queue highlight
        self._refresh_queue_view()

    def _add_track_to_queue(self, track: Track) -> None:
        """Add a track to the queue."""
        self.queue.add(track)
        self._refresh_queue_view()
        self.notify(f"Added: {track.display_title}", timeout=2)

        # If nothing is playing, start playing
        if self.player.state == PlaybackState.STOPPED and self.queue.length == 1:
            self.queue.set_current(0)
            self._play_track(track)

    def _refresh_queue_view(self) -> None:
        """Refresh the queue view."""
        try:
            queue_view = self.query_one("#queue-view", QueueView)
            queue_view.update_queue(self.queue.tracks, self.queue.current_index)
        except Exception:
            pass

    def _update_volume_display(self) -> None:
        """Update volume in the now playing bar."""
        now_playing = self.query_one("#now-playing", NowPlaying)
        now_playing.volume = self.player.volume

    # ── Player Callbacks (called from mpv thread!) ──

    def _on_position_change(self, position: float, duration: float) -> None:
        """Called from mpv thread when position changes."""
        try:
            self.call_from_thread(self._update_position, position, duration)
        except Exception:
            pass

    def _on_state_change(self, state: PlaybackState) -> None:
        """Called from mpv thread when playback state changes."""
        try:
            self.call_from_thread(self._update_state, state)
        except Exception:
            pass

    def _on_track_end(self) -> None:
        """Called from mpv thread when a track ends."""
        try:
            self.call_from_thread(self._handle_track_end)
        except Exception:
            pass

    def _update_position(self, position: float, duration: float) -> None:
        """Update the position display (called on main thread)."""
        now_playing = self.query_one("#now-playing", NowPlaying)
        now_playing.update_position(position, duration)

    def _update_state(self, state: PlaybackState) -> None:
        """Update the state display (called on main thread)."""
        now_playing = self.query_one("#now-playing", NowPlaying)
        now_playing.update_state(state)

    def _handle_track_end(self) -> None:
        """Handle track end — play next track or stop."""
        track = self.queue.next()
        if track:
            self._play_track(track)
        else:
            now_playing = self.query_one("#now-playing", NowPlaying)
            now_playing.update_state(PlaybackState.STOPPED)

    def _tick(self) -> None:
        """Periodic update tick for UI refresh."""
        if self.player.state in (PlaybackState.PLAYING, PlaybackState.BUFFERING):
            pos = self.player.position
            dur = self.player.duration
            if pos > 0 or dur > 0:
                now_playing = self.query_one("#now-playing", NowPlaying)
                now_playing.update_position(pos, dur)

    async def action_quit(self) -> None:
        """Clean up and quit."""
        # Save config
        self.config.volume = self.player.volume
        self.config.save()
        # Shutdown player
        self.player.shutdown()
        self.exit()

"""Now Playing bar widget — shows current track, progress, and controls."""

from __future__ import annotations

from rich.text import Text
from textual.widget import Widget
from textual.reactive import reactive

from ytune.models import PlaybackState, RepeatMode, _format_time


class NowPlaying(Widget):
    """Bottom bar showing current track info, progress bar, and controls."""

    DEFAULT_CSS = """
    NowPlaying {
        height: 4;
        dock: bottom;
        padding: 0 1;
    }
    """

    # Reactive state
    track_title: reactive[str] = reactive("", layout=True)
    track_artist: reactive[str] = reactive("", layout=True)
    position: reactive[float] = reactive(0.0)
    duration: reactive[float] = reactive(0.0)
    playback_state: reactive[PlaybackState] = reactive(PlaybackState.STOPPED)
    volume: reactive[int] = reactive(75)
    repeat_mode: reactive[RepeatMode] = reactive(RepeatMode.OFF)
    shuffle_on: reactive[bool] = reactive(False)

    def render(self) -> Text:
        """Render the now-playing bar."""
        width = self.size.width - 2
        if width < 20:
            return Text("...")

        text = Text()

        # Line 1: State icon + Track title — Artist
        state_icon = self._state_icon()
        title = self.track_title or "No track loaded"
        artist = self.track_artist

        line1 = Text()
        line1.append(f" {state_icon} ", style="bold #e879f9")
        if self.playback_state == PlaybackState.STOPPED and not self.track_title:
            line1.append("Ready to play", style="dim italic #94a3b8")
        else:
            line1.append(title, style="bold #f0abfc")
            if artist:
                line1.append(" — ", style="dim #64748b")
                line1.append(artist, style="#c084fc")
        text.append_text(line1)
        text.append("\n")

        # Line 2: Progress bar
        pos_str = _format_time(self.position)
        dur_str = _format_time(self.duration)
        time_str = f" {pos_str} / {dur_str} "

        bar_width = width - len(time_str) - 4
        if bar_width < 10:
            bar_width = 10

        progress = self.position / self.duration if self.duration > 0 else 0.0
        filled = int(bar_width * progress)
        empty = bar_width - filled

        line2 = Text()
        line2.append("  ")
        line2.append("━" * filled, style="bold #a855f7")
        if filled < bar_width:
            line2.append("╸", style="bold #a855f7")
            line2.append("━" * max(0, empty - 1), style="dim #334155")
        line2.append(time_str, style="#94a3b8")
        text.append_text(line2)
        text.append("\n")

        # Line 3: Controls
        line3 = Text()
        line3.append("  ⏮ ", style="dim #94a3b8")
        if self.playback_state == PlaybackState.PLAYING:
            line3.append(" ⏸ ", style="bold #e879f9")
        else:
            line3.append(" ▶ ", style="bold #e879f9")
        line3.append(" ⏭  ", style="dim #94a3b8")

        # Shuffle
        if self.shuffle_on:
            line3.append(" 🔀 on ", style="bold #22d3ee")
        else:
            line3.append(" 🔀 off ", style="dim #475569")

        # Repeat
        if self.repeat_mode == RepeatMode.ALL:
            line3.append(" 🔁 all ", style="bold #22d3ee")
        elif self.repeat_mode == RepeatMode.ONE:
            line3.append(" 🔂 one ", style="bold #f59e0b")
        else:
            line3.append(" 🔁 off ", style="dim #475569")

        # Volume
        vol_color = "#22d3ee" if self.volume > 0 else "dim #475569"
        line3.append(f"  🔊 {self.volume}%", style=vol_color)

        text.append_text(line3)

        return text

    def _state_icon(self) -> str:
        """Get the playback state icon."""
        match self.playback_state:
            case PlaybackState.PLAYING:
                return "▶"
            case PlaybackState.PAUSED:
                return "⏸"
            case PlaybackState.BUFFERING:
                return "⟳"
            case _:
                return "⏹"

    def update_position(self, pos: float, dur: float) -> None:
        """Update the position and duration (called from timer)."""
        self.position = pos
        self.duration = dur
        self.refresh()

    def update_track(self, title: str, artist: str) -> None:
        """Update the current track info."""
        self.track_title = title
        self.track_artist = artist
        self.refresh()

    def update_state(self, state: PlaybackState) -> None:
        """Update the playback state."""
        self.playback_state = state
        self.refresh()

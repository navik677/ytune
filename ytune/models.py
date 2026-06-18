"""Data models for ytune."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class RepeatMode(Enum):
    """Repeat mode for the queue."""
    OFF = auto()
    ALL = auto()
    ONE = auto()


class PlaybackState(Enum):
    """Current playback state."""
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()
    BUFFERING = auto()


@dataclass
class Track:
    """Represents a single music track."""
    video_id: str
    title: str
    artist: str
    album: str = ""
    duration_seconds: int = 0
    thumbnail_url: str = ""
    is_available: bool = True

    @property
    def duration_str(self) -> str:
        """Format duration as M:SS or H:MM:SS."""
        if self.duration_seconds <= 0:
            return "—:——"
        hours, remainder = divmod(self.duration_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    @property
    def display_artist(self) -> str:
        return self.artist or "Unknown Artist"

    @property
    def display_title(self) -> str:
        return self.title or "Unknown Title"


@dataclass
class Playlist:
    """Represents a playlist."""
    playlist_id: str
    title: str
    description: str = ""
    track_count: int = 0
    thumbnail_url: str = ""
    tracks: list[Track] = field(default_factory=list)


@dataclass
class SearchResult:
    """Container for search results."""
    query: str = ""
    tracks: list[Track] = field(default_factory=list)
    albums: list[dict] = field(default_factory=list)
    artists: list[dict] = field(default_factory=list)
    playlists: list[Playlist] = field(default_factory=list)


@dataclass
class PlayerState:
    """Snapshot of current player state."""
    playback: PlaybackState = PlaybackState.STOPPED
    current_track: Optional[Track] = None
    position: float = 0.0
    duration: float = 0.0
    volume: int = 75
    repeat: RepeatMode = RepeatMode.OFF
    shuffle: bool = False

    @property
    def position_str(self) -> str:
        return _format_time(self.position)

    @property
    def duration_str(self) -> str:
        return _format_time(self.duration)

    @property
    def progress(self) -> float:
        """Progress as 0.0–1.0."""
        if self.duration <= 0:
            return 0.0
        return min(self.position / self.duration, 1.0)


def _format_time(seconds: float) -> str:
    """Format seconds as M:SS or H:MM:SS."""
    total = int(max(0, seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"

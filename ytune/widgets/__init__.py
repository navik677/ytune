"""ytune widgets package."""

from ytune.widgets.now_playing import NowPlaying
from ytune.widgets.track_table import TrackTable
from ytune.widgets.search_view import SearchView
from ytune.widgets.queue_view import QueueView
from ytune.widgets.library_view import LibraryView
from ytune.widgets.album_art import AlbumArt

__all__ = [
    "NowPlaying",
    "TrackTable",
    "SearchView",
    "QueueView",
    "LibraryView",
    "AlbumArt",
]

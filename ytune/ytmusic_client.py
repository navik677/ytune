"""YouTube Music API client wrapper for ytune."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ytmusicapi import YTMusic

from ytune.config import get_config_dir, Config
from ytune.models import Track, Playlist, SearchResult

log = logging.getLogger(__name__)


class YTMusicClient:
    """Async-friendly wrapper around ytmusicapi."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._ytm: Optional[YTMusic] = None
        self._authenticated = False

    async def initialize(self) -> None:
        """Initialize the YouTube Music client."""
        try:
            oauth_file = self._config.oauth_file
            if oauth_file:
                self._ytm = await asyncio.to_thread(YTMusic, str(oauth_file))
                self._authenticated = True
                log.info("Authenticated with YouTube Music (OAuth)")
            else:
                self._ytm = await asyncio.to_thread(YTMusic)
                self._authenticated = False
                log.info("Using YouTube Music without authentication")
        except Exception as e:
            log.error("Failed to initialize YouTube Music client: %s", e)
            # Fallback to unauthenticated
            self._ytm = await asyncio.to_thread(YTMusic)
            self._authenticated = False

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    async def search(self, query: str, filter_type: str = "songs", limit: int = 20) -> list[Track]:
        """Search YouTube Music and return tracks."""
        if not self._ytm:
            return []

        try:
            results = await asyncio.to_thread(
                self._ytm.search, query, filter=filter_type, limit=limit
            )
            tracks = []
            for item in results:
                track = self._parse_track(item)
                if track:
                    tracks.append(track)
            return tracks
        except Exception as e:
            log.error("Search failed: %s", e)
            return []

    async def get_playlist(self, playlist_id: str, limit: int = 100) -> Playlist:
        """Get a playlist with its tracks."""
        if not self._ytm:
            return Playlist(playlist_id=playlist_id, title="Error")

        try:
            data = await asyncio.to_thread(
                self._ytm.get_playlist, playlist_id, limit=limit
            )
            tracks = []
            for item in data.get("tracks", []):
                track = self._parse_track(item)
                if track:
                    tracks.append(track)

            return Playlist(
                playlist_id=playlist_id,
                title=data.get("title", "Unknown Playlist"),
                description=data.get("description", ""),
                track_count=data.get("trackCount", len(tracks)),
                thumbnail_url=self._get_thumbnail(data),
                tracks=tracks,
            )
        except Exception as e:
            log.error("Failed to get playlist: %s", e)
            return Playlist(playlist_id=playlist_id, title="Error")

    async def get_library_playlists(self, limit: int = 25) -> list[Playlist]:
        """Get user's library playlists (requires auth)."""
        if not self._ytm or not self._authenticated:
            return []

        try:
            data = await asyncio.to_thread(
                self._ytm.get_library_playlists, limit=limit
            )
            playlists = []
            for item in data:
                playlists.append(Playlist(
                    playlist_id=item.get("playlistId", ""),
                    title=item.get("title", "Unknown"),
                    track_count=item.get("count", 0),
                    thumbnail_url=self._get_thumbnail(item),
                ))
            return playlists
        except Exception as e:
            log.error("Failed to get library playlists: %s", e)
            return []

    async def get_liked_songs(self, limit: int = 100) -> list[Track]:
        """Get user's liked songs (requires auth)."""
        if not self._ytm or not self._authenticated:
            return []

        try:
            data = await asyncio.to_thread(
                self._ytm.get_liked_songs, limit=limit
            )
            tracks = []
            for item in data.get("tracks", []):
                track = self._parse_track(item)
                if track:
                    tracks.append(track)
            return tracks
        except Exception as e:
            log.error("Failed to get liked songs: %s", e)
            return []

    async def get_home(self, limit: int = 6) -> list[dict]:
        """Get home page recommendations."""
        if not self._ytm:
            return []

        try:
            return await asyncio.to_thread(self._ytm.get_home, limit=limit)
        except Exception as e:
            log.error("Failed to get home: %s", e)
            return []

    async def get_watch_playlist(self, video_id: str, limit: int = 25) -> list[Track]:
        """Get the auto-generated watch playlist (radio/up-next) for a video."""
        if not self._ytm:
            return []

        try:
            data = await asyncio.to_thread(
                self._ytm.get_watch_playlist, videoId=video_id, limit=limit
            )
            tracks = []
            for item in data.get("tracks", []):
                track = self._parse_track(item)
                if track:
                    tracks.append(track)
            return tracks
        except Exception as e:
            log.error("Failed to get watch playlist: %s", e)
            return []

    @staticmethod
    def setup_oauth(client_id: str, client_secret: str) -> str:
        """Run interactive OAuth setup. Returns the path to the oauth file."""
        import ytmusicapi
        oauth_path = get_config_dir() / "oauth.json"
        ytmusicapi.setup_oauth(client_id=client_id, client_secret=client_secret, filepath=str(oauth_path), open_browser=True)
        return str(oauth_path)

    @staticmethod
    def setup_browser(headers_raw: str) -> str:
        """Run browser header setup. Returns the path to the oauth file."""
        import ytmusicapi
        import json
        oauth_path = get_config_dir() / "oauth.json"
        ytmusicapi.setup(filepath=str(oauth_path), headers_raw=headers_raw)
        
        # Inject dummy Authorization header and strip Accept-Encoding to prevent Brotli issues
        try:
            with open(oauth_path) as f:
                data = json.load(f)
            data["Authorization"] = "SAPISIDHASH dummy"
            data.pop("accept-encoding", None)
            data.pop("Accept-Encoding", None)
            with open(oauth_path, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            log.warning("Failed to post-process oauth.json: %s", e)
            
        return str(oauth_path)

    def _parse_track(self, item: dict) -> Optional[Track]:
        """Parse a track dict from ytmusicapi into a Track model."""
        try:
            video_id = item.get("videoId")
            if not video_id:
                return None

            # Parse artists
            artists = item.get("artists") or item.get("artist")
            if isinstance(artists, list):
                artist = ", ".join(a.get("name", "") for a in artists if a.get("name"))
            elif isinstance(artists, str):
                artist = artists
            else:
                artist = "Unknown Artist"

            # Parse album
            album_data = item.get("album")
            if isinstance(album_data, dict):
                album = album_data.get("name", "")
            elif isinstance(album_data, str):
                album = album_data
            else:
                album = ""

            # Parse duration
            duration_str = item.get("duration", "") or ""
            duration_seconds = item.get("duration_seconds", 0)
            if not duration_seconds and duration_str:
                duration_seconds = self._parse_duration(duration_str)

            return Track(
                video_id=video_id,
                title=item.get("title", "Unknown"),
                artist=artist,
                album=album,
                duration_seconds=duration_seconds,
                thumbnail_url=self._get_thumbnail(item),
                is_available=item.get("isAvailable", True),
            )
        except Exception as e:
            log.debug("Failed to parse track: %s — %s", e, item)
            return None

    @staticmethod
    def _get_thumbnail(item: dict) -> str:
        """Extract thumbnail URL from item data."""
        thumbnails = item.get("thumbnails") or []
        if thumbnails:
            # Prefer medium resolution
            if len(thumbnails) > 1:
                return thumbnails[-2].get("url", thumbnails[0].get("url", ""))
            return thumbnails[0].get("url", "")
        return ""

    @staticmethod
    def _parse_duration(duration_str: str) -> int:
        """Parse duration string like '3:45' or '1:02:30' into seconds."""
        try:
            parts = duration_str.split(":")
            parts = [int(p) for p in parts]
            if len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2:
                return parts[0] * 60 + parts[1]
            return 0
        except (ValueError, IndexError):
            return 0

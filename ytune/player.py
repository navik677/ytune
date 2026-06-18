"""Audio player wrapper around mpv for ytune."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Callable, Optional

import mpv

from ytune.config import get_config_dir
from ytune.models import PlaybackState

log = logging.getLogger(__name__)


class Player:
    """Wraps python-mpv for audio playback of YouTube Music tracks.

    We resolve the direct streaming URLs ourselves via Python's yt-dlp library
    and pass the direct URLs to mpv. This is faster and much more reliable.
    """

    def __init__(self) -> None:
        self._mpv: Optional[mpv.MPV] = None
        self._state = PlaybackState.STOPPED
        self._volume = 75
        self._lock = threading.Lock()

        # Callbacks — set by the app
        self.on_position_change: Optional[Callable[[float, float], None]] = None
        self.on_state_change: Optional[Callable[[PlaybackState], None]] = None
        self.on_track_end: Optional[Callable[[], None]] = None
        self.on_metadata_change: Optional[Callable[[dict], None]] = None

    def initialize(self) -> None:
        """Create the mpv instance. Must be called before any playback."""
        try:
            def _mpv_log_handler(loglevel, component, message):
                try:
                    with open("/tmp/ytune_mpv.log", "a") as f:
                        f.write(f"[{loglevel}] {component}: {message}\n")
                except Exception:
                    pass

            self._mpv = mpv.MPV(
                ytdl=False,  # We resolve URLs ourselves using Python's yt-dlp
                video=False,
                terminal=False,
                input_default_bindings=False,
                input_vo_keyboard=False,
                log_handler=_mpv_log_handler,
                loglevel='info',
            )
            self._mpv.volume = self._volume

            # Load and apply HTTP auth headers to mpv
            self._load_and_apply_auth_headers()

            # Register observers
            self._mpv.observe_property("time-pos", self._on_time_pos)
            self._mpv.observe_property("duration", self._on_duration)
            self._mpv.observe_property("pause", self._on_pause)
            self._mpv.observe_property("idle-active", self._on_idle)

            # Register end-file event
            @self._mpv.event_callback("end-file")
            def _end_file_handler(event):
                evt_data = event.get("event", {})
                reason = evt_data.get("reason")
                error_code = evt_data.get("error")
                if reason == "error":
                    log.error("mpv playback failed with error: %s", error_code)
                    try:
                        with open("/tmp/ytune_mpv.log", "a") as f:
                            f.write(f"[ERROR] mpv playback failed with error: {error_code}\n")
                    except Exception:
                        pass
                self._handle_track_end()

            log.info("mpv player initialized")
        except Exception as e:
            log.error("Failed to initialize mpv: %s", e)
            raise RuntimeError(
                "Failed to initialize mpv. Make sure mpv and libmpv are installed:\n"
                "  sudo apt install mpv libmpv-dev\n"
                f"Error: {e}"
            ) from e

    def _load_and_apply_auth_headers(self) -> None:
        """Load auth headers from oauth.json and apply them to mpv."""
        oauth_path = get_config_dir() / "oauth.json"
        if oauth_path.exists():
            try:
                with open(oauth_path) as f:
                    data = json.load(f)
                
                user_agent = data.get("user-agent") or data.get("User-Agent")
                cookie_str = data.get("cookie") or data.get("Cookie")
                
                if user_agent or cookie_str:
                    headers_list = []
                    if user_agent:
                        headers_list.append(f"User-Agent: {user_agent}")
                    if cookie_str:
                        headers_list.append(f"Cookie: {cookie_str}")
                    
                    if headers_list and self._mpv:
                        self._mpv["http-header-fields"] = headers_list
                        log.info("Applied auth headers to mpv")
            except Exception as e:
                log.warning("Failed to load/apply auth headers in player: %s", e)

    def play(self, video_id: str) -> None:
        """Play a YouTube Music track by video ID."""
        if not self._mpv:
            return
        self._set_state(PlaybackState.BUFFERING)
        
        # Load fresh auth headers for yt-dlp
        user_agent = None
        cookie_str = None
        oauth_path = get_config_dir() / "oauth.json"
        if oauth_path.exists():
            try:
                with open(oauth_path) as f:
                    data = json.load(f)
                user_agent = data.get("user-agent") or data.get("User-Agent")
                cookie_str = data.get("cookie") or data.get("Cookie")
            except Exception:
                pass

        # Update mpv headers in case they changed
        if user_agent or cookie_str:
            self._load_and_apply_auth_headers()

        def _resolve_and_play():
            import yt_dlp
            url = f"https://music.youtube.com/watch?v={video_id}"
            log.info("Resolving URL with yt-dlp: %s", url)
            
            headers = {}
            if user_agent:
                headers['User-Agent'] = user_agent
            if cookie_str:
                headers['Cookie'] = cookie_str
                
            ydl_opts = {
                'format': 'bestaudio[protocol^=http]/bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'nocheckcertificate': True,
                'remote_components': ['ejs:github'],
                'nocachedir': True,
                'socket_timeout': 10,
            }
            if headers:
                ydl_opts['http_headers'] = headers

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if info and 'url' in info:
                        direct_url = info['url']
                        log.info("Resolved stream URL, starting playback in mpv")
                        with self._lock:
                            if self._mpv:
                                self._mpv.play(direct_url)
                        return
            except Exception as e:
                log.error("Failed to resolve stream URL: %s", e)
            
            # Fallback: try resolving without cookies/headers in case they are expired or invalid
            if headers:
                log.info("Retrying URL resolution without headers...")
                try:
                    ydl_opts_fallback = {
                        'format': 'bestaudio[protocol^=http]/bestaudio/best',
                        'quiet': True,
                        'no_warnings': True,
                        'skip_download': True,
                        'nocheckcertificate': True,
                        'remote_components': ['ejs:github'],
                        'nocachedir': True,
                        'socket_timeout': 10,
                    }
                    with yt_dlp.YoutubeDL(ydl_opts_fallback) as ydl:
                        info = ydl.extract_info(url, download=False)
                        if info and 'url' in info:
                            direct_url = info['url']
                            log.info("Resolved stream URL without headers, starting playback")
                            with self._lock:
                                if self._mpv:
                                    self._mpv.play(direct_url)
                            return
                except Exception as e_fallback:
                    log.error("Failed fallback URL resolution: %s", e_fallback)
            
            # If resolution fails, skip to next track instead of getting stuck
            log.info("Playback failed: could not resolve track stream")
            self._set_state(PlaybackState.STOPPED)
            self._handle_track_end()

        threading.Thread(target=_resolve_and_play, daemon=True).start()

    def play_url(self, url: str) -> None:
        """Play a direct URL."""
        if not self._mpv:
            return
        self._set_state(PlaybackState.BUFFERING)
        self._mpv.play(url)

    def pause(self) -> None:
        """Pause playback."""
        if self._mpv and self._state in (PlaybackState.PLAYING, PlaybackState.BUFFERING):
            self._mpv.pause = True

    def resume(self) -> None:
        """Resume playback."""
        if self._mpv and self._state == PlaybackState.PAUSED:
            self._mpv.pause = False

    def toggle_pause(self) -> None:
        """Toggle pause/resume."""
        if not self._mpv:
            return
        if self._state == PlaybackState.PAUSED:
            self.resume()
        elif self._state in (PlaybackState.PLAYING, PlaybackState.BUFFERING):
            self.pause()

    def stop(self) -> None:
        """Stop playback."""
        if self._mpv:
            self._mpv.command("stop")
            self._set_state(PlaybackState.STOPPED)

    def seek(self, position: float) -> None:
        """Seek to absolute position in seconds."""
        if self._mpv and self._state != PlaybackState.STOPPED:
            self._mpv.seek(position, reference="absolute")

    def seek_relative(self, offset: float) -> None:
        """Seek relative to current position."""
        if self._mpv and self._state != PlaybackState.STOPPED:
            self._mpv.seek(offset, reference="relative")

    @property
    def volume(self) -> int:
        return self._volume

    @volume.setter
    def volume(self, value: int) -> None:
        self._volume = max(0, min(100, value))
        if self._mpv:
            self._mpv.volume = self._volume

    @property
    def position(self) -> float:
        if self._mpv:
            pos = self._mpv.time_pos
            return pos if pos is not None else 0.0
        return 0.0

    @property
    def duration(self) -> float:
        if self._mpv:
            dur = self._mpv.duration
            return dur if dur is not None else 0.0
        return 0.0

    @property
    def state(self) -> PlaybackState:
        return self._state

    @property
    def is_playing(self) -> bool:
        return self._state == PlaybackState.PLAYING

    @property
    def is_paused(self) -> bool:
        return self._state == PlaybackState.PAUSED

    def shutdown(self) -> None:
        """Clean up mpv resources."""
        if self._mpv:
            try:
                self._mpv.terminate()
            except Exception:
                pass
            self._mpv = None

    # --- Private callbacks ---

    def _on_time_pos(self, _name: str, value) -> None:
        if value is not None and self.on_position_change:
            dur = 0.0
            if self._mpv:
                dur = self._mpv.duration or 0.0
            try:
                self.on_position_change(float(value), float(dur))
            except Exception:
                pass

    def _on_duration(self, _name: str, value) -> None:
        # When duration becomes available, we know we're truly playing
        if value is not None and value > 0 and self._state == PlaybackState.BUFFERING:
            self._set_state(PlaybackState.PLAYING)

    def _on_pause(self, _name: str, value) -> None:
        if value is True:
            self._set_state(PlaybackState.PAUSED)
        elif value is False and self._state == PlaybackState.PAUSED:
            self._set_state(PlaybackState.PLAYING)

    def _on_idle(self, _name: str, value) -> None:
        if value is True and self._state != PlaybackState.STOPPED:
            self._set_state(PlaybackState.STOPPED)

    def _handle_track_end(self) -> None:
        if self.on_track_end:
            try:
                self.on_track_end()
            except Exception:
                pass

    def _set_state(self, new_state: PlaybackState) -> None:
        if self._state != new_state:
            self._state = new_state
            if self.on_state_change:
                try:
                    self.on_state_change(new_state)
                except Exception:
                    pass
